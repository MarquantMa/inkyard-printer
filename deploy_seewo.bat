@echo off
@chcp 65001 >nul
setlocal enabledelayedexpansion
title InkYard - Seewo Classroom 1-Click Deployment
color 0A

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "BASE=%~dp0"
set "LOG=%BASE%deploy_log.txt"
cd /d "%BASE%"

>> "%LOG%" echo ===== [DEPLOY START] %date% %time% =====

echo ================================================================
echo   [InkYard] Seewo Classroom PC 1-Click Deployment
echo   - Detect / Auto-install Python 3.9+
echo   - Install dependencies via high-speed domestic mirrors
echo   - Configure Power / Windows Firewall / Auto-Start
echo   - Launch Print Portal Server
echo   Log file: deploy_log.txt
echo ================================================================
echo.

REM ============================================================
REM [1/6] Power Settings: Disable sleep/hibernate on AC power
REM ============================================================
echo [1/6] Configuring power settings (disable sleep/hibernate)...
powercfg /change standby-timeout-ac 0 >nul 2>&1
if !errorlevel! neq 0 (
    powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP STANDBYIDLE 0 >nul 2>&1
    powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP HIBERNATEIDLE 0 >nul 2>&1
    powercfg /setacvalueindex SCHEME_CURRENT SUB_VIDEO VIDEOIDLE 900 >nul 2>&1
    powercfg /setactive SCHEME_CURRENT >nul 2>&1
) else (
    powercfg /change hibernate-timeout-ac 0 >nul 2>&1
    powercfg /change monitor-timeout-ac 15 >nul 2>&1
)
echo     [OK] Sleep/hibernate disabled (monitor sleeps after 15 mins)
>> "%LOG%" echo [1/6] power settings ok
echo.

REM ============================================================
REM [2/6] Firewall: Open TCP ports 5000,5050,8080,8000
REM ============================================================
echo [2/6] Configuring Windows Firewall (ports 5000,5050,8080,8000)...
net session >nul 2>&1
if !errorlevel! equ 0 goto :fw_admin

reg query "HKLM\SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy\FirewallRules" /f "InkYardWebPortal" /d >nul 2>&1
if !errorlevel! equ 0 (
    echo     [OK] Firewall rule already exists, skipping
    >> "%LOG%" echo [2/6] firewall rule already exists
    goto :fw_done
)
echo     [!] Requesting Administrator permission for Firewall rule...
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-Command','netsh advfirewall firewall delete rule name=InkYardWebPortal; netsh advfirewall firewall add rule name=InkYardWebPortal dir=in action=allow protocol=TCP localport=5000,5050,8080,8000'"
if !errorlevel! neq 0 (
    echo     [WARN] Firewall rule not applied (no admin rights).
    >> "%LOG%" echo [2/6] firewall FAILED - no admin rights
) else (
    echo     [OK] Firewall rule configured
    >> "%LOG%" echo [2/6] firewall rule created
)
goto :fw_done

:fw_admin
netsh advfirewall firewall delete rule name=InkYardWebPortal >nul 2>&1
netsh advfirewall firewall add rule name=InkYardWebPortal dir=in action=allow protocol=TCP localport=5000,5050,8080,8000 >nul 2>&1
if !errorlevel! neq 0 (
    echo     [WARN] Firewall configuration returned non-zero status
    >> "%LOG%" echo [2/6] firewall FAILED - netsh error
) else (
    echo     [OK] Firewall rule configured
    >> "%LOG%" echo [2/6] firewall rule created
)
:fw_done
echo.

REM ============================================================
REM [3/6] Detect or Install Python 3.9+
REM ============================================================
echo [3/6] Detecting Python 3.9+ environment...
:detect_python
set "PY_EXE="

if exist "%BASE%.venv\Scripts\python.exe" (
    "%BASE%.venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY_EXE=%BASE%.venv\Scripts\python.exe"
        goto :python_ok
    )
)

py -3 -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
if !errorlevel! equ 0 (
    for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
        if exist "%%P" (
            set "PY_EXE=%%P"
            goto :python_found
        )
    )
)

for /f "delims=" %%I in ('where python 2^>nul') do (
    echo %%I | findstr /i "WindowsApps" >nul
    if !errorlevel! neq 0 (
        if exist "%%~fI" (
            "%%~fI" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
            if !errorlevel! equ 0 (
                set "PY_EXE=%%~fI"
                goto :python_found
            )
        )
    )
)

if exist "%LOCALAPPDATA%\Programs\Python" (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%D\python.exe" (
            "%%D\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
            if !errorlevel! equ 0 (
                set "PY_EXE=%%D\python.exe"
                goto :python_found
            )
        )
    )
)

