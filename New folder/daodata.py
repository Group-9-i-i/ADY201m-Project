import time
import json
import requests
import sys
import os
import csv
import threading
import hashlib
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ================= CẤU HÌNH QUÉT =================
SCAN_START_LAT = 15.81
SCAN_END_LAT = 16.76

SCAN_START_LON =  74.98
SCAN_END_LON = 76.33

SCAN_STEP = 0.001 
MAX_WORKERS = 40

# Tiền tố tên file
BASE_FILENAME = "Bagalkote_Data"

# --- LOCKS ---
file_lock = threading.Lock()
print_lock = threading.Lock()
global_processed_count = 0
global_found_count = 0

# Bộ nhớ đệm cấu trúc
structure_map = {} 

# --- TỐI ƯU KẾT NỐI (SESSION POOLING) ---
thread_local = threading.local()

def get_session():
    if not hasattr(thread_local, "session"):
        thread_local.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries, pool_connections=100, pool_maxsize=100)
        thread_local.session.mount("https://", adapter)
        thread_local.session.mount("http://", adapter)
    return thread_local.session

def init_driver():
    """Hàm khởi tạo driver"""
    options = webdriver.ChromeOptions()
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    # options.add_argument("--headless=new") 
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def navigate_to_target(driver, wait):
    """Điều hướng đến trang đích"""
    print("   -> Loading Web...")
    driver.get("https://soilhealth.dac.gov.in/slusi-visualisation/")
    driver.maximize_window()
    time.sleep(5) 
    
    print("   -> Chon State: KARNATAKA...")
    state_open = wait.until(EC.element_to_be_clickable((By.XPATH, "//label[text()='State']/following-sibling::div//button[@title='Open']")))
    driver.execute_script("arguments[0].click();", state_open)
    wait.until(EC.element_to_be_clickable((By.XPATH, "//li[contains(text(), 'KARNATAKA')]"))).click()
    time.sleep(2)

    print("   -> Chon District: BAGALKOTE...")
    dist_open = wait.until(EC.element_to_be_clickable((By.XPATH, "//label[text()='District']/following-sibling::div//button[@title='Open']")))
    driver.execute_script("arguments[0].click();", dist_open)
    wait.until(EC.element_to_be_clickable((By.XPATH, "//li[contains(text(), 'BAGALKOTE')]"))).click()
    time.sleep(2)

def get_all_available_cycles():
    """Lấy danh sách tất cả các năm (Đã sửa lỗi XPath)"""
    print("\n--- GIAI DOAN 0: LAY DANH SACH NAM (CYCLES) ---")
    cycles = []
    driver = init_driver()
    try:
        wait = WebDriverWait(driver, 30)
        navigate_to_target(driver, wait)
        
        print("   -> Dang lay danh sach Cycle...")
        
        # --- FIX XPATH: Tìm label rồi tìm div combobox bên cạnh ---
        try:
            # Cách 1: Tìm theo Label 'Select Cycle'
            cycle_trigger = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//label[contains(text(), 'Select Cycle')]/following-sibling::div//div[@role='combobox']")
            ))
        except:
            # Cách 2: Tìm trực tiếp div combobox (dự phòng)
            cycle_trigger = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//div[@role='combobox' and contains(@class, 'MuiSelect-select')]")
            ))

        driver.execute_script("arguments[0].click();", cycle_trigger)
        
        # Đợi list hiện ra (quan trọng)
        wait.until(EC.presence_of_element_located((By.XPATH, "//li[@role='option']")))
        time.sleep(1) 
        
        options = driver.find_elements(By.XPATH, "//li[@role='option']")
        for opt in options:
            txt = opt.text.strip()
            if txt:
                cycles.append(txt)
        
        print(f"   -> Tim thay {len(cycles)} cycle: {cycles}")
        
    except Exception as e:
        print(f"Loi khi lay danh sach Cycle: {e}")
    finally:
        driver.quit()
    return cycles

