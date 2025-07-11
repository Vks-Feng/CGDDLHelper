import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from plyer import notification
import json
import time
import pytesseract
import cv2
import numpy as np
import os
import platform
from playsound import playsound

# --- 基本配置 ---
BASE_URL = "https://cslabcg.whu.edu.cn"
LOGIN_URL = f"{BASE_URL}/login/loginproc.jsp"
CAPTCHA_URL = f"{BASE_URL}/cgjiaoyan"
CONFIG_FILE = 'config.json'
KNOWN_HOMEWORK_FILE = 'known_homework.json'
CHECK_INTERVAL_SECONDS = 30
FAILURE_THRESHOLD = 3  # 连续失败3次后要求手动
ALERT_SOUND_FILE = 'alert.wav'
SLOW_CHECK_INTERVAL = 60 * 5 # 慢登录状态下的检查间隔（5分钟）
ERROR_CHECK_INTERVAL = 30 # 登录失败下重试间隔（半分钟）
FAST_RETRY_INTERVAL = 3  # 快登录状态下的重试间隔
FAILURE_THRESHOLD = 6    # 两种模式下的失败阈值

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})


# --- 配置管理模块 (无需修改) ---
def get_config():
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

    if 'stid' not in config or 'pwd' not in config:
        print("首次运行或配置不完整，请输入您的凭据。")
        config['stid'] = input("请输入学号：")
        config['pwd'] = input("请输入密码：")

    if platform.system() == "Windows":
        tesseract_path = config.get('tesseract_path')
        if not tesseract_path or not os.path.isfile(tesseract_path):
            print("\n未找到有效的Tesseract-OCR路径配置。")
            print("请提供Tesseract的安装路径，例如：C:\\Program Files\\Tesseract-OCR\\tesseract.exe")
            while True:
                path_input = input("请输入tesseract.exe的完整路径: ")
                if os.path.isfile(path_input) and path_input.endswith('tesseract.exe'):
                    config['tesseract_path'] = path_input
                    break
                else:
                    print("路径无效或不是tesseract.exe文件，请重新输入。")
        pytesseract.pytesseract.tesseract_cmd = config['tesseract_path']

    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

    print(f"配置加载成功。学号: {config['stid']}")
    if 'tesseract_path' in config:
        print(f"Tesseract路径: {config['tesseract_path']}")
    return config


# --- 作业状态管理 (无需修改) ---
def load_known_homework():
    if not os.path.exists(KNOWN_HOMEWORK_FILE): return set()
    try:
        with open(KNOWN_HOMEWORK_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    except (json.JSONDecodeError, FileNotFoundError):
        return set()


def save_known_homework(known_homework_set):
    with open(KNOWN_HOMEWORK_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(known_homework_set), f, ensure_ascii=False, indent=4)


# --- 验证码识别模块 (无需修改) ---
def solve_captcha(force_manual=False):
    print("正在获取验证码...")
    try:
        response = session.get(CAPTCHA_URL)
        response.raise_for_status()
        img_bytes = response.content
        image = Image.open(BytesIO(img_bytes))

        if force_manual:
            print("OCR长时间失败，需要您手动干预！")
            image.show()
            return input("请手动输入5位验证码：")

        img_np = np.array(image.convert('RGB'))
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        binary = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)

        char_whitelist = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        custom_config = f'--oem 3 --psm 8 -c tessedit_char_whitelist={char_whitelist}'

        code = pytesseract.image_to_string(binary, config=custom_config).strip()

        print(f"OCR识别结果: '{code}'")
        if len(code) == 5 and code.isalnum():
            return code
        else:
            print("OCR识别失败或结果格式不符，本轮跳过。")
            return None

    except Exception as e:
        print(f"处理验证码时出错: {e}")
        return None


# --- 核心逻辑 (登录部分无需修改) ---
def login(config, force_manual=False):
    captcha_code = solve_captcha(force_manual)

    if captcha_code is None:
        return None

    login_data = {"stid": config['stid'], "pwd": config['pwd'], "captchaCode": captcha_code}

    try:
        response = session.post(LOGIN_URL, data=login_data)
        response.raise_for_status()

        if "用户名或者密码错误！" in response.text:
            print("登录失败：用户名或密码错误！")
            return None
        elif "验证码错误！" in response.text:
            print("登录失败：验证码错误！")
            return None
        elif "选择课程" in response.text:
            print("登录成功！")
            return response
        else:
            print("登录失败：未知错误。")
            return None
    except requests.exceptions.RequestException as e:
        print(f"登录请求失败: {e}")
        return None


# --- 作业检查逻辑 (已复用您的关键逻辑) ---
# --- 作业检查逻辑 (增加“显示历史”功能) ---
def check_for_new_homework(login_response, known_homework_set, show_history=False):
    print("开始解析课程列表并检查作业...")
    new_homework_found = []

    soup = BeautifulSoup(login_response.text, 'html.parser')

    course_divs = soup.select('.media')
    if not course_divs:
        print("错误：登录成功但未在页面中找到任何课程。")
        return new_homework_found

    for media_div in course_divs:
        course_name = media_div.select_one('strong a').text.strip()

        try:
            course_link = f"{BASE_URL}/{media_div.select_one('strong a')['href']}"
            session.get(course_link)
            session.get(f"{BASE_URL}/main.jsp")
            hw_page_res = session.get(f"{BASE_URL}/includes/redirect.jsp?tab=-2")
            hw_page_res.raise_for_status()

            homework_soup = BeautifulSoup(hw_page_res.text, 'html.parser')

            # --- 1. 检查当前作业 (逻辑不变) ---
            current_hw_div = homework_soup.select_one("div.list-group-flush.mb-4")
            if not current_hw_div:
                print(f"✅ 课程《{course_name}》当前无作业。")
            else:
                hw_items = current_hw_div.select("a.list-group-item")
                print(f"🔍 正在检查课程《{course_name}》，发现 {len(hw_items)} 个当前作业...")
                for item in hw_items:
                    title = item.get_text(strip=True)
                    homework_id = f"{course_name}::{title}"
                    href = item['href']
                    link = f"{BASE_URL}/{href}" if not href.startswith("http") else href
                    print(f"  当前作业  - {title} 链接：{link}")
                    if homework_id not in known_homework_set:
                        print(f"🚨 发现新作业! 🚨\n  - 课程: {course_name}\n  - 作业: {title}")
                        notification.notify(title=f"【新作业】{course_name}", message=f"任务：{title}", timeout=180)
                        new_homework_found.append(homework_id)

            # --- 2. 仅在首次运行时展示历史作业 ---
            if show_history:
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

        except Exception as e:
            print(f"检查课程《{course_name}》时出错: {e}")

    if show_history:
        print("\n" + "=" * 25 + " 首次历史作业展示完毕 " + "=" * 25 + "\n")

    return new_homework_found


