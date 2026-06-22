from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import pandas as pd
import time

# Khởi tạo trình duyệt
driver = webdriver.Chrome()
driver.get("https://soilhealth.dac.gov.in/nutrient-dashboard") # Ví dụ URL dashboard

time.sleep(5) # Đợi trang tải

try:
    # 1. Tìm và chọn Bang (Karnataka)
    state_dropdown = Select(driver.find_element(By.ID, "state_id_dropdown")) # ID này bạn phải F12 để tìm thực tế
    state_dropdown.select_by_visible_text("Karnataka")
    time.sleep(2)

    # 2. Lặp qua từng Huyện (District)
    district_dropdown = Select(driver.find_element(By.ID, "district_id_dropdown"))
    
    for district in district_dropdown.options:
        if district.text == "Select District": continue
        
        print(f"Đang cào dữ liệu huyện: {district.text}")
        district.click()
        time.sleep(3) # Đợi bảng dữ liệu hiện ra
        
        # 3. Lấy dữ liệu từ bảng (Table)
        html = driver.page_source
        # Dùng Pandas để đọc bảng HTML nhanh
        dfs = pd.read_html(html)
        
        if dfs:
            df_soil = dfs[0] # Lấy bảng đầu tiên tìm thấy
            df_soil['District'] = district.text # Thêm cột tên huyện
            # Lưu file CSV riêng từng huyện hoặc gộp lại
            df_soil.to_csv(f"karnataka_{district.text}.csv", index=False)

except Exception as e:
    print(f"Lỗi: {e}")

finally:
    driver.quit()