import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import rasterio
import pandas as pd
import numpy as np
import os
import threading
import time

class NDVIConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Công cụ Chuyển đổi Sentinel-2 TIFF sang CSV")
        self.root.geometry("600x450")
        self.root.resizable(False, False)

        # Biến lưu trữ
        self.file_paths = []
        self.is_processing = False

        # --- GIAO DIỆN (UI) ---
        
        # 1. Khung chọn file
        frame_top = tk.LabelFrame(root, text="1. Chọn dữ liệu đầu vào", padx=10, pady=10)
        frame_top.pack(fill="x", padx=10, pady=5)

        self.btn_select = tk.Button(frame_top, text="Chọn File .tif (Chọn 1 hoặc nhiều)", command=self.select_files, bg="#dddddd")
        self.btn_select.pack(fill="x", pady=5)

        self.lbl_file_count = tk.Label(frame_top, text="Chưa chọn file nào", fg="red")
        self.lbl_file_count.pack()

        # 2. Tùy chọn chuyển đổi
        frame_mid = tk.LabelFrame(root, text="2. Cấu hình chuyển đổi", padx=10, pady=10)
        frame_mid.pack(fill="x", padx=10, pady=5)

        # Checkbox: Chỉ lấy giá trị có dữ liệu (Bỏ qua nền đen/NaN)
        self.var_skip_nodata = tk.BooleanVar(value=True)
        chk_nodata = tk.Checkbutton(frame_mid, text="Bỏ qua điểm ảnh rỗng (NaN/NoData) - Khuyên dùng để giảm dung lượng", variable=self.var_skip_nodata)
        chk_nodata.pack(anchor="w")

        # Checkbox: Làm tròn số liệu
        self.var_round = tk.BooleanVar(value=True)
        chk_round = tk.Checkbutton(frame_mid, text="Làm tròn số liệu (Lat/Lon 5 số, NDVI 4 số)", variable=self.var_round)
        chk_round.pack(anchor="w")

        # 3. Khu vực Tiển trình & Log
        frame_bottom = tk.LabelFrame(root, text="3. Trạng thái xử lý", padx=10, pady=10)
        frame_bottom.pack(fill="both", expand=True, padx=10, pady=5)

        self.btn_convert = tk.Button(frame_bottom, text="BẮT ĐẦU CHUYỂN ĐỔI", command=self.start_conversion_thread, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.btn_convert.pack(fill="x", pady=5)

        self.progress = ttk.Progressbar(frame_bottom, orient="horizontal", length=100, mode="determinate")
        self.progress.pack(fill="x", pady=5)

        self.txt_log = tk.Text(frame_bottom, height=8, state='disabled', font=("Consolas", 9))
        self.txt_log.pack(fill="both", pady=5)

    def log(self, message):
        """Ghi log ra màn hình"""
        self.txt_log.config(state='normal')
        self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state='disabled')

    def select_files(self):
        """Mở hộp thoại chọn nhiều file"""
        files = filedialog.askopenfilenames(
            title="Chọn các file GeoTIFF",
            filetypes=[("GeoTIFF Files", "*.tif"), ("All Files", "*.*")]
        )
        if files:
            self.file_paths = list(files)
            self.lbl_file_count.config(text=f"Đã chọn: {len(self.file_paths)} file", fg="green")
            self.log(f"-> Đã tải danh sách {len(self.file_paths)} file.")
        else:
            self.lbl_file_count.config(text="Chưa chọn file nào", fg="red")

    def start_conversion_thread(self):
        """Chạy xử lý trong luồng riêng để không đơ ứng dụng"""
        if not self.file_paths:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 file .tif!")
            return
        
        if self.is_processing:
            return

        self.is_processing = True
        self.btn_convert.config(state="disabled", text="ĐANG XỬ LÝ...")
        self.btn_select.config(state="disabled")
        
        # Tạo luồng chạy ngầm
        thread = threading.Thread(target=self.process_files)
        thread.start()

    def process_files(self):
        """Logic chính để chuyển đổi"""
        total_files = len(self.file_paths)
        self.progress["maximum"] = total_files
        self.progress["value"] = 0
        
        success_count = 0
        error_count = 0

        for index, file_path in enumerate(self.file_paths):
            filename = os.path.basename(file_path)
            output_csv = file_path.replace(".tif", ".csv")

            self.log(f"[{index+1}/{total_files}] Đang xử lý: {filename}...")
            
            try:
                # --- BẮT ĐẦU XỬ LÝ RASTER ---
                with rasterio.open(file_path) as src:
                    # Đọc dữ liệu band 1 (NDVI)
                    data = src.read(1)
                    
                    # Tạo lưới tọa độ
                    height, width = data.shape
                    cols, rows = np.meshgrid(np.arange(width), np.arange(height))
                    xs, ys = rasterio.transform.xy(src.transform, rows, cols)
                    
                    # Flatten (trải phẳng mảng 2 chiều thành 1 chiều)
                    lons = np.array(xs).flatten()
                    lats = np.array(ys).flatten()
                    values = data.flatten()
                    
                    # Tạo DataFrame
                    df = pd.DataFrame({'Lat': lats, 'Lon': lons, 'NDVI': values})
                    
                    # Lọc dữ liệu rác (nếu user chọn)
                    if self.var_skip_nodata.get():
                        # Lọc bỏ giá trị 0 (thường là viền đen) và NaN
                        df = df[(df['NDVI'] != 0) & (df['NDVI'].notna())]

                    if df.empty:
                        self.log(f"   ! Cảnh báo: File {filename} không có dữ liệu (toàn mây/rỗng). Bỏ qua.")
                        error_count += 1
                    else:
                        # Làm tròn số (nếu user chọn)
                        if self.var_round.get():
                            df['Lat'] = df['Lat'].round(5)
                            df['Lon'] = df['Lon'].round(5)
                            df['NDVI'] = df['NDVI'].round(4)

                        # Lưu CSV
                        df.to_csv(output_csv, index=False)
                        self.log(f"   OK -> Đã lưu: {os.path.basename(output_csv)} ({len(df)} dòng)")
                        success_count += 1

                # --- KẾT THÚC XỬ LÝ RASTER ---

            except Exception as e:
                self.log(f"   X LỖI: {e}")
                error_count += 1

            # Cập nhật thanh tiến trình
            self.progress["value"] = index + 1
            self.root.update_idletasks()

        # Hoàn tất
        self.is_processing = False
        self.btn_convert.config(state="normal", text="BẮT ĐẦU CHUYỂN ĐỔI")
        self.btn_select.config(state="normal")
        self.log(f"\n--- HOÀN TẤT ---\nThành công: {success_count} | Lỗi/Rỗng: {error_count}")
        messagebox.showinfo("Hoàn tất", f"Đã xử lý xong!\nThành công: {success_count}\nFile CSV nằm cùng thư mục với file ảnh gốc.")

if __name__ == "__main__":
    root = tk.Tk()
    app = NDVIConverterApp(root)
    root.mainloop()