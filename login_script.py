# 文件名: login_script.py
# 作用: 自动登录 ClawCloud Run + 2FA 验证 + Telegram 通知 (带用户名)

import os
import time
import requests  # 确保安装了 requests
import pyotp
from playwright.sync_api import sync_playwright

def send_telegram_notify(token, chat_id, photo_path, message):
    """
    发送带有图片的 Telegram 通知
    """
    if not token or not chat_id:
        print("⚠️ 未配置 Telegram 变量，跳过通知。")
        return

    print("📨 [Step 7] 正在发送 Telegram 通知...")
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    
    try:
        if os.path.exists(photo_path):
            with open(photo_path, 'rb') as img_file:
                payload = {'chat_id': chat_id, 'caption': message}
                files = {'photo': img_file}
                response = requests.post(url, data=payload, files=files)
                if response.status_code == 200:
                    print("✅ Telegram 通知发送成功！")
                else:
                    print(f"❌ 发送失败: {response.text}")
        else:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                          data={'chat_id': chat_id, 'text': message + " (无截图)"})

    except Exception as e:
        print(f"❌ 发送通知异常: {e}")

def run_login():
    # 1. 获取环境变量
    username = os.environ.get("GH_USERNAME")
    password = os.environ.get("GH_PASSWORD")
    totp_secret = os.environ.get("GH_2FA_SECRET")
    
    tg_bot_token = os.environ.get("TG_BOT_TOKEN")
    tg_chat_id = os.environ.get("TG_CHAT_ID")

    if not username or not password:
        print("❌ 错误: 必须设置 GH_USERNAME 和 GH_PASSWORD 环境变量。")
        return

    print("🚀 [Step 1] 启动浏览器...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        # 2. 访问 ClawCloud 登录页
        target_url = "https://ap-northeast-1.run.claw.cloud/"
        print(f"🌐 [Step 2] 正在访问: {target_url}")
        try:
            page.goto(target_url, timeout=60000)
            page.wait_for_load_state("networkidle")
        except Exception as e:
             print(f"⚠️ 访问页面超时或出错: {e}")

        # 3. 点击 GitHub 登录按钮
        print("🔍 [Step 3] 寻找 GitHub 按钮...")
        try:
            login_button = page.locator("button:has-text('GitHub')")
            login_button.wait_for(state="visible", timeout=10000)
            login_button.click()
            print("✅ 按钮已点击")
        except Exception as e:
            print(f"⚠️ 未找到 GitHub 按钮 (可能已自动登录): {e}")

        # 4. 处理 GitHub 登录表单
        print("⏳ [Step 4] 等待跳转到 GitHub...")
        try:
            page.wait_for_url(lambda url: "github.com" in url, timeout=15000)
            if "login" in page.url:
                print("🔒 输入账号密码...")
                page.fill("#login_field", username)
                page.fill("#password", password)
                page.click("input[name='commit']")
                print("📤 登录表单已提交")
        except Exception as e:
            print(f"ℹ️ 跳过账号密码填写: {e}")

        # 5. 处理 2FA
        page.wait_for_timeout(3000)
        if "two-factor" in page.url or page.locator("#app_totp").count() > 0:
            print("🔐 [Step 5] 检测到 2FA 请求...")
            if totp_secret:
                try:
                    totp = pyotp.TOTP(totp_secret)
                    token = totp.now()
                    page.fill("#app_totp", token)
                    print(f"✅ 验证码已填入: {token}")
                except Exception as e:
                    print(f"❌ 填入验证码失败: {e}")
            else:
                print("❌ 致命错误: 未配置 GH_2FA_SECRET")
                exit(1)

        # 6. Authorize App
        page.wait_for_timeout(3000)
        if "authorize" in page.url.lower():
            print("⚠️ 检测到授权请求，点击 Authorize...")
            try:
                page.click("button:has-text('Authorize')", timeout=5000)
            except:
                pass

        # 7. 等待结果并截图
        print("⏳ [Step 6] 等待跳转回 ClawCloud 控制台...")
        page.wait_for_timeout(20000)
        
        final_url = page.url
        print(f"📍 最终页面 URL: {final_url}")
        
        screenshot_path = "login_result.png"
        page.screenshot(path=screenshot_path)
        print(f"📸 已保存结果截图: {screenshot_path}")

        # 8. 验证是否成功
        is_success = False
        if page.get_by_text("App Launchpad").count() > 0 or page.get_by_text("Devbox").count() > 0:
            is_success = True
        elif "private-team" in final_url or "console" in final_url:
            is_success = True
        elif "signin" not in final_url and "github.com" not in final_url:
            is_success = True

        if is_success:
            print("🎉🎉🎉 登录成功！")
            # --- 这里只修改了通知内容，增加了 username ---
            send_telegram_notify(
                token=tg_bot_token,
                chat_id=tg_chat_id,
                photo_path=screenshot_path,
                message=f"✅ ClawCloud 自动登录成功\n👤 账号: {username}\n📅 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            print("😭😭😭 登录失败。")
            # 如果失败也要通知，取消下面这行注释即可
            # send_telegram_notify(tg_bot_token, tg_chat_id, screenshot_path, f"❌ 登录失败: {username}")
            exit(1)

        browser.close()

if __name__ == "__main__":
    run_login()
