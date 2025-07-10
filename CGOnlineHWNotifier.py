import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from plyer import notification
import json
import time

# 基本配置
BASE_URL = "https://cslabcg.whu.edu.cn"
LOGIN_URL = f"{BASE_URL}/login/loginproc.jsp"
CAPTCHA_URL = f"{BASE_URL}/cgjiaoyan"
session = requests.Session()

def load_credentials():
    try:
        with open('credentials.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def save_credentials(stid, pwd):
    with open('credentials.json', 'w') as f:
        json.dump({'stid': stid, 'pwd': pwd}, f)

def get_captcha():
    response = session.get(CAPTCHA_URL)
    image = Image.open(BytesIO(response.content))
    image.save("captcha.png")
    image.show()
    return input("请输入验证码：")

def login(stid, pwd, captcha_code):
    login_data = {"stid": stid, "pwd": pwd, "captchaCode": captcha_code}
    return session.post(LOGIN_URL, data=login_data)

def check_homework(stid, pwd):
    captcha_code = get_captcha()
    response = login(stid, pwd, captcha_code)

    if "用户名或者密码错误！" in response.text:
        print("用户名或密码错误！")
        return
    elif "验证码错误！" in response.text:
        print("验证码错误！")
        return
    elif "选择课程" in response.text:
        print("登录成功！")
        soup = BeautifulSoup(response.text, 'html.parser')

        for i, media_div in enumerate(soup.select('.media'), start=1):
            course_name = media_div.select_one('strong a').text.strip()
            course_link = f"{BASE_URL}/{media_div.select_one('strong a')['href']}"
            session.get(course_link)
            session.get(f"{BASE_URL}/main.jsp")
            course_online_homework = session.get(f"{BASE_URL}/includes/redirect.jsp?tab=-2")
            homework_soup = BeautifulSoup(course_online_homework.text, 'html.parser')

            # ======= 当前作业优化显示 =======
            current_hw_header = homework_soup.select_one("h5 span strong")
            has_current_hw = False

            if current_hw_header and "当前作业" in current_hw_header.get_text():
                current_hw_div = homework_soup.select_one("div.list-group-flush.mb-4")
                if current_hw_div:
                    hw_items = current_hw_div.find_all("a")
                    if hw_items:
                        has_current_hw = True
                        print(f"⚠️ 课程《{course_name}》当前作业：")
                        for a in hw_items:
                            title = a.get_text(strip=True)
                            href = a['href']
                            link = f"{BASE_URL}/{href}" if not href.startswith("http") else href
                            print(f"    - {title} 链接：{link}")

                        # 只提醒最新一条
                        notification.notify(
                            title="在线测试提醒",
                            message=f"{course_name} 有 {len(hw_items)} 个当前作业，最新：{hw_items[0].get_text(strip=True)}",
                            timeout=8
                        )

            if not has_current_hw:
                print(f"✅ 当前无作业：{course_name}")

            # ======= 历史作业展示 =======
            history_hw_headers = homework_soup.select("h5 span strong")
            for h in history_hw_headers:
                if "历史作业" in h.get_text():
                    history_hw_div = h.find_parent("h5").find_next_sibling("div")
                    if history_hw_div:
                        print(f"📜 课程《{course_name}》历史作业：")
                        for a in history_hw_div.find_all("a"):
                            title = a.get_text(strip=True)
                            href = a['href']
                            link = f"{BASE_URL}/{href}" if not href.startswith("http") else href
                            print(f"    - {title} 链接：{link}")
    else:
        print("登录失败，意料外的错误")

def main():
    print("欢迎使用希冀在线作业提醒小助手！")

    credentials = load_credentials()
    stid = credentials['stid'] if credentials else input("请输入学号：")
    pwd = credentials['pwd'] if credentials else input("请输入密码：")

    if not credentials:
        save_credentials(stid, pwd)

    while True:
        print(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} 正在检查作业 ===")
        try:
            check_homework(stid, pwd)
        except Exception as e:
            print(f"检查失败：{e}")
        print("等待两分钟后再次检查...\n")
        time.sleep(120)

if __name__ == "__main__":
    main()
