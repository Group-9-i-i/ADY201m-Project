----- 1.Xem data co ba nhieu ban ghi 
SELECT COUNT(*) AS total_rows
FROM Data; 
--- Nhan xet : Co 4178 ban ghi sau khi clean , moi ban ghi tuong trung cho 1 ruong

----- 2.Xem cac loai cay trong bangladesh va so ban ghi cua chung 
SELECT [Crop Name],COUNT([Crop Name]) AS numbers
FROM Data
group by [Crop Name]
Order by COUNT([Crop Name]) desc  ;
-----Nhan xet chung ta thay du lieu kha can bang giua cac loai cay , nhung cay Arhar, Tobacco, cheena se co ban ghi thap hon so voi cac loai cay khac
---- goi y nen tang so luong ban ghi bang cac phuong phap tang cuong du lieu de model hoc tot hon

------ So luong ban ghi season
SELECT 
    Season,
    COUNT(*) AS samples
FROM DATA
GROUP BY Season;
-----Mua rabi co so luong 1188 ban ghi so voi kharif2 va kharif1 la 1569 va 1421 hoi mat can bang nhe  

------Lọc các điều kiện nhiệt độ và lượng mưa 
SELECT Yield, [Crop Name]
FROM DATA
WHERE [Avg Temp] BETWEEN 20 AND 35
  AND rainfall > 100

------Lọc các điều kiện theo mùa 
SELECT Yield,[Crop Name]
FROM DATA
WHERE season = 'Kharif 1'
   
------Phan tich seson anh huong den yeild nhu nao 
SELECT 
    Season,
    AVG(Yield) AS avg_yield,
    MIN(Yield) AS min_yield,
    MAX(Yield) AS max_yield
FROM data
GROUP BY Season;
-----Ta nhan xet : Qua phân tích theo mùa vụ, có thể thấy năng suất cây trồng thay đổi đáng kể giữa các mùa. Cụ thể, mùa Kharif 1 có năng suất trung bình cao nhất (~5.87) 
-----và cũng ghi nhận giá trị cực đại lớn nhất (~98.99), cho thấy đây là mùa có điều kiện tự nhiên thuận lợi nhất cho sự phát triển của cây trồng.
-------Trong khi đó, mùa Rabi có năng suất trung bình thấp nhất (~2.96), phản ánh điều kiện kém thuận lợi hơn. Mùa Kharif 2 nằm ở mức trung gian. 
------Ngoài ra, sự xuất hiện của các giá trị năng suất cực lớn, đặc biệt trong mùa Kharif 1, cho thấy dữ liệu có thể bị lệch (skew) và tồn tại outlier, cần được xử lý trong giai đoạn tiền xử lý dữ liệu trước khi xây dựng mô hình.

---- 3.Xem cac huyen trong bangladesh va so ban ghi cua chung
SELECT District, COUNT(District) as  numbers
FROM Data
group by District
Order by COUNT(District) desc;
---- Dataset co 64 huyen va ta thay so luong ban ghi kha la can bang giua cac huyen 

-----4. Xem phan bo cua du lieu target (Yeild)
SELECT 
    MIN(Yield) AS min_yield,
    MAX(Yield) AS max_yield,
    AVG(Yield) AS avg_yield,
    STDEV(Yield) AS std_yield
FROM Data;
---- Dữ liệu phân bố khá skew khi std  khoang 5.77 goi y nen co nhung phuong phap de giam skew co the gay ra model hoc lech

-----5.Năng xuất trung bình theo huyện
SELECT 
    District,
    AVG(Yield) AS avg_yield
FROM Data
GROUP BY District
ORDER BY avg_yield DESC;
----Nhan xet Huyen Kushtia co nang xuat 6.49 co nang xuat trung binh cao nhat ,trong do Barguna co nang xuat thap nhat = 1.616 

-----6.Xem quan he giua luong mua va nang xuat
SELECT 
    ROUND(Rainfall,0) AS rainfall,
    AVG(Yield) AS avg_yield
FROM Data
GROUP BY ROUND(Rainfall,0)
ORDER BY rainfall;
---- ta thấy quan hệ không phải mưa lúc nào tăng thì lượng  mưa tăng thì không có nghĩa là năng xuất cũng tăng 
---- Vì ở ngoài đời tưới mưa nhiều quá cũng không tăng năng xuất

-----7.Xem quan he giua nhiet do va nang xuat
SELECT 
    ROUND([Avg Temp],1) AS avg_temp,
    AVG(Yield) AS avg_yield
FROM Data
GROUP BY ROUND([Avg Temp],1)
ORDER BY avg_temp;
---- Nhan xet : ở đây ta quan sát được nhiệt độ không ảnh hưởng nhiều đến năng xuất nhưng ta thấy từ 29 độ thấy năng xuất tăng khá cao 

