import time
import json
import requests
import sys
import os
import csv
import threading
import hashlib
import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ================= CẤU HÌNH TỐI ƯU =================
SCAN_START_LAT = 15.81
SCAN_END_LAT = 16.76

SCAN_START_LON =  74.98
SCAN_END_LON = 76.33

SCAN_STEP = 0.002 
MAX_WORKERS = 150 
BASE_FILENAME = "Bagalkote_Data"

# --- BIẾN TOÀN CỤC ---
TARGET_CYCLE = "" # Sẽ được cập nhật khi người dùng chọn từ menu

# --- LOCKS & GLOBALS ---
file_lock = threading.Lock()
print_lock = threading.Lock()
global_processed_count = 0
global_found_count = 0
global_start_time = 0   
global_total_tasks = 0   

structure_map = {} 

# --- TẠO SESSION TOÀN CỤC ---
def create_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS, max_retries=retries)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session

def get_session_info():
    """Lấy Link WMS, Cookies, User-Agent (Chế độ chọn năm tương tác)"""
    global TARGET_CYCLE
    
    print("\n--- GIAI DOAN 1: KHOI DONG TRINH DUYET ---")
    options = webdriver.ChromeOptions()
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    # --- LƯU Ý: Tắt headless để bạn thấy menu chọn ---
    # options.add_argument("--headless=new") 
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    final_base_url = None
    final_layer_id = None
    cookies = {}
    user_agent = ""

    try:
        driver.get("https://soilhealth.dac.gov.in/slusi-visualisation/")
        driver.maximize_window()
        wait = WebDriverWait(driver, 30)
        
        print("1. Loading Web...")
        try:
            wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "MuiBackdrop-root")))
        except:
            pass
        time.sleep(3)
        
        # --- CHỌN STATE ---
        print("2. Chon State: KARNATAKA...")
        state_open = wait.until(EC.element_to_be_clickable((By.XPATH, "//label[text()='State']/following-sibling::div//button[@title='Open']")))
        driver.execute_script("arguments[0].click();", state_open)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//li[contains(text(), 'KARNATAKA')]"))).click()
        time.sleep(1)

        # --- CHỌN DISTRICT ---
        print("3. Chon District: BAGALKOTE...")
        dist_open = wait.until(EC.element_to_be_clickable((By.XPATH, "//label[text()='District']/following-sibling::div//button[@title='Open']")))
        driver.execute_script("arguments[0].click();", dist_open)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//li[contains(text(), 'BAGALKOTE')]"))).click()
        time.sleep(2)

        # --- CHỌN CYCLE (TƯƠNG TÁC NGƯỜI DÙNG) ---
        print("3.5. Dang doc danh sach Cycle...")
        try:
            # 1. Click mở menu
            cycle_trigger = wait.until(EC.element_to_be_clickable((
                By.XPATH, 
                "//label[text()='Select Cycle']/following-sibling::div//div[@role='combobox' or @role='button']"
            )))
            cycle_trigger.click()
            time.sleep(1) # Đợi menu sổ xuống
            
            # 2. Lấy danh sách các năm
            options_elements = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//ul[@role='listbox']//li")))
            
            available_cycles = [opt.text for opt in options_elements if opt.text.strip() != ""]
            
            if not available_cycles:
                raise Exception("Khong tim thay nam nao trong danh sach!")

            # 3. HIỂN THỊ MENU CHO NGƯỜI DÙNG CHỌN
            print("\n" + "="*40)
            print("DANH SACH NAM HIEN CO TREN WEB:")
            for idx, cyc in enumerate(available_cycles):
                print(f"  [{idx + 1}] {cyc}")
            print("="*40)
            
            # 4. Yêu cầu người dùng nhập số
            while True:
                try:
                    user_input = input(f"Nhap so thu tu nam muon chon (1-{len(available_cycles)}): ")
                    choice_idx = int(user_input) - 1
                    if 0 <= choice_idx < len(available_cycles):
                        TARGET_CYCLE = available_cycles[choice_idx]
                        print(f"\n---> BAN DA CHON: {TARGET_CYCLE}")
                        break
                    else:
                        print("So khong hop le, vui long nhap lai!")
                except ValueError:
                    print("Vui long nhap so!")

            # 5. Click vào năm đã chọn
            # Tìm lại element dựa trên text đã chọn để click chính xác
            xpath_choice = f"//ul[@role='listbox']//li[text()='{TARGET_CYCLE}']"
            driver.find_element(By.XPATH, xpath_choice).click()
            
            time.sleep(5) # Đợi web load dữ liệu năm mới

        except Exception as e:
            print(f"Lỗi quá trình chọn Cycle: {e}")
            return None, None, None, None

        # --- CHỌN NITROGEN ---
        print("4. Kich hoat Nitrogen...")
        try:
            # Click vào chữ Nitrogen
            nitro_label = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Nitrogen')]")))
            driver.execute_script("arguments[0].scrollIntoView(true);", nitro_label)
            time.sleep(1)
            nitro_label.click()
            print("   -> Da click Nitrogen")
            
            print("   -> Doi 8s lay link...")
            time.sleep(8)
        except Exception as e:
            print(f"Loi Click Nitrogen: {e}")

        # --- QUÉT LOG ---
        print("5. Quet Log mang...")
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
                        print(f"   -> LAY DUOC LAYER ID: {final_layer_id}")
                    break
        
        user_agent = driver.execute_script("return navigator.userAgent;")
        selenium_cookies = driver.get_cookies()
        for c in selenium_cookies:
            cookies[c['name']] = c['value']
            
    except Exception as e:
        print(f"Loi Selenium Tong Quat: {e}")
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

