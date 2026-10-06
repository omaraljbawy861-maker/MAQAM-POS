@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>&1 && set "PY=py"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
 echo Python غير موجود. ثبت Python ثم أعد التشغيل.
 pause
 exit /b 1
)
%PY% -m pip install --upgrade pyinstaller
if errorlevel 1 goto fail
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist MaqamPOS.spec del /q MaqamPOS.spec
%PY% -m PyInstaller --noconfirm --clean --windowed --onedir --name MaqamPOS --icon "maqam_logo.ico" --add-data "maqam_logo.png;." --add-data "maqam_logo_watermark.png;." "maqam_pos.py"
if errorlevel 1 goto fail
echo.
echo BUILD OK: dist\MaqamPOS\MaqamPOS.exe
start "" explorer "%~dp0dist\MaqamPOS"
pause
exit /b 0
:fail
echo BUILD FAILED
pause
exit /b 1