# --- 主循环 (全新的状态机逻辑) ---
def main():
    print("--- 希冀平台在线作业提醒脚本 (状态机版) ---")
    try:
        config = get_config()
    except Exception as e:
        print(f"初始化配置失败: {e}"); return

    known_homework = load_known_homework()
    print(f"已加载 {len(known_homework)} 个已知作业。")

    # --- 状态变量初始化 ---
    is_in_fast_mode = True
    is_initial_history_shown = False
    fast_mode_attempts = 0
    slow_mode_failures = 0

    print("\n>>> 进入【快登录状态】，将进行最多3次快速尝试...")
    while True:
        try:
            print(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

            # 第一次登录逻辑
            if is_in_fast_mode:
                # --- 快登录状态逻辑 ---
                login_response = login(config)
                if login_response:  # 快速登录成功
                    is_in_fast_mode = False  # 永久退出快登录模式
                    print(">>> 快速登录成功！退出【快登录状态】，进入【慢登录状态】。")
                    new_items = check_for_new_homework(login_response, known_homework,
                                                       show_history=not is_initial_history_shown)
                    is_initial_history_shown = True  # 标记历史已显示
                    if new_items:
                        known_homework.update(new_items); save_known_homework(known_homework)
                    else:
                        print("本次检查未发现新作业。")
                    time.sleep(SLOW_CHECK_INTERVAL)
                else:  # 快速登录失败
                    fast_mode_attempts += 1
                    if fast_mode_attempts < FAILURE_THRESHOLD:
                        print(f"快速登录失败第 {fast_mode_attempts} 次，等待 {FAST_RETRY_INTERVAL} 秒后重试...")
                        time.sleep(FAST_RETRY_INTERVAL)
                    else:  # 3次快速失败，强制手动
                        is_in_fast_mode = False  # 永久退出快登录模式
                        print("\n" + "=" * 50);
                        print(f"!! 快登录状态连续失败 {fast_mode_attempts} 次，需要手动干预！");
                        print("=" * 50 + "\n")
                        if os.path.exists(ALERT_SOUND_FILE):
                            try:
                                playsound(ALERT_SOUND_FILE)
                            except Exception as e:
                                print(f"播放警报声失败: {e}")

                        manual_response = login(config, force_manual=True)  # 进行一次手动登录
                        print(">>> 退出【快登录状态】，进入【慢登录状态】。")
                        if manual_response:
                            new_items = check_for_new_homework(manual_response, known_homework,
                                                               show_history=not is_initial_history_shown)
                            is_initial_history_shown = True
                            if new_items: known_homework.update(new_items); save_known_homework(known_homework)
                        time.sleep(SLOW_CHECK_INTERVAL)

            # --- 第一次登录之后 ---
            else:
                # --- 慢登录状态逻辑 ---
                force_manual = False
                if slow_mode_failures >= FAILURE_THRESHOLD:
                    print("\n" + "=" * 50);
                    print(f"!! 慢登录状态连续失败 {slow_mode_failures} 次，需要手动干预！");
                    print("=" * 50 + "\n")
                    if os.path.exists(ALERT_SOUND_FILE):
                        try:
                            playsound(ALERT_SOUND_FILE)
                        except Exception as e:
                            print(f"播放警报声失败: {e}")
                    force_manual = True
                    slow_mode_failures = 0  # 提醒后重置计数器，给用户新的3次机会

                login_response = login(config, force_manual=force_manual)
                if login_response:
                    slow_mode_failures = 0  # 成功后重置计数器
                    new_items = check_for_new_homework(login_response, known_homework,
                                                       show_history=not is_initial_history_shown)
                    is_initial_history_shown = True
                    if new_items:
                        known_homework.update(new_items); save_known_homework(known_homework)
                    else:
                        print("本次检查未发现新作业。")
                        print(f"--- 等待 {SLOW_CHECK_INTERVAL} 秒后进行下一次检查 ---")
                        time.sleep(SLOW_CHECK_INTERVAL)
                else:
                    slow_mode_failures += 1  # 失败后增加计数器
                    print(f"慢登录状态失败，累计失败次数: {slow_mode_failures}")
                    print(f"--- 等待 {ERROR_CHECK_INTERVAL} 秒后进行下一次检查 ---")
                    time.sleep(ERROR_CHECK_INTERVAL)


        except Exception as e:
            print(f"主循环中发生未预料的错误: {e}")
            print(f"--- 系统异常，等待 {ERROR_CHECK_INTERVAL} 秒后重试 ---")
            time.sleep(ERROR_CHECK_INTERVAL)


if __name__ == "__main__":
    main()