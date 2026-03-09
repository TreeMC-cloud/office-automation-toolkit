@echo off
chcp 65001 >nul
echo ============================================
echo   一键打包三个桌面应用 (PyInstaller)
echo ============================================
echo.

where pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 未检测到 PyInstaller，正在安装...
    pip install pyinstaller
)

echo.
echo [1/3] 打包 Excel 智能核对助手...
echo ----------------------------------------
cd excel-reconcile-assistant
pyinstaller --noconfirm --onedir --windowed ^
    --name "Excel智能核对助手" ^
    --add-data "sample_data;sample_data" ^
    --add-data "services;services" ^
    --add-data "utils;utils" ^
    --hidden-import customtkinter ^
    desktop_app.py
cd ..

echo.
echo [2/3] 打包 网页信息采集平台...
echo ----------------------------------------
cd web-data-collector
pyinstaller --noconfirm --onedir --windowed ^
    --name "网页信息采集平台" ^
    --add-data "sample_data;sample_data" ^
    --add-data "crawlers;crawlers" ^
    --add-data "services;services" ^
    --add-data "utils;utils" ^
    --hidden-import customtkinter ^
    desktop_app.py
cd ..

echo.
echo [3/3] 打包 自动报表机器人...
echo ----------------------------------------
cd report-automation-bot
pyinstaller --noconfirm --onedir --windowed ^
    --name "自动报表机器人" ^
    --add-data "sample_data;sample_data" ^
    --add-data "services;services" ^
    --add-data "utils;utils" ^
    --add-data "templates;templates" ^
    --hidden-import customtkinter ^
    desktop_app.py
cd ..

echo.
echo ============================================
echo   打包完成！输出目录：
echo   excel-reconcile-assistant\dist\
echo   web-data-collector\dist\
echo   report-automation-bot\dist\
echo ============================================
pause
