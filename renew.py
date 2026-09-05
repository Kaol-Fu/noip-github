import os
import time
import requests
import pyotp
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- LẤY BIẾN MÔI TRƯỜNG ---
USERNAME = os.environ['NOIP_USERNAME']
PASSWORD = os.environ['NOIP_PASSWORD']
NOIP_2FA_SECRET = os.environ.get('NOIP_2FA_SECRET', '').replace(" ", "").strip()
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram(msg, photo=None):
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID): return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        if photo and os.path.exists(photo):
            with open(photo, 'rb') as f:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", data={'chat_id': TELEGRAM_CHAT_ID}, files={'photo': f}, timeout=15)
    except Exception as e:
        print(f"Lỗi Telegram: {e}")

def enter_otp_and_submit(driver, otp_code):
    inputs = [i for i in driver.find_elements(By.TAG_NAME, "input") if i.is_displayed()]
    
    if len(inputs) >= 6:
        print(f"🧩 Đang điền mã OTP: {otp_code}...")
        for i in range(6):
            digit = otp_code[i]
            inp = inputs[i]
            driver.execute_script("""
                var el = arguments[0];
                var val = arguments[1];
                var valueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                valueSetter.call(el, val);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new KeyboardEvent('keydown', { key: val, bubbles: true }));
                el.dispatchEvent(new KeyboardEvent('keyup', { key: val, bubbles: true }));
            """, inp, digit)
            time.sleep(0.15)
        
        time.sleep(1)
        try:
            btn = driver.find_element(By.XPATH, "//button[@type='submit' or contains(text(), 'Verify') or contains(text(), 'Submit')]")
            driver.execute_script("arguments[0].click();", btn)
        except Exception:
            inputs[5].send_keys(Keys.ENTER)

    elif len(inputs) == 1:
        print(f"📝 Đang điền mã OTP vào 1 ô: {otp_code}...")
        driver.execute_script("""
            var el = arguments[0];
            var val = arguments[1];
            var valueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            valueSetter.call(el, val);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        """, inputs[0], otp_code)
        inputs[0].send_keys(Keys.ENTER)

def renew():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=options)

    try:
        # 1. ĐĂNG NHẬP USERNAME / PASSWORD
        print("Mở trang đăng nhập No-IP...")
        driver.get("https://www.noip.com/login")
        time.sleep(4)

        driver.find_element(By.NAME, "username").send_keys(USERNAME)
        p_field = driver.find_element(By.NAME, "password")
        p_field.send_keys(PASSWORD)
        p_field.send_keys(Keys.ENTER)
        time.sleep(6)

        # 2. XỬ LÝ 2FA (ĐIỀN 1 LẦN DUY NHẤT)
        current_url = driver.current_url.lower()
        if "2fa" in current_url or "verify" in current_url:
            print("🔐 Phát hiện trang xác minh 2FA. Đang tạo mã OTP...")
            totp = pyotp.TOTP(NOIP_2FA_SECRET)
            otp_code = totp.now()
            
            enter_otp_and_submit(driver, otp_code)
            print("⏳ Đã điền OTP. Đang chờ hệ thống xác thực và cấp Session Token (15s)...")
            time.sleep(15)

        # 3. ĐIỀU HƯỚNG TỚI DYNAMIC DNS DASHBOARD
        print("🚀 Đang truy cập trang Dynamic DNS...")
        driver.get("https://my.noip.com/dynamic-dns")
        time.sleep(10)

        current_url = driver.current_url.lower()
        print(f"📍 URL hiện tại: {driver.current_url}")

        # Kiểm tra chuẩn: Chỉ coi là thất bại nếu bị đẩy về hẳn trang login gốc của www.noip.com
        if "www.noip.com/login" in current_url:
            raise Exception("Hệ thống từ chối xác thực và đẩy về trang Đăng nhập chính!")

        # 4. THỰC HIỆN GIA HẠN HOST
        print("Đang kiểm tra danh sách Host...")
        time.sleep(3)
        buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Confirm')]")
        
        if buttons:
            count = 0
            for b in buttons:
                driver.execute_script("arguments[0].click();", b)
                count += 1
                time.sleep(2)
            msg = f"🎉 Đã gia hạn thành công {count} tên miền trên No-IP!"
        else:
            msg = "✅ Đăng nhập thành công! Hiện tại không có tên miền nào cần gia hạn."

        print(msg)
        send_telegram(msg)

    except Exception as e:
        err = f"❌ Lỗi Bot Gia Hạn: {e}"
        print(err)
        driver.save_screenshot("error.png")
        send_telegram(err, "error.png")
        raise e
    finally:
        driver.quit()

if __name__ == "__main__":
    renew()