-----8. Xem quan he giua do am va nang xuat
SELECT 
    ROUND([Avg Humidity],1) AS humidity,
    AVG(Yield) AS avg_yield
FROM Data
GROUP BY ROUND([Avg Humidity],1)
ORDER BY humidity;

-----9.Xem quan he giua so luong ngay nong va nang xuat 
SELECT 
    AVG(Heat_Stress_Days) AS heat_days,
    AVG(Yield) AS avg_yield
FROM data
GROUP BY Heat_Stress_Days
ORDER BY heat_days;
---- Ta nhân tháy heat strest day có mối tương quan tăng 1 chút đối với yeild

-----9. Xem moi quan he giua NDVI va yield
SELECT 
    ROUND(NDVI_Season_Mean,2) AS ndvi,
    AVG(Yield) AS avg_yield
FROM data
GROUP BY ROUND(NDVI_Season_Mean,2)
ORDER BY ndvi;
--- Ta nhận xét Cây phát triển tốt nhất ra nhiều năng xuất khi NDVI ở mức 0.4 đến 0.5

SELECT 
    ROUND(NDVI_Season_Max,2) AS ndvi_max,
    AVG(Yield) AS avg_yield
FROM data
GROUP BY ROUND(NDVI_Season_Max,2)
ORDER BY ndvi_max;
----- Kết quả chúng ta vẫn thấy cây cho nhiều năng xuất nhất là khi có cây trồng ở mwucs NDVI 0.3 đến 0.6


-----Phan tich EVI và nang xuat trung bình
SELECT 
    ROUND(EVI,2) AS evi,
    AVG(Yield) AS avg_yield
FROM data
GROUP BY ROUND(EVI,2)
ORDER BY evi;

----- Phan tich Nitro va nang xuat trung bình 
SELECT 
    ROUND(Nitrogen,1) AS nitrogen,
    AVG(Yield) AS avg_yield
FROM Data
GROUP BY ROUND(Nitrogen,1)
ORDER BY nitrogen;

SELECT 
    ROUND(Organic_Carbon,2) AS carbon,
    AVG(Yield) AS avg_yield
FROM data
GROUP BY ROUND(Organic_Carbon,2)
ORDER BY carbon;


SELECT 
    ROUND(Soil_Moisture_mm,0) AS soil_moisture,
    AVG(Yield) AS avg_yield
FROM data
GROUP BY ROUND(Soil_Moisture_mm,0)
ORDER BY soil_moisture;


-----Xem mua va crop cung anh huong yeild nhu nao 
WITH rainfall_group AS (
    SELECT *,
        CASE 
            WHEN Rainfall < 500 THEN 'Low Rain'
            WHEN Rainfall BETWEEN 500 AND 1000 THEN 'Medium Rain'
            ELSE 'High Rain'
        END AS rain_level
    FROM data
)

SELECT 
    [Crop Name],
    rain_level,
    MIN(Yield) AS min_yield,
    MAX(Yield) AS max_yield
FROM rainfall_group
GROUP BY [Crop Name], rain_level
ORDER BY [Crop Name], rain_level;
--------Yield phụ thuộc mạnh vào rainfall, nhưng mối quan hệ này thay đổi theo từng loại cây trồng, với điều kiện mưa trung bình thường mang lại năng suất tối ưu cho phần lớn crop.
-----✔️ Nhóm ổn định (dễ predict)
-------Ví dụ: Aus, Jhinga
------Yield không thay đổi nhiều theo rainfall
-------⚠️ Nhóm biến động mạnh (khó predict)
------Ví dụ: Date Palm, Green Coconut, Mango
-------Yield thay đổi rất lớn theo rainfall



------Phân tích crop và season ảnh hương như nào đến yeild
SELECT 
    [Crop Name],
    Season,
    AVG(Yield) AS avg_yield
FROM data
GROUP BY [Crop Name], Season
ORDER BY [Crop Name];
-----Kết quả cho thấy phần lớn cây trồng đạt năng suất cao nhất trong mùa Kharif 1 và Kharif 2, trong khi mùa Rabi thường có năng suất thấp hơn. 
-------Một số cây như Jack Fruit, Ripe Papaya và Green Coconut có năng suất vượt trội trong Kharif 1, cho thấy đây là mùa thuận lợi nhất.
---------Điều này chứng tỏ Season là yếu tố quan trọng và cần được kết hợp với loại cây trồng trong mô hình dự đoán.

SELECT District, season, AVG(Yield) AS avg_yield
FROM DATA
GROUP BY District, season

SELECT
    Yield / rainfall AS yield_per_rain
FROM DATA
WHERE rainfall > 0

-------Yeild trung bình theo mùa
SELECT 
    Season,
    AVG(Yield) AS avg_yield
FROM Data
GROUP BY Season;