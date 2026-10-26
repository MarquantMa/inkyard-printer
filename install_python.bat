@echo off
@chcp 65001 >nul
setlocal enabledelayedexpansion

title InkYard - Python Installer Helper
color 0B

echo =================================================================
echo   [ InkYard - Python Auto-Installer for Windows 10/11 ]
echo =================================================================
echo.
cd /d "%~dp0"

REM 1. Quick check if Python 3 is already functional (skip WindowsApps stub)
py -3 -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] Python 3 is already installed and functional via 'py -3'!
    goto :done
)
for /f "delims=" %%I in ('where python 2^>nul') do (
    echo %%I | findstr /i "WindowsApps" >nul
    if !errorlevel! neq 0 (
        if exist "%%~fI" (
            "%%~fI" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
            if !errorlevel! equ 0 (
                echo [OK] Python 3 is already installed and functional at %%~fI!
                goto :done
            )
        )
    )
)

REM Check common local AppData directory
if exist "%LOCALAPPDATA%\Programs\Python" (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%D\python.exe" (
            "%%D\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
            if !errorlevel! equ 0 (
                echo [OK] Python 3 is already installed at %%D!
                goto :done
            )
        )
    )
)

REM 2. Check for winget (Windows Package Manager)
echo [*] Checking for Windows Package Manager (winget)...
winget --version >nul 2>&1
if !errorlevel! equ 0 (
    echo [*] winget found! Installing Python 3.11...
    winget install --id Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements
    if !errorlevel! equ 0 (
        echo [OK] Python 3.11 installed successfully via winget!
        goto :done
    )
    echo [!] winget installation encountered an issue, trying direct download...
)

REM 3. Download official Python installer using PowerShell (with high-speed mirror)
echo [*] Downloading Python 3.11 installer via high-speed domestic mirror...
set "INSTALLER_PATH=%TEMP%\python_installer.exe"
if exist "%INSTALLER_PATH%" del /f /q "%INSTALLER_PATH%" >nul 2>&1

powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $f = if ([Environment]::Is64BitOperatingSystem) { 'python-3.11.9-amd64.exe' } else { 'python-3.11.9.exe' }; $urls = @('https://mirrors.huaweicloud.com/python/3.11.9/' + $f, 'https://cdn.npmmirror.com/binaries/python/3.11.9/' + $f, 'https://www.python.org/ftp/python/3.11.9/' + $f); $dest = $env:TEMP + '\python_installer.exe'; foreach ($u in $urls) { try { Write-Host ('[*] Downloading from ' + $u); (New-Object System.Net.WebClient).DownloadFile($u, $dest); if ((Test-Path $dest) -and ((Get-Item $dest).Length -gt 15000000)) { exit 0 } } catch {} }; exit 1"

if exist "%INSTALLER_PATH%" (
    echo [*] Installer downloaded successfully!
    echo [*] Installing Python 3.11 (with 'Add Python to PATH' enabled)...
    echo [*] Please wait a moment while installation completes...
    start /wait "" "%INSTALLER_PATH%" /passive InstallAllUsers=0 InstallLauncherAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1 Include_test=0
    set "INST_EXIT=!errorlevel!"
    del /f /q "%INSTALLER_PATH%" >nul 2>&1
    if !INST_EXIT! equ 0 goto :done
    echo [!] Installer exited with code !INST_EXIT!.
) else (
    echo [!] Automatic download failed.
)

REM 4. Fallback: Open browser to python.org
echo.
echo =================================================================
echo   [MANUAL INSTALLATION REQUIRED]
echo =================================================================
echo   Opening the official Python download page in your web browser:
echo   --^> https://www.python.org/downloads/
echo.
echo   STEP 1: Download Python 3.11 or 3.12 (Windows installer 64-bit).
echo   STEP 2: Run the downloaded .exe installer.
echo   STEP 3: CRITICAL: Check the box "Add Python to PATH" on the
echo           very first screen of the installer!
echo   STEP 4: Click "Install Now".
echo =================================================================
start https://www.python.org/downloads/
echo.
pause
exit /b 1

:done
echo.
echo =================================================================
echo   [SUCCESS] Python 3 installation complete!
echo =================================================================
echo.
if "%~1"=="--from-launcher" exit /b 0
pause
exit /b 0