def process_grid_cell(lat, lon, base_endpoint, layer_id, cookies, user_agent, session):
    global global_found_count, global_processed_count
    
    half_size = SCAN_STEP / 2.0 
    bbox = f"{lon - half_size:.6f},{lat - half_size:.6f},{lon + half_size:.6f},{lat + half_size:.6f}"
    
    tap_points = []
    for x in range(20, 100, 20): 
        for y in range(20, 100, 20):
            tap_points.append((x, y))

    headers = {
        "User-Agent": user_agent,
        "Referer": "https://soilhealth.dac.gov.in/",
        "Host": "soilhealth.dac.gov.in",
        "Connection": "keep-alive"
    }

    found_in_this_cell = False

    for (px, py) in tap_points:
        if found_in_this_cell: break 

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
            resp = session.get(base_endpoint, params=query_params, headers=headers, cookies=cookies, timeout=3)
            
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
                                props['Cycle_Year'] = TARGET_CYCLE 
                                props['Feature_ID'] = feature.get('id', '')
                                save_row_dynamic(props)
                                items_saved += 1
                        
                        if items_saved > 0:
                            with print_lock:
                                global_found_count += items_saved
                                v_name = data["features"][0]["properties"].get("village", "VILLAGE")
                                sys.stdout.write(f"\n[HIT!] {lat:.3f},{lon:.3f} | {v_name} | +{items_saved}\n")
                            found_in_this_cell = True 
                except:
                    pass
        except Exception:
            pass

    with print_lock:
        global_processed_count += 1
        if global_processed_count % 20 == 0 or found_in_this_cell:
            current_time = time.time()
            elapsed_time = current_time - global_start_time
            speed = global_processed_count / elapsed_time if elapsed_time > 0 else 0
            
            remaining_items = global_total_tasks - global_processed_count
            eta_seconds = remaining_items / speed if speed > 0 else 0
            
            elapsed_str = str(datetime.timedelta(seconds=int(elapsed_time)))
            eta_str = str(datetime.timedelta(seconds=int(eta_seconds)))
            percent = (global_processed_count / global_total_tasks) * 100
            
            status_line = (
                f"\rProgress: {global_processed_count}/{global_total_tasks} ({percent:.2f}%) | "
                f"Hits: {global_found_count} | "
                f"Time: {elapsed_str} | ETA: {eta_str} | Speed: {speed:.1f} req/s   "
            )
            sys.stdout.write(status_line)
            sys.stdout.flush()

def run_scan():
    global global_total_tasks, global_start_time
    
    base_url, layer_id, cookies, user_agent = get_session_info()
    
    if not base_url:
        print("\n!!! THAT BAI: Khong lay duoc link hoac ban da tat trinh duyet qua som.")
        return
    
    session = create_session()

    print(f"\n--- GIAI DOAN 2: QUET PHAN LOAI FILE ({MAX_WORKERS} Workers) ---")
    print(f"Cycle duoc chon: {TARGET_CYCLE}")
    
    tasks = []
    lat = SCAN_START_LAT
    while lat <= SCAN_END_LAT:
        lon = SCAN_START_LON
        while lon <= SCAN_END_LON:
            tasks.append((lat, lon))
            lon += SCAN_STEP
        lat += SCAN_STEP
    
    global_total_tasks = len(tasks)
    global_start_time = time.time()
    
    print(f"Tong so request: {global_total_tasks} (Moi request quet 16 diem)")
    print("-" * 80)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(process_grid_cell, lat, lon, base_url, layer_id, cookies, user_agent, session) 
            for (lat, lon) in tasks
        ]
        for future in as_completed(futures):
            pass

    print(f"\n\n--- HOAN THANH ---")
    total_time = str(datetime.timedelta(seconds=int(time.time() - global_start_time)))
    print(f"Tong thoi gian chay: {total_time}")
    session.close()

if __name__ == "__main__":
    run_scan()