SELECT COUNT(*) AS total_rows
FROM Data;
SELECT COUNT(DISTINCT [Crop Name]) AS total_crops
FROM Data;
SELECT COUNT(DISTINCT District) AS total_districts
FROM Data;
--- Dataset balance theo crop
SELECT 
    [Crop Name],
    COUNT(*) AS samples
FROM DATA
GROUP BY [Crop Name]
ORDER BY samples DESC;
SELECT 
    MIN(Yield) AS min_yield,
    MAX(Yield) AS max_yield,
    AVG(Yield) AS avg_yield,
    STDEV(Yield) AS std_yield
FROM Data;
---- Dữ liệu phân bố khá skew
SELECT TOP 10 *
FROM Data
ORDER BY Yield DESC;
----- Năng xuất trung bình theo huyện
SELECT 
    District,
    AVG(Yield) AS avg_yield
FROM Data
GROUP BY District
ORDER BY avg_yield DESC;
SELECT 
    ROUND(Rainfall,0) AS rainfall,
    AVG(Yield) AS avg_yield
FROM Data
GROUP BY ROUND(Rainfall,0)
ORDER BY rainfall;
---- Ta thấy quan hệ không phải mưa lúc nào tăng thì lượng  mưa tăng thì không có nghĩa là năng xuất cũng tăng 
---- Vì ở ngoài đời tưới mưa nhiều quá cũng không tăng năng xuất
SELECT 
    ROUND([Avg Temp],1) AS avg_temp,
    AVG(Yield) AS avg_yield
FROM Data
GROUP BY ROUND([Avg Temp],1)
ORDER BY avg_temp;
---- Ở đây ta quan sát được nhiệt độ không ảnh hưởng nhiều đến năng xuất nhưng ta thấy từ 29 độ thấy năng xuất tăng khá cao 
SELECT 
    ROUND([Avg Humidity],1) AS humidity,
    AVG(Yield) AS avg_yield
FROM Data
GROUP BY ROUND([Avg Humidity],1)
ORDER BY humidity;
----- 
SELECT 
    AVG(Heat_Stress_Days) AS heat_days,
    AVG(Yield) AS avg_yield
FROM data
GROUP BY Heat_Stress_Days
ORDER BY heat_days;
---- Ta nhân tháy heat strest day có mối tương quan tăng 1 chút đối với yeild
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
SELECT 
    ROUND(EVI,2) AS evi,
    AVG(Yield) AS avg_yield
FROM data
GROUP BY ROUND(EVI,2)
ORDER BY evi;
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