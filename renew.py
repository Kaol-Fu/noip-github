import os
import time
import requests
import pyotp
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

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
    """Hàm nhập OTP bằng Native Event để React nhận đúng 100%"""
    inputs = [i for i in driver.find_elements(By.TAG_NAME, "input") if i.is_displayed()]
    
    if len(inputs) >= 6:
        print(f"🧩 Đang điền mã OTP: {otp_code} vào 6 ô...")
        for i in range(6):
            digit = otp_code[i]
            inp = inputs[i]
            
            # Ép cập nhật giá trị vào state của React
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
        # Bấm nút Verify hoặc Submit
        try:
            btn = driver.find_element(By.XPATH, "//button[@type='submit' or contains(text(), 'Verify') or contains(text(), 'Submit')]")
            driver.execute_script("arguments[0].click();", btn)
        except Exception:
            inputs[5].send_keys(Keys.ENTER)

    elif len(inputs) == 1:
        print(f"📝 Đang điền mã OTP: {otp_code} vào 1 ô...")
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
        time.sleep(5)

        driver.find_element(By.NAME, "username").send_keys(USERNAME)
        p_field = driver.find_element(By.NAME, "password")
        p_field.send_keys(PASSWORD)
        p_field.send_keys(Keys.ENTER)
        time.sleep(8)

        # 2. XỬ LÝ 2FA VỚI CƠ CHẾ BÙ LỆCH GIỜ VÀ THỬ LẠI (RETRY)
        totp = pyotp.TOTP(NOIP_2FA_SECRET)
        offsets = [0, -30, 30] # Thử giờ chuẩn, chậm 30s, nhanh 30s
        
        for attempt, offset in enumerate(offsets, start=1):
            current_url = driver.current_url.lower()
            if "2fa" not in current_url and "verify" not in current_url:
                print("✅ Đã vượt qua bước 2FA thành công!")
                break

            print(f"🔐 Lần thử 2FA thứ {attempt}/{len(offsets)} (Offset: {offset}s)...")
            
            # Tính OTP theo mốc thời gian lệch bù trừ
            calc_time = time.time() + offset
            otp_code = totp.at(calc_time)
            
            enter_otp_and_submit(driver, otp_code)
            
            print("⏳ Chờ hệ thống xác nhận (12s)...")
            time.sleep(12)

        # 3. KIỂM TRA ĐĂNG NHẬP VÀ CHUYỂN DASHBOARD
        print("Truy cập Dashboard...")
        driver.get("https://my.noip.com/dynamic-dns")
        time.sleep(6)

        if "login" in driver.current_url.lower():
            raise Exception("Tất cả mã OTP thử nghiệm đều bị vô hiệu hoặc sai tài khoản!")

        # 4. THỰC HIỆN GIA HẠN
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