def get_session_info_for_cycle(target_cycle):
    """Lấy thông tin phiên làm việc cho một năm cụ thể"""
    print(f"\n--- KHOI DONG SESSION CHO NAM: {target_cycle} ---")
    driver = init_driver()
    final_base_url = None
    final_layer_id = None
    cookies = {}
    user_agent = ""

    try:
        wait = WebDriverWait(driver, 40)
        navigate_to_target(driver, wait)

        print(f"   -> Chon Cycle: {target_cycle}...")
        
        # --- FIX XPATH TƯƠNG TỰ ---
        cycle_trigger = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//label[contains(text(), 'Select Cycle')]/following-sibling::div//div[@role='combobox']")
        ))
        driver.execute_script("arguments[0].click();", cycle_trigger)
        
        # Chọn năm
        year_option_xpath = f"//li[@role='option' and contains(text(), '{target_cycle}')]"
        year_item = wait.until(EC.element_to_be_clickable((By.XPATH, year_option_xpath)))
        year_item.click()
        time.sleep(3)

        print("   -> Kich hoat Nitrogen de bat link...")
        try:
            nitro_btn = driver.find_element(By.XPATH, "//span[text()='Nitrogen']/preceding-sibling::span/input[@type='radio']")
            driver.execute_script("arguments[0].scrollIntoView(true);", nitro_btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", nitro_btn)
            print("   -> Doi 5s lay link mang...")
            time.sleep(5)
        except Exception as e:
            print(f"Warning click Nitrogen: {e}")

        logs = driver.get_log('performance')
        for entry in logs:
            log_json = json.loads(entry['message'])
            message = log_json['message']
            if message['method'] == 'Network.requestWillBeSent':
                request_url = message['params']['request']['url']
                if "wms" in request_url and "GetMap" in request_url and "shc" in request_url and "boundary" not in request_url:
                    parsed = urlparse(request_url)
                    params = parse_qs(parsed.query)
                    final_base_url = request_url.split('?')[0]
                    if 'layers' in params:
                        final_layer_id = params['layers'][0]
                    break
        
        user_agent = driver.execute_script("return navigator.userAgent;")
        selenium_cookies = driver.get_cookies()
        for c in selenium_cookies:
            cookies[c['name']] = c['value']
            
    except Exception as e:
        print(f"Loi Selenium ({target_cycle}): {e}")
    finally:
        driver.quit()
        
    return final_base_url, final_layer_id, cookies, user_agent

def get_target_filename(data_dict):
    global structure_map
    keys = sorted(list(data_dict.keys()))
    structure_str = ",".join(keys)
    structure_hash = hashlib.md5(structure_str.encode('utf-8')).hexdigest()[:8]
    target_filename = f"{BASE_FILENAME}_{structure_hash}.csv"
    
    with print_lock:
        if structure_hash not in structure_map:
            structure_map[structure_hash] = target_filename
            print(f"\n[NEW SCHEMA] File moi: {target_filename}")
            
    return target_filename

def save_row_dynamic(data_dict):
    filename = get_target_filename(data_dict)
    with file_lock:
        file_exists = os.path.isfile(filename)
        with open(filename, mode='a', newline='', encoding='utf-8') as f:
            fieldnames = sorted(list(data_dict.keys()))
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            if not file_exists:
                writer.writeheader()
            writer.writerow(data_dict)

def process_grid_cell(lat, lon, base_endpoint, layer_id, cookies, user_agent, current_cycle):
    global global_found_count, global_processed_count
    
    half_size = 0.01 
    bbox = f"{lon - half_size:.6f},{lat - half_size:.6f},{lon + half_size:.6f},{lat + half_size:.6f}"
    
    # --- CƠ CHẾ TĂNG TỐC (SMART PROBING) ---
    # Kiểm tra tâm và 4 góc trước.
    priority_points = [(50, 50), (10, 10), (90, 90), (10, 90), (90, 10)]
    secondary_points = []
    
    for x in range(10, 100, 20):
        for y in range(10, 100, 20):
            if (x, y) not in priority_points:
                secondary_points.append((x, y))
    
    # List điểm cần check
    tap_points = priority_points + secondary_points

    headers = {
        "User-Agent": user_agent,
        "Referer": "https://soilhealth.dac.gov.in/",
        "Host": "soilhealth.dac.gov.in"
    }

    found_in_this_cell = False
    empty_streak = 0 
    EARLY_EXIT_THRESHOLD = 3 # Nếu 3 điểm đầu tiên (quan trọng nhất) rỗng -> SKIP LUÔN Ô NÀY

    session = get_session() 

    for (px, py) in tap_points:
        if found_in_this_cell: break 
        
        # NẾU 3 điểm đầu tiên check mà ko có gì -> Bỏ qua ô này luôn (Tăng tốc cực mạnh)
        if empty_streak >= EARLY_EXIT_THRESHOLD:
            break

        query_params = {
            "service": "WMS", "version": "1.1.1", "request": "GetFeatureInfo",
            "format": "image/png", "transparent": "true",
            "layers": layer_id, "query_layers": layer_id, "srs": "EPSG:4326",
            "width": "101", "height": "101", 
            "X": str(px), "Y": str(py), 
            "info_format": "application/json",
            "bbox": bbox,
            "feature_count": "50", 
            "HIDE_GEOMETRY": "true"
        }

        try:
            resp = session.get(base_endpoint, params=query_params, headers=headers, cookies=cookies, timeout=5)
            
            has_data = False
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if "features" in data and len(data["features"]) > 0:
                        items_saved = 0
                        for feature in data["features"]:
                            props = feature["properties"]
                            check_val = str(props.get('N', '')) + str(props.get('P', ''))
                            if check_val and check_val.lower() not in ["none", "null", ""]:
                                props['Scan_Lat'] = lat
                                props['Scan_Lon'] = lon
                                props['Feature_ID'] = feature.get('id', '')
                                props['Cycle'] = current_cycle 

                                save_row_dynamic(props)
                                items_saved += 1
                                has_data = True
                        
                        if items_saved > 0:
                            with print_lock:
                                global_found_count += items_saved
                                v_name = data["features"][0]["properties"].get("village", "Unknown")
                                print(f"\n[HIT!] {current_cycle} | {lat:.3f}, {lon:.3f} | {v_name} | +{items_saved}")
                            found_in_this_cell = True 
                except:
                    pass
            
            if not has_data:
                empty_streak += 1
            else:
                empty_streak = 0 # Reset nếu tìm thấy
                
        except Exception:
            empty_streak += 1

    with print_lock:
        global_processed_count += 1
        if global_processed_count % 50 == 0:
            sys.stdout.write(f"\r-> [{current_cycle}] Tien do: {global_processed_count} o | Data: {global_found_count}...")
            sys.stdout.flush()

def main_controller():
    all_cycles = get_all_available_cycles()
    
    if not all_cycles:
        print("KHONG TIM THAY NAM NAO. Kiem tra lai Web.")
        return

    for cycle in all_cycles:
        print("\n" + "="*60)
        print(f"BAT DAU QUET DU LIEU NAM: {cycle}")
        print("="*60)
        
        global global_processed_count
        global_processed_count = 0
        
        base_url, layer_id, cookies, user_agent = get_session_info_for_cycle(cycle)
        
        if not base_url or not layer_id:
            print(f"!!! SKIP {cycle}: Khong lay duoc Layer ID/URL.")
            continue
            
        tasks = []
        lat = SCAN_START_LAT
        while lat <= SCAN_END_LAT:
            lon = SCAN_START_LON
            while lon <= SCAN_END_LON:
                tasks.append((lat, lon))
                lon += SCAN_STEP
            lat += SCAN_STEP
            
        print(f" -> Bat dau chay {len(tasks)} requests cho nam {cycle}...")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(process_grid_cell, lat, lon, base_url, layer_id, cookies, user_agent, cycle) 
                for (lat, lon) in tasks
            ]
            for future in as_completed(futures):
                pass
        
        print(f"\n -> HOAN THANH NAM {cycle}.\n")
        time.sleep(2)

    print("\n\n=== TAT CA DA HOAN THANH ===")

if __name__ == "__main__":
    main_controller()