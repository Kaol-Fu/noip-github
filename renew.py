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
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Chưa cấu hình TELEGRAM_TOKEN hoặc TELEGRAM_CHAT_ID trong Secrets.")
        return

    # Gửi tin nhắn văn bản
    text_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        res = requests.post(text_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
        if res.status_code == 200:
            print("📲 Đã gửi báo cáo Telegram thành công.")
    except Exception as e:
        print(f"❌ Lỗi kết nối Telegram: {e}")

    # Gửi ảnh màn hình nếu gặp lỗi
    if photo_path and os.path.exists(photo_path):
        photo_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        try:
            with open(photo_path, 'rb') as photo:
                files = {'photo': photo}
                data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': "📌 Ảnh màn hình tại thời điểm văng lỗi:"}
                requests.post(photo_url, data=data, files=files, timeout=15)
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
        if "2fa/verify" in current_url:
            if not NOIP_2FA_SECRET:
                driver.save_screenshot("2fa_error.png")
                raise Exception("Phát hiện trang đòi mã xác minh nhưng thiếu NOIP_2FA_SECRET!")
                
            print("🔐 Đang tự động tính toán mã số OTP từ Secret Key...")
            clean_secret = NOIP_2FA_SECRET.replace(" ", "").strip()
            totp = pyotp.TOTP(clean_secret)
            otp_code = str(totp.now())
            print(f"🔑 Mã OTP khởi tạo thành công: {otp_code}")
            
            all_inputs = driver.find_elements(By.XPATH, "//form//input[@type='text' or @type='number' or not(@type)]")
            visible_inputs = [inp for inp in all_inputs if inp.is_displayed()]
            
            print(f"📊 Tìm thấy {len(visible_inputs)} ô nhập hiển thị thực tế trên màn hình.")

            if len(visible_inputs) >= 6:
                print("🧩 Điền OTP kết hợp JS Event ép hệ thống ghi nhận...")
                for i in range(6):
                    try:
                        inp = visible_inputs[i]
                        inp.click()
                        inp.clear()
                        inp.send_keys(otp_code[i])
                        # Kích hoạt JS Event bắt buộc của framework UI
                        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", inp)
                        driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", inp)
                        time.sleep(0.1)
                    except Exception as input_err:
                        print(f"⚠️ Lỗi ô thứ {i+1}: {input_err}")
                
                print("🖱️ Tìm và click nút Verify bằng JS...")
                time.sleep(1)
                try:
                    verify_btn = driver.find_element(By.XPATH, "//button[@type='submit' or contains(text(), 'Verify') or @value='Verify']")
                    driver.execute_script("arguments[0].click();", verify_btn)
                except Exception as btn_err:
                    print(f"⚠️ Không click được nút bằng JS, gửi phím Enter từ ô 6: {btn_err}")
                    visible_inputs[5].send_keys(Keys.ENTER)
            else:
                print("📝 Điền thẳng vào ô nhập OTP 2FA dạng liền...")
                try:
                    otp_field = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@id='mfa-code' or @name='code' or contains(@class, 'form-control')]")))
                    otp_field.clear()
                    otp_field.send_keys(otp_code)
                    otp_field.send_keys(Keys.ENTER)
                except Exception as e:
                    driver.save_screenshot("otp_field_error.png")
                    raise Exception("Không tìm thấy cấu hình ô nhập mã OTP phù hợp.")
            
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
                files = {'photo': photo}
                data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': "📌 Ảnh màn hình tại thời điểm văng lỗi:"}
                requests.post(photo_url, data=data, files=files, timeout=15)
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

    print("🤖 Khởi tạo Trình duyệt Selenium tiêu chuẩn (Tự động khớp ChromeDriver)...")
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
        if "2fa/verify" in current_url:
            if not NOIP_2FA_SECRET:
                driver.save_screenshot("2fa_error.png")
                raise Exception("Phát hiện trang đòi mã xác minh nhưng thiếu NOIP_2FA_SECRET!")
                
            print("🔐 Đang tự động tính toán mã số OTP từ Secret Key...")
            clean_secret = NOIP_2FA_SECRET.replace(" ", "").strip()
            totp = pyotp.TOTP(clean_secret)
            otp_code = str(totp.now())
            print(f"🔑 Mã OTP khởi tạo thành công: {otp_code}")
            
            # Lấy danh sách ô nhập thực tế hiển thị
            all_inputs = driver.find_elements(By.XPATH, "//form//input[@type='text' or @type='number' or not(@type)]")
            visible_inputs = [inp for inp in all_inputs if inp.is_displayed()]
            
            print(f"📊 Tìm thấy {len(visible_inputs)} ô nhập hiển thị thực tế trên màn hình.")

            if len(visible_inputs) >= 6:
                print("🧩 Tiến hành rải chính xác 6 ký tự OTP vào các ô số rời...")
                for i in range(6):
                    try:
                        visible_inputs[i].clear()
                        visible_inputs[i].send_keys(otp_code[i])
                        time.sleep(0.2)
                    except Exception as input_err:
                        print(f"⚠️ Lỗi ô thứ {i+1}: {input_err}")
                
                print("⏳ Chờ 1 giây để hệ thống tự nhận diện chuỗi OTP...")
                time.sleep(1)
                
                print("🖱️ Gửi phím Enter từ ô số cuối cùng để xác thực...")
                try:
                    visible_inputs[5].send_keys(Keys.ENTER)
                except:
                    verify_btn = driver.find_element(By.XPATH, "//*[contains(text(), 'Verify') or @value='Verify']")
                    verify_btn.click()
            else:
                print("📝 Điền thẳng vào ô nhập OTP 2FA dạng liền...")
                try:
                    otp_field = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@id='mfa-code' or @name='code' or contains(@class, 'form-control')]")))
                    otp_field.clear()
                    otp_field.send_keys(otp_code)
                    otp_field.send_keys(Keys.ENTER)
                except Exception as e:
                    driver.save_screenshot("otp_field_error.png")
                    raise Exception("Không tìm thấy cấu hình ô nhập mã OTP phù hợp.")
            
            print("⏳ Đang đợi hệ thống duyệt quyền truy cập (20s)...")
            time.sleep(20)

        print("Navigating to Dynamic DNS Dashboard...")
        driver.get("https://my.noip.com/dynamic-dns")
        time.sleep(8)

        if "login" in driver.current_url:
            driver.save_screenshot("dashboard_failed.png")
            raise Exception("Bị đá về trang đăng nhập! Phiên làm việc không được chấp nhận.")

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
