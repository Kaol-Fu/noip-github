import os
import time
import requests
import pyotp
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
USERNAME = os.environ['NOIP_USERNAME']
PASSWORD = os.environ['NOIP_PASSWORD']
NOIP_2FA_SECRET = os.environ.get('NOIP_2FA_SECRET') 
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram(message, photo_path=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=10
        )
        print("📲 Đã gửi tin nhắn Telegram thành công.")
    except Exception as e:
        print(f"❌ Lỗi Telegram msg: {e}")

    if photo_path and os.path.exists(photo_path):
        try:
            with open(photo_path, 'rb') as f:
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                    data={'chat_id': TELEGRAM_CHAT_ID, 'caption': '📌 Ảnh lỗi:'},
                    files={'photo': f},
                    timeout=15
                )
            print("📸 Đã gửi ảnh lỗi qua Telegram.")
        except Exception as e:
            print(f"❌ Lỗi gửi ảnh Telegram: {e}")

def renew():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,1024")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

    print("🤖 Khởi tạo Trình duyệt Selenium...")
    driver = webdriver.Chrome(options=options)

    try:
        print("Opening No-IP Login Page...")
        driver.get("https://www.noip.com/login")
        wait = WebDriverWait(driver, 20)

        print("Filling login form...")
        username_field = wait.until(EC.element_to_be_clickable((By.NAME, "username")))
        username_field.clear()
        username_field.send_keys(USERNAME)
        print("🎯 Đã điền xong Username")
        
        password_field = wait.until(EC.element_to_be_clickable((By.NAME, "password")))
        password_field.clear()
        password_field.send_keys(PASSWORD)
        print("🎯 Đã điền xong Password")
        
        print("Submitting login form via Enter key...")
        password_field.send_keys(Keys.ENTER)
        
        time.sleep(10)
        current_url = driver.current_url.lower()
        print(f"📍 URL hiện tại: {driver.current_url}")
        
        # XỬ LÝ KHU VỰC XÁC THỰC 2FA / OTP
        if "2fa" in current_url or "verify" in current_url:
            if not NOIP_2FA_SECRET:
                driver.save_screenshot("2fa_error.png")
                raise Exception("Phát hiện trang đòi mã xác minh nhưng thiếu NOIP_2FA_SECRET!")

            clean_secret = NOIP_2FA_SECRET.replace(" ", "").strip()
            totp = pyotp.TOTP(clean_secret)
            
            # Tính toán OTP bù trừ sai số thời gian (Epoch offset)
            current_time = time.time()
            otp_code = totp.at(current_time)
            print(f"🔑 Mã OTP tính toán thành công: {otp_code}")

            inputs = driver.find_elements(By.XPATH, "//input[@type='text' or @type='number' or @type='tel' or not(@type)]")
            visible_inputs = [i for i in inputs if i.is_displayed()]
            print(f"📊 Tìm thấy {len(visible_inputs)} ô nhập hiển thị.")

            if len(visible_inputs) >= 6:
                print("🧩 Nhập OTP bằng ActionChains mô phỏng gõ phím thực...")
                first_input = visible_inputs[0]
                first_input.click()
                time.sleep(0.5)

                # Gõ từng số qua ActionChains để kích hoạt đầy đủ Event JS
                actions = ActionChains(driver)
                for digit in otp_code:
                    actions.send_keys(digit)
                    actions.pause(0.15)
                actions.perform()

                time.sleep(1.5)
                
                # Thử tìm nút Submit/Verify nếu form chưa tự động submit
                try:
                    submit_btn = driver.find_element(By.XPATH, "//button[@type='submit' or contains(text(),'Verify') or contains(text(),'Submit')]")
                    if submit_btn.is_displayed():
                        driver.execute_script("arguments[0].click();", submit_btn)
                        print("🖱️ Đã click nút Verify.")
                except Exception:
                    print("⚠️ Nút Verify không xuất hiện hoặc form đã tự submit.")

            elif len(visible_inputs) == 1:
                print("📝 Điền OTP vào 1 ô duy nhất...")
                visible_inputs[0].clear()
                visible_inputs[0].send_keys(otp_code)
                visible_inputs[0].send_keys(Keys.ENTER)
            else:
                driver.save_screenshot("no_inputs_found.png")
                raise Exception("Không tìm thấy ô nhập mã OTP phù hợp.")

            print("⏳ Đang chờ xác minh cấp quyền...")
            time.sleep(12)

        print("Navigating to Dynamic DNS Dashboard...")
        driver.get("https://my.noip.com/dynamic-dns")
        time.sleep(8)

        if "login" in driver.current_url.lower():
            driver.save_screenshot("dashboard_failed.png")
            raise Exception("Bị đá về trang đăng nhập! Mã OTP bị hệ thống từ chối.")

        print("Checking for hosts to renew...")
        confirm_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Confirm')]")
        
        if len(confirm_buttons) > 0:
            count = 0
            for btn in confirm_buttons:
                btn.click()
                count += 1
                time.sleep(2)
            success_msg = f"🎉 Success! Gia hạn thành công {count} tên miền trên No-IP."
            print(success_msg)
            send_telegram(success_msg) 
        else:
            info_msg = "✅ [NO-IP CHECK] Đăng nhập thành công. Không có tên miền nào cần bấm gia hạn hôm nay."
            print(info_msg)
            send_telegram(info_msg)
            
    except Exception as e:
        error_msg = f"⚠️ [NO-IP FAILED] Bot Thất Bại!\nLỗi: {str(e)}"
        print(error_msg)
        driver.save_screenshot("error.png")
        send_telegram(error_msg, photo_path="error.png")
        raise e
    finally:
        driver.quit()

if __name__ == "__main__":
    renew()
 
