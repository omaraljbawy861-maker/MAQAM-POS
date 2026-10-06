@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title MAQAM POS - Build & Update
color 0A

echo ============================================
echo       MAQAM POS - BUILD AND UPDATE
 echo ============================================
echo.

where py >nul 2>&1
if %errorlevel%==0 (set "PY=py") else (
  where python >nul 2>&1
  if %errorlevel%==0 (set "PY=python") else (
    echo ERROR: Python is not installed.
    pause
    exit /b 1
  )
)

echo [1/4] Checking PyInstaller...
%PY% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo Installing PyInstaller...
  %PY% -m pip install pyinstaller
  if errorlevel 1 (
    echo ERROR: Could not install PyInstaller.
    pause
    exit /b 1
  )
)

echo [2/4] Building the new EXE...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist MaqamPOS.spec del /q MaqamPOS.spec

%PY% -m PyInstaller --noconfirm --clean --windowed --name MaqamPOS --icon maqam_logo.ico maqam_pos.py
if errorlevel 1 (
  echo.
  echo ERROR: Build failed.
  pause
  exit /b 1
)

set "NEWEXE=%~dp0dist\MaqamPOS\MaqamPOS.exe"
if not exist "%NEWEXE%" (
  echo ERROR: New EXE was not created.
  pause
  exit /b 1
)

echo [3/4] Closing the old MAQAM POS if it is running...
taskkill /IM MaqamPOS.exe /F >nul 2>&1

echo [4/4] Looking for the installed MAQAM POS...
set "TARGET="
for %%D in ("%LOCALAPPDATA%\Programs\MaqamPOS" "%LOCALAPPDATA%\MaqamPOS" "%ProgramFiles%\MaqamPOS" "%ProgramFiles(x86)%\MaqamPOS" "%USERPROFILE%\Desktop\MaqamPOS" "%USERPROFILE%\Desktop") do (
  if not defined TARGET if exist "%%~D\MaqamPOS.exe" set "TARGET=%%~D"
)

if not defined TARGET (
  echo.
  echo Could not automatically find the installed copy.
  echo The new EXE is ready here:
  echo %NEWEXE%
  echo.
  start "" explorer.exe /select,"%NEWEXE%"
  pause
  exit /b 0
)

if not exist "%TARGET%\MaqamPOS.exe.bak" copy /y "%TARGET%\MaqamPOS.exe" "%TARGET%\MaqamPOS.exe.bak" >nul
copy /y "%NEWEXE%" "%TARGET%\MaqamPOS.exe" >nul
if errorlevel 1 (
  echo.
  echo ERROR: Could not replace the installed EXE.
  echo Try running this BAT as Administrator.
  pause
  exit /b 1
)

echo.
echo ============================================
echo       UPDATE COMPLETED SUCCESSFULLY
 echo ============================================
echo Installed EXE:
echo %TARGET%\MaqamPOS.exe
echo.
start "" explorer.exe /select,"%TARGET%\MaqamPOS.exe"
start "" "%TARGET%\MaqamPOS.exe"
echo MAQAM POS is now running with the new version.
timeout /t 3 >nul
exit /b 0
