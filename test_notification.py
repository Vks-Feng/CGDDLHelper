import time
from plyer import notification
from playsound import playsound
import os

# --- 配置 ---
SOUND_FILE = 'alert.wav'

def test_notification_system():
    """
    一个简单的脚本，用于测试系统的弹窗和声音提醒功能。
    """
    print("--- 通知系统测试 ---")
    print("这个脚本将测试两件事：")
    print("1. 弹窗通知：你的操作系统应该会弹出一个通知。")
    print("2. 声音提醒：你应该能听到一声提示音。")
    print("\n请确保你已经：")
    print("1. 安装了 plyer 和 playsound 库 (pip install plyer playsound==1.2.2)")
    print(f"2. 在此脚本同目录下放置了一个名为 '{SOUND_FILE}' 的声音文件。")
    print("-" * 20)

    # 倒计时，给你准备时间
    for i in range(5, 0, -1):
        print(f"测试将在 {i} 秒后开始...")
        time.sleep(1)

    print("\n正在触发通知...")

    # 1. 测试弹窗通知
    try:
        notification.notify(
            title="【测试】这是一个测试通知",
            message="如果你能看到这条消息，说明弹窗通知功能正常！",
            app_name="Python Notifier", # 一些系统会显示应用名
            timeout=10 # 通知显示10秒
        )
        print("✅ 弹窗通知已发送。请检查你的屏幕角落或通知中心。")
    except Exception as e:
        print(f"❌ 发送弹窗通知失败: {e}")
        print("   请检查plyer库的依赖是否在您的系统上正确安装。")

    time.sleep(1) # 短暂间隔

    # 2. 测试声音提醒
    try:
        if os.path.exists(SOUND_FILE):
            playsound(SOUND_FILE)
            print(f"✅ 声音提醒 '{SOUND_FILE}' 已播放。")
        else:
            print(f"❌ 声音文件 '{SOUND_FILE}' 未找到！无法测试声音提醒。")
    except Exception as e:
        print(f"❌ 播放声音失败: {e}")
        print("   请检查声音文件是否有效，以及你的电脑是否静音。")

    print("\n--- 测试结束 ---")

if __name__ == "__main__":
    test_notification_system()