for /d %%D in ("%ProgramFiles%\Python3*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PY_EXE=%%D\python.exe"
            goto :python_found
        )
    )
)

for /d %%D in ("C:\Python3*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PY_EXE=%%D\python.exe"
            goto :python_found
        )
    )
)

for /d %%D in ("D:\Python3*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PY_EXE=%%D\python.exe"
            goto :python_found
        )
    )
)

for %%P in ("%ProgramData%\anaconda3\python.exe" "%ProgramData%\miniconda3\python.exe" "C:\anaconda3\python.exe" "C:\miniconda3\python.exe" "D:\anaconda3\python.exe" "D:\miniconda3\python.exe" "%USERPROFILE%\anaconda3\python.exe" "%USERPROFILE%\miniconda3\python.exe") do (
    if exist %%P (
        "%%~fP" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PY_EXE=%%~fP"
            goto :python_found
        )
    )
)

:try_install
if defined PY_INSTALL_ATTEMPTED (
    echo     [ERROR] Automatic Python installation failed.
    echo             Please install Python 3.11+ from https://www.python.org/downloads/
    echo             and check "Add Python to PATH".
    >> "%LOG%" echo [3/6] ERROR - python install failed
    pause
    exit /b 1
)
set "PY_INSTALL_ATTEMPTED=1"
echo     [!] Python not detected, starting automatic installation...
>> "%LOG%" echo [3/6] no python found - attempting auto install
if exist "%BASE%install_python.bat" (
    call "%BASE%install_python.bat" --from-launcher
    goto :detect_python
)
echo     [ERROR] install_python.bat is missing.
>> "%LOG%" echo [3/6] ERROR - install_python.bat missing
pause
exit /b 1

:python_found
"!PY_EXE!" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
if !errorlevel! equ 0 goto :python_ok
echo     [!] Detected Python is older than 3.9; upgrading...
goto :try_install

:python_ok
echo     [OK] Using Python: !PY_EXE!
>> "%LOG%" echo [3/6] python found: !PY_EXE!
echo.

REM ============================================================
REM [4/6] Virtual Environment & Dependencies
REM ============================================================
echo [4/6] Checking virtual environment and installing dependencies...
if exist "%BASE%.venv\Scripts\python.exe" (
    "%BASE%.venv\Scripts\python.exe" -c "import sys" >nul 2>&1
    if !errorlevel! neq 0 (
        echo     [!] Invalid .venv detected (copied from another PC). Rebuilding...
        rmdir /s /q "%BASE%.venv" >nul 2>&1
        >> "%LOG%" echo [4/6] invalid venv detected - rebuilding
    )
)
if not exist "%BASE%.venv\Scripts\python.exe" (
    "!PY_EXE!" -m venv "%BASE%.venv"
    if !errorlevel! neq 0 echo     [WARN] venv creation failed, using system Python
    >> "%LOG%" echo [4/6] venv created
)
if exist "%BASE%.venv\Scripts\python.exe" (
    set "RUN_PY=%BASE%.venv\Scripts\python.exe"
    echo     [OK] Virtual environment ready: %BASE%.venv
) else (
    set "RUN_PY=!PY_EXE!"
    echo     [OK] Using system Python: !PY_EXE!
)

"!RUN_PY!" -c "import flask, fitz, PIL, reportlab, docx, pptx" >nul 2>&1
if !errorlevel! neq 0 (
    "!RUN_PY!" -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --quiet >nul 2>&1
    echo     [*] Installing requirements via domestic mirrors...
    "!RUN_PY!" -m pip install -r "%BASE%requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --quiet
    if !errorlevel! neq 0 (
        echo     [WARN] Tsinghua mirror failed, trying Aliyun mirror...
        "!RUN_PY!" -m pip install -r "%BASE%requirements.txt" -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --quiet
    )
    if !errorlevel! neq 0 (
        echo     [WARN] Domestic mirrors failed, trying default PyPI...
        "!RUN_PY!" -m pip install -r "%BASE%requirements.txt" --quiet
    )
    "!RUN_PY!" -c "import flask, fitz, PIL" >nul 2>&1
    if !errorlevel! neq 0 (
        echo     [*] Installing essential core packages (Flask, PyMuPDF, Pillow, ReportLab)...
        "!RUN_PY!" -m pip install flask pymupdf Pillow reportlab python-docx python-pptx requests -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --quiet
    )
)

