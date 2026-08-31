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
NOIP_2FA_SECRET = os.environ.get('NOIP_2FA_SECRET')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram(msg, photo=None):
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID): return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        if photo and os.path.exists(photo):
            with open(photo, 'rb') as f:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", data={'chat_id': TELEGRAM_CHAT_ID}, files={'photo': f})
    except Exception as e:
        print(f"Lỗi Telegram: {e}")

def renew():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)

    try:
        # 1. ĐĂNG NHẬP
        print("Mở trang đăng nhập No-IP...")
        driver.get("https://www.noip.com/login")
        time.sleep(3)

        driver.find_element(By.NAME, "username").send_keys(USERNAME)
        p_field = driver.find_element(By.NAME, "password")
        p_field.send_keys(PASSWORD)
        p_field.send_keys(Keys.ENTER)
        time.sleep(10)

        # 2. XỬ LÝ 2FA (NẾU CÓ)
        if "2fa" in driver.current_url.lower() or "verify" in driver.current_url.lower():
            print("Xử lý xác minh OTP...")
            otp = pyotp.TOTP(NOIP_2FA_SECRET.replace(" ", "")).now()
            print(f"Mã OTP: {otp}")

            # Tìm tất cả các ô nhập trên form
            inputs = [i for i in driver.find_elements(By.TAG_NAME, "input") if i.is_displayed()]

            if len(inputs) >= 6:
                # Nếu giao diện tách 6 ô -> gõ từng số vào từng ô
                for i in range(6):
                    inputs[i].send_keys(otp[i])
                    time.sleep(0.1)
                inputs[5].send_keys(Keys.ENTER)
            elif len(inputs) == 1:
                # Nếu giao diện là 1 ô chung -> gõ cả chuỗi
                inputs[0].send_keys(otp)
                inputs[0].send_keys(Keys.ENTER)

            time.sleep(10)

        # 3. VÀO DASHBOARD GIA HẠN
        print("Truy cập Dashboard...")
        driver.get("https://my.noip.com/dynamic-dns")
        time.sleep(5)

        if "login" in driver.current_url.lower():
            raise Exception("Đăng nhập không thành công! Bị trả về trang Login.")

        buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Confirm')]")
        if buttons:
            for b in buttons:
                b.click()
                time.sleep(2)
            msg = f"🎉 Đã bấm Confirm gia hạn thành công {len(buttons)} host!"
        else:
            msg = "✅ Đăng nhập thành công, hiện không có host nào cần Confirm."

        print(msg)
        send_telegram(msg)

    except Exception as e:
        err = f"❌ Lỗi Bot: {e}"
        print(err)
        driver.save_screenshot("error.png")
        send_telegram(err, "error.png")
        raise e
    finally:
        driver.quit()

if __name__ == "__main__":
    renew()
 
