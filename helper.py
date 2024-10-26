import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 基本配置
BASE_URL = "https://cslabcg.whu.edu.cn"
LOGIN_URL = f"{BASE_URL}/login/loginproc.jsp"
CAPTCHA_URL = f"{BASE_URL}/cgjiaoyan"
CONFIG_FILE = 'config.json'

def load_credentials():
    """加载凭据（学号和密码）"""
    try:
        with open('credentials.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def load_config():
    """加载配置（发件人邮箱等）"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def save_credentials(stid, pwd):
    """保存凭据（学号和密码）"""
    with open('credentials.json', 'w') as f:
        json.dump({'stid': stid, 'pwd': pwd}, f)

def save_config(sender_email, recipient_email, sender_password):
    """保存配置（发件人和收件人邮箱及密码）"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump({'sender_email': sender_email, 'recipient_email': recipient_email, 'sender_password': sender_password}, f)

def get_captcha(session):
    """获取验证码并显示"""
    response = session.get(CAPTCHA_URL)
    image = Image.open(BytesIO(response.content))
    image.save("captcha.png")  # 保存验证码
    image.show() # 打开验证码，用户手动输入
    return input("请输入验证码：")

def login(session, stid, pwd, captcha_code):
    """登录功能"""
    login_data = {"stid": stid, "pwd": pwd, "captchaCode": captcha_code}
    return session.post(LOGIN_URL, data=login_data)

def check_assignment_completion(url):
    """检查作业是否完成"""
    try:
        response = requests.get(url)
        response.raise_for_status()  # 检查请求是否成功
        # 此处暂时根据有无 “未提交” 判断作业完成情况
        return "未提交" not in response.text  # 作业完成则返回 True
    except requests.RequestException as e:
        print(f"请求出错: {e}")
        return None  # 请求出错

def parse_assignments(soup):
    """解析作业信息并检查是否完成"""
    assignments = []
    active_assignments_div = soup.find('div', id='activeAssignBodyDIV')
    
    if active_assignments_div:
        for link in active_assignments_div.find_all('a'):
            name = link.get_text(strip=True)
            url = BASE_URL + '/' + link['href']
            due_time = link.find_next('span', class_='').get_text(strip=True) if link.find_next('span', class_='') else None
            is_late_submission = '补交' in link.find_next('span', class_='badge').get_text(strip=True)

            is_completed = check_assignment_completion(url)

            # 添加作业信息
            assignments.append({
                'name': name,
                'url': url,
                'due_time': due_time,
                'is_completed': is_completed,
                'is_late_submission': is_late_submission
            })
    return assignments

def send_email(subject, body, to_email, sender_email, sender_password):
    """发送邮件功能"""
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(f"<pre>{body}</pre>", 'html', 'utf-8'))

    try:
        with smtplib.SMTP('smtp.qq.com', 587) as server:
            server.starttls()  # 启动 TLS 加密
            server.login(sender_email, sender_password)  # 使用配置文件中的密码
            server.sendmail(sender_email, to_email, msg.as_string())
        print("邮件发送成功！")
    except Exception as e:
        print(f"邮件发送失败: {e}")

def format_email_body(courses, stid):
    """格式化邮件内容"""
    email_body_lines = [f"以下{stid}是未完成的作业信息：\n"]

    for course_info in courses.values():
        email_body_lines.append(f"科目: {course_info['course_name']}\n未完成作业:")
        
        for assignment in course_info['active_assignments']:
            email_body_lines.append(f"  - 作业名称: {assignment['name']}")
            email_body_lines.append(f"    截止时间: {assignment['due_time']}")
            email_body_lines.append(f"    是否处于补交状态: {'是' if assignment['is_late_submission'] else '否'}\n")
        
        email_body_lines.append("-" * 40)  # 添加分隔线
    
    return "\n".join(email_body_lines)

def main():
    print("欢迎使用希冀ddl小助手！")

    # 加载或输入学号和密码
    credentials = load_credentials()
    stid = credentials['stid'] if credentials else input("请输入学号：")
    pwd = credentials['pwd'] if credentials else input("请输入密码：")
    
    # 加载配置
    config = load_config()
    sender_email = config['sender_email'] if config else input("请输入发件人邮箱：")
    recipient_email = config['recipient_email'] if config else input("请输入收件人邮箱：")
    sender_password = config['sender_password'] if config else input("请输入发件人邮箱的密码：")
    
    save_config(sender_email, recipient_email, sender_password)  # 保存配置
    
    with requests.Session() as session:
        captcha_code = get_captcha(session)
        response = login(session, stid, pwd, captcha_code)

        if "用户名或者密码错误！" in response.text:
            print("用户名或密码错误！")
            return
        elif "验证码错误！" in response.text:
            print("验证码错误！！")
            return
        elif "选择课程" in response.text: #这里是通过响应数据中有无“选择课程”，判断是否登陆成功
            print("登录成功！学号和密码已保存")
            save_credentials(stid, pwd)
            soup = BeautifulSoup(response.text, 'html.parser')
            courses = {}

            for i, media_div in enumerate(soup.select('.media'), start=1):
                course_name = media_div.select_one('strong a').text.strip()
                course_link = f"{BASE_URL}/{media_div.select_one('strong a')['href']}"
                session.get(course_link)
                online_assignments_response = session.get('https://cslabcg.whu.edu.cn/assignment/mainActiveAssigns.jsp')
                assignments = parse_assignments(BeautifulSoup(online_assignments_response.content, 'html.parser'))

                unfinished_assignments = [a for a in assignments if not a['is_completed']]
                if unfinished_assignments:
                    courses[str(i)] = {
                        'course_name': course_name,
                        'course_link': course_link,
                        'active_assignments': unfinished_assignments
                    }

            if courses:
                print("未完成的作业信息：", json.dumps(courses, ensure_ascii=False, indent=2))
                email_body = format_email_body(courses, stid)
                email_subject = "希冀课程未完成作业信息"
                send_email(email_subject, email_body, recipient_email, sender_email, sender_password)
            else:
                print("所有作业均已完成！")
        else:
            print("登陆失败，意料外的错误")


if __name__ == "__main__":
    main()