"!RUN_PY!" -c "import flask, fitz, PIL" >nul 2>&1
set "DEP_CODE=!errorlevel!"
if !DEP_CODE! neq 0 (
    echo     [ERROR] Core dependencies failed to load (exit code: !DEP_CODE!).
    >> "%LOG%" echo [4/6] ERROR - dependency check failed with code !DEP_CODE!
    pause
    exit /b 1
)

REM Probe OpenCV/NumPy separately to guard against AVX2 Illegal Instruction crash on older Seewo CPUs
"!RUN_PY!" -c "import numpy as np, cv2; _ = np.array([1.0], dtype=np.float32) * 4.0" >nul 2>&1
if !errorlevel! neq 0 (
    echo     [WARN] OpenCV/NumPy native probe failed on this CPU. Installing compatible wheels...
    set "INKYARD_REPAIR_ATTEMPTED=1"
    "!RUN_PY!" -m pip install --upgrade "numpy>=1.24.0,<2.0.0" "opencv-python-headless==4.8.1.78" -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --quiet
    "!RUN_PY!" -c "import numpy as np, cv2; _ = np.array([1.0], dtype=np.float32) * 4.0" >nul 2>&1
    if !errorlevel! neq 0 (
        echo     [INFO] Enabling pure-Pillow compatibility fallback (INKYARD_SKIP_CV2=1).
        set "INKYARD_SKIP_CV2=1"
        "!RUN_PY!" -c "import numpy as np; _ = np.array([1.0], dtype=np.float32) * 4.0" >nul 2>&1
        if !errorlevel! neq 0 set "INKYARD_SKIP_NUMPY=1"
    )
)

echo     [OK] Dependencies verified!
>> "%LOG%" echo [4/6] dependencies ok
echo.

REM ============================================================
REM [5/6] Desktop & Startup Shortcuts
REM ============================================================
echo [5/6] Creating Desktop and Startup shortcuts...
powershell -NoProfile -Command "$wsh=New-Object -ComObject WScript.Shell; $desktop=[Environment]::GetFolderPath('Desktop'); $startup=[Environment]::GetFolderPath('Startup'); $dir=(Get-Location).Path; $lnk=$wsh.CreateShortcut($desktop+'\Start InkYard.lnk'); $lnk.TargetPath=$dir+'\run_server_windows.bat'; $lnk.WorkingDirectory=$dir; $lnk.Save(); Copy-Item ($desktop+'\Start InkYard.lnk') ($startup+'\Start InkYard.lnk') -Force" >nul 2>&1
echo     [OK] Shortcuts created on Desktop and Startup folder
>> "%LOG%" echo [5/6] shortcuts ok
echo.

REM ============================================================
REM [6/6] Launch Server Window (with visible console output)
REM ============================================================
echo [6/6] Launching InkYard Print Portal Server...
echo.
echo   Classroom PC IPv4 Address:
ipconfig | findstr /i "IPv4" | findstr /v "169.254."
echo.
echo ================================================================
echo   DEPLOYMENT COMPLETE!
echo   * Local URL (this PC):  http://localhost:5000  (include :5000)
echo   * Student Wi-Fi URL:    http://[IPv4_ABOVE]:5000
echo ================================================================
echo.

start "InkYard Server" cmd /k ""!RUN_PY!" -u "%BASE%server.py""
if !errorlevel! neq 0 (
    echo     [WARN] Failed to launch separate server window; running inline...
    >> "%LOG%" echo [6/6] running inline server
    "!RUN_PY!" -u "%BASE%server.py"
) else (
    >> "%LOG%" echo [6/6] server window launched
)

echo     [*] Waiting for server readiness (up to 10 seconds)...
%SystemRoot%\System32\timeout.exe /t 4 /nobreak >nul 2>nul
for /l %%R in (1,1,4) do (
    for %%Q in (5000 5050 8080 8000 3000) do (
        curl -s -o nul -m 2 http://localhost:%%Q/ >nul 2>&1
        if !errorlevel! equ 0 (
            echo     [OK] Server is online and responding at http://localhost:%%Q
            >> "%LOG%" echo [6/6] server responding on port %%Q
            for /f "delims=" %%U in ('curl -s -m 5 http://localhost:%%Q/api/network_info 2^>nul') do >> "%LOG%" echo [6/6] network info: %%U
            goto :srv_ok
        )
    )
    %SystemRoot%\System32\timeout.exe /t 2 /nobreak >nul 2>nul
)
echo     [WARN] Server did not respond within timeout. Check the "InkYard Server" window for details.
>> "%LOG%" echo [6/6] WARNING - server not responding on any port
:srv_ok
echo.
pause
