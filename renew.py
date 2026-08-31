import os
import time
import requests
import pyotp
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
USERNAME = os.environ['NOIP_USERNAME']
PASSWORD = os.environ['NOIP_PASSWORD']
NOIP_2FA_SECRET = os.environ.get('NOIP_2FA_SECRET') 
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram(message, photo_path=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
        print("📲 Đã gửi tin nhắn Telegram thành công.")
    except Exception as e:
        print(f"❌ Lỗi Telegram msg: {e}")

    if photo_path and os.path.exists(photo_path):
        try:
            with open(photo_path, 'rb') as f:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", data={'chat_id': TELEGRAM_CHAT_ID, 'caption': '📌 Ảnh lỗi:'}, files={'photo': f}, timeout=15)
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
    options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    print("🤖 Khởi tạo Trình duyệt Selenium tiêu chuẩn...")
    driver = webdriver.Chrome(options=options)

    try:
        print("Opening No-IP Login Page...")
        driver.get("https://www.noip.com/login")
        
        wait = WebDriverWait(driver, 25)

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
        
        print("⏳ Đang đợi trang bảo mật phản hồi (15s)...")
        time.sleep(15) 

        current_url = driver.current_url.lower()
        print(f"📍 URL hiện tại sau khi đăng nhập: {driver.current_url}")
        
        # XỬ LÝ KHU VỰC XÁC THỰC THIẾT BỊ / 2FA
        if "2fa" in current_url or "verify" in current_url:
            if not NOIP_2FA_SECRET:
                driver.save_screenshot("2fa_error.png")
                raise Exception("Phát hiện trang đòi mã xác minh nhưng thiếu NOIP_2FA_SECRET!")
                
            print("🔐 Đang tự động tính toán mã số OTP từ Secret Key...")
            clean_secret = NOIP_2FA_SECRET.replace(" ", "").strip()
            totp = pyotp.TOTP(clean_secret)
            otp_code = str(totp.now())
            print(f"🔑 Mã OTP khởi tạo thành công: {otp_code}")
            
            # Lấy toàn bộ ô input có thể tương tác
            inputs = driver.find_elements(By.XPATH, "//input[@type='text' or @type='number' or @type='tel' or not(@type)]")
            visible_inputs = [i for i in inputs if i.is_displayed()]
            print(f"📊 Tìm thấy {len(visible_inputs)} ô nhập hiển thị thực tế trên màn hình.")

            if len(visible_inputs) >= 6:
                print("🧩 Phân bổ từng ký tự vào 6 ô bằng Native Setter Event...")
                for idx in range(6):
                    target_input = visible_inputs[idx]
                    digit = otp_code[idx]
                    
                    # Dùng JS Native Setter để buộc React/Vue cập nhật state chính xác
                    driver.execute_script("""
                        var el = arguments[0];
                        var val = arguments[1];
                        var valueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        valueSetter.call(el, val);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    """, target_input, digit)
                    time.sleep(0.1)
                
                time.sleep(1)
                print("🖱️ Nhấp nút Submit...")
                
                try:
                    submit_btn = driver.find_element(By.XPATH, "//button[@type='submit' or contains(text(), 'Verify') or contains(text(), 'Submit') or contains(text(), 'Confirm')]")
                    driver.execute_script("arguments[0].click();", submit_btn)
                except Exception:
                    print("⚠️ Bấm Enter ở ô cuối cùng...")
                    visible_inputs[5].send_keys(Keys.ENTER)

            elif len(visible_inputs) == 1:
                print("📝 Điền vào 1 ô duy nhất...")
                driver.execute_script("""
                    var el = arguments[0];
                    var val = arguments[1];
                    var valueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    valueSetter.call(el, val);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                """, visible_inputs[0], otp_code)
                visible_inputs[0].send_keys(Keys.ENTER)
            else:
                driver.save_screenshot("no_inputs_found.png")
                raise Exception("Không tìm thấy ô nhập mã OTP phù hợp.")
            
            print("⏳ Đang đợi hệ thống duyệt quyền truy cập (15s)...")
            time.sleep(15)

        print("Navigating to Dynamic DNS Dashboard...")
        driver.get("https://my.noip.com/dynamic-dns")
        time.sleep(8)

        if "login" in driver.current_url:
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
            success_msg = f"🎉 Success! Bạn Trung Hiếu đã tự động gia hạn thành công {count} tên miền trên No-IP."
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
 
