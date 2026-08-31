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
        print("⚠️ Chưa cấu hình TELEGRAM_TOKEN hoặc TELEGRAM_CHAT_ID.")
        return

    # 1. Gửi tin nhắn văn bản
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
        print("📲 Đã gửi báo cáo văn bản Telegram thành công.")
    except Exception as e:
        print(f"❌ Lỗi gửi Telegram message: {e}")

    # 2. Gửi ảnh đính kèm nếu có lỗi
    if photo_path and os.path.exists(photo_path):
        try:
            url_photo = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            f = open(photo_path, 'rb')
            requests.post(url_photo, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': '📌 Ảnh chụp lỗi:'}, files={'photo': f}, timeout=15)
            f.close()
            print("📸 Đã gửi ảnh screenshot lỗi qua Telegram.")
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
            
            # Lấy toàn bộ input trên form
            inputs = driver.find_elements(By.XPATH, "//form//input[not(@type='hidden')]")
            visible_inputs = [i for i in inputs if i.is_displayed()]
            print(f"📊 Tìm thấy {len(visible_inputs)} ô nhập hiển thị thực tế trên màn hình.")

            if len(visible_inputs) >= 6:
                print("🧩 Thực hiện phân bổ từng chữ số OTP vào 6 ô tương ứng...")
                for idx in range(6):
                    target_input = visible_inputs[idx]
                    digit = otp_code[idx]
                    
                    driver.execute_script("arguments[0].focus();", target_input)
                    target_input.click()
                    target_input.clear()
                    
                    target_input.send_keys(digit)
                    
                    driver.execute_script("""
                        var el = arguments[0];
                        var val = arguments[1];
                        el.value = val;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        el.dispatchEvent(new KeyboardEvent('keydown', { key: val, bubbles: true }));
                        el.dispatchEvent(new KeyboardEvent('keyup', { key: val, bubbles: true }));
                    """, target_input, digit)
                    time.sleep(0.2)
                
                time.sleep(1)
                print("🖱️ Gửi form xác nhận OTP...")
                
                try:
                    form = driver.find_element(By.TAG_NAME, "form")
                    driver.execute_script("arguments[0].submit();", form)
                    print("✅ Đã submit Form OTP bằng Javascript.")
                except Exception as submit_err:
                    print(f"⚠️ Không submit được form, bấm Enter từ ô cuối: {submit_err}")
                    visible_inputs[5].send_keys(Keys.ENTER)

            elif len(visible_inputs) == 1:
                print("📝 Điền thẳng vào 1 ô nhập OTP dạng liền...")
                visible_inputs[0].clear()
                visible_inputs[0].send_keys(otp_code)
                visible_inputs[0].send_keys(Keys.ENTER)
            else:
                driver.save_screenshot("no_inputs_found.png")
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
            print("📸 Đã gửi ảnh screenshot lỗi qua Telegram.")
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
            
            # Lấy toàn bộ input trên form
            inputs = driver.find_elements(By.XPATH, "//form//input[not(@type='hidden')]")
            visible_inputs = [i for i in inputs if i.is_displayed()]
            print(f"📊 Tìm thấy {len(visible_inputs)} ô nhập hiển thị thực tế trên màn hình.")

            if len(visible_inputs) >= 6:
                print("🧩 Thực hiện phân bổ từng chữ số OTP vào 6 ô tương ứng...")
                for idx in range(6):
                    target_input = visible_inputs[idx]
                    digit = otp_code[idx]
                    
                    # Click và xóa sạch
                    driver.execute_script("arguments[0].focus();", target_input)
                    target_input.click()
                    target_input.clear()
                    
                    # Gửi phím thực sự
                    target_input.send_keys(digit)
                    
                    # Phát tín hiệu event mô phỏng người dùng gõ phím chuẩn JS
                    driver.execute_script("""
                        var el = arguments[0];
                        var val = arguments[1];
                        el.value = val;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        el.dispatchEvent(new KeyboardEvent('keydown', { key: val, bubbles: true }));
                        el.dispatchEvent(new KeyboardEvent('keyup', { key: val, bubbles: true }));
                    """, target_input, digit)
                    time.sleep(0.2)
                
                time.sleep(1)
                print("🖱️ Gửi form xác nhận OTP...")
                
                # Ưu tiên submit form trực tiếp thay vì click nhầm button ẩn
                try:
                    form = driver.find_element(By.TAG_NAME, "form")
                    driver.execute_script("arguments[0].submit();", form)
                    print("✅ Đã submit Form OTP bằng Javascript.")
                except Exception as submit_err:
                    print(f"⚠️ Không submit được form, bấm Enter từ ô cuối: {submit_err}")
                    visible_inputs[5].send_keys(Keys.ENTER)

            elif len(visible_inputs) == 1:
                print("📝 Điền thẳng vào 1 ô nhập OTP dạng liền...")
                visible_inputs[0].clear()
                visible_inputs[0].send_keys(otp_code)
                visible_inputs[0].send_keys(Keys.ENTER)
            else:
                driver.save_screenshot("no_inputs_found.png")
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
            print("📸 Đã gửi ảnh screenshot lỗi qua Telegram.")
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
        if "2fa/verify" in current_url or "2fa" in current_url:
            if not NOIP_2FA_SECRET:
                driver.save_screenshot("2fa_error.png")
                raise Exception("Phát hiện trang đòi mã xác minh nhưng thiếu NOIP_2FA_SECRET!")
                
            print("🔐 Đang tự động tính toán mã số OTP từ Secret Key...")
            clean_secret = NOIP_2FA_SECRET.replace(" ", "").strip()
            totp = pyotp.TOTP(clean_secret)
            otp_code = str(totp.now())
            print(f"🔑 Mã OTP khởi tạo thành công: {otp_code}")
            
            all_inputs = driver.find_elements(By.XPATH, "//form//input[@type='text' or @type='number' or @type='tel' or not(@type)]")
            visible_inputs = [inp for inp in all_inputs if inp.is_displayed()]
            
            print(f"📊 Tìm thấy {len(visible_inputs)} ô nhập hiển thị thực tế trên màn hình.")

            if len(visible_inputs) > 0:
                print("🧩 Nhập nguyên chuỗi OTP vào ô đầu tiên để JS tự nhảy ô...")
                first_input = visible_inputs[0]
                first_input.click()
                
                # Cách 1: Gõ liên tục 6 số vào ô đầu tiên
                for digit in otp_code:
                    first_input.send_keys(digit)
                    time.sleep(0.1)
                
                time.sleep(1)
                
                print("🖱️ Đang bấm nút Submit/Verify...")
                submit_success = False
                
                # Thử tìm các nút Submit khả thi
                buttons = driver.find_elements(By.XPATH, "//button | //input[@type='submit']")
                for btn in buttons:
                    if btn.is_displayed():
                        try:
                            driver.execute_script("arguments[0].click();", btn)
                            submit_success = True
                            print("✅ Đã click nút Submit/Verify bằng JS.")
                            break
                        except:
                            pass
                
                if not submit_success:
                    print("⚠️ Không tìm thấy nút Verify, gửi phím ENTER...")
                    first_input.send_keys(Keys.ENTER)
            else:
                driver.save_screenshot("no_inputs_found.png")
                raise Exception("Không tìm thấy ô nhập mã OTP nào hiển thị trên trang!")
            
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
 
