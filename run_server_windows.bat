@echo off
@chcp 65001 >nul
setlocal enabledelayedexpansion

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

title InkYard Portal (Classroom Server)
color 0A

echo =================================================================
echo   [ InkYard - Windows 10/11 Classroom Server ]
echo =================================================================
cd /d "%~dp0"

:detect_python
set "PY_EXE="

REM 1. Check py launcher in PATH (verify Python >= 3.9 and no native crash)
py -3 -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
if !errorlevel! equ 0 (
    for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
        if exist "%%P" (
            set "PY_EXE=%%P"
            for %%A in ("%%P") do set "PATH=%%~dpA;%%~dpA\Scripts;!PATH!"
            goto :python_found
        )
    )
    set "PY_EXE=py -3"
    goto :python_found
)

REM 2. Check python command in PATH (skip WindowsApps stub)
for /f "delims=" %%I in ('where python 2^>nul') do (
    echo %%I | findstr /i "WindowsApps" >nul
    if !errorlevel! neq 0 (
        if exist "%%~fI" (
            "%%~fI" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
            if !errorlevel! equ 0 (
                set "PY_EXE=%%~fI"
                set "PATH=%%~dpI;%%~dpI\Scripts;!PATH!"
                goto :python_found
            )
        )
    )
)

REM 3. Check python3 command in PATH (skip WindowsApps stub)
for /f "delims=" %%I in ('where python3 2^>nul') do (
    echo %%I | findstr /i "WindowsApps" >nul
    if !errorlevel! neq 0 (
        if exist "%%~fI" (
            "%%~fI" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
            if !errorlevel! equ 0 (
                set "PY_EXE=%%~fI"
                set "PATH=%%~dpI;%%~dpI\Scripts;!PATH!"
                goto :python_found
            )
        )
    )
)

REM 4. Scan standard AppData per-user install directory
if exist "%LOCALAPPDATA%\Programs\Python" (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%D\python.exe" (
            "%%D\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
            if !errorlevel! equ 0 (
                set "PY_EXE=%%D\python.exe"
                set "PATH=%%D;%%D\Scripts;!PATH!"
                goto :python_found
            )
        )
    )
)

REM 5. Scan ProgramFiles (64-bit system-wide installs)
for /d %%D in ("%ProgramFiles%\Python3*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PY_EXE=%%D\python.exe"
            set "PATH=%%D;%%D\Scripts;!PATH!"
            goto :python_found
        )
    )
)

REM 6. Scan ProgramFiles(x86) (32-bit installs)
if defined ProgramFiles(x86) (
    for /d %%D in ("%ProgramFiles(x86)%\Python3*") do (
        if exist "%%D\python.exe" (
            "%%D\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
            if !errorlevel! equ 0 (
                set "PY_EXE=%%D\python.exe"
                set "PATH=%%D;%%D\Scripts;!PATH!"
                goto :python_found
            )
        )
    )
)

REM 7. Scan C:\Python3* root directory installs
for /d %%D in ("C:\Python3*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PY_EXE=%%D\python.exe"
            set "PATH=%%D;%%D\Scripts;!PATH!"
            goto :python_found
        )
    )
)

REM 8. Scan D:\Python3* root directory installs (common on partitioned classroom PCs)
for /d %%D in ("D:\Python3*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PY_EXE=%%D\python.exe"
            set "PATH=%%D;%%D\Scripts;!PATH!"
            goto :python_found
        )
    )
)

REM 9. Check Anaconda / Miniconda installations
for %%P in (
    "%USERPROFILE%\anaconda3\python.exe"
    "%USERPROFILE%\miniconda3\python.exe"
    "%LOCALAPPDATA%\anaconda3\python.exe"
    "%LOCALAPPDATA%\miniconda3\python.exe"
    "C:\ProgramData\anaconda3\python.exe"
    "C:\ProgramData\miniconda3\python.exe"
    "C:\anaconda3\python.exe"
    "C:\miniconda3\python.exe"
    "D:\anaconda3\python.exe"
    "D:\miniconda3\python.exe"
) do (
    if exist %%P (
        %%P -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PY_EXE=%%~fP"
            set "PATH=%%~dpP;%%~dpP\Scripts;!PATH!"
            goto :python_found
        )
    )
)

:python_not_found
echo.
echo =================================================================
echo   [ERROR] Python 3.9+ was not detected on this PC!
echo   [TIPS]  Classroom PC (Seewo / Touchscreen) needs Python installed.
echo =================================================================
echo.
echo   InkYard requires Python 3.9+ to run.
echo   You only need to install Python ONCE on this PC.
echo.
echo   Options:
echo     [1] Auto-install Python 3 now (1-click installer, ~30s) [Default]
echo     [2] Open Python.org official download page in web browser
echo     [3] Install via Windows winget package manager
echo     [4] Exit
echo.
set "USER_CHOICE="
set /p USER_CHOICE="Select an option [1/2/3/4] (Default: 1): "
if "!USER_CHOICE!"=="" set USER_CHOICE=1
if "!USER_CHOICE!"=="1" (
    if exist "install_python.bat" (
        call "install_python.bat" --from-launcher
        echo.
        echo [*] Re-checking for Python installation...
        goto :detect_python
    ) else (
        echo [!] install_python.bat not found in directory.
        start https://www.python.org/downloads/
    )
)
if "!USER_CHOICE!"=="2" (
    start https://www.python.org/downloads/
    echo.
    echo Please install Python 3.9+ from https://www.python.org/downloads/
    echo CRITICAL: Check the box "Add Python to PATH" on the first screen!
    echo.
    pause
    exit /b 1
)
if "!USER_CHOICE!"=="3" (
    echo [*] Attempting winget install...
    winget install --id Python.Python.3.11 -e --accept-package-agreements --accept-source-agreements
    goto :detect_python
)
if "!USER_CHOICE!"=="4" (
    exit /b 0
)

echo.
echo Please install Python 3.9+ from https://www.python.org/downloads/
echo CRITICAL: Check the box "Add Python to PATH" during installation!
echo.
pause
exit /b 1

:python_found
echo [*] Python detected: !PY_EXE!

REM Validate existing .venv (rebuild if copied from another PC or broken)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>&1
    if !errorlevel! neq 0 (
        echo [WARN] Existing .venv is from another PC or broken. Rebuilding .venv...
        rmdir /s /q ".venv" >nul 2>&1
    )
)

REM Create .venv if not present
if not exist ".venv\Scripts\python.exe" (
    echo [*] Creating Python virtual environment (.venv)...
    if "!PY_EXE!"=="py -3" (
        py -3 -m venv .venv
    ) else (
        "!PY_EXE!" -m venv .venv
    )
    if !errorlevel! neq 0 (
        echo [WARN] Failed to create .venv virtual environment (code !errorlevel!).
        echo [*] Will run using system Python directly.
    )
)

if exist ".venv\Scripts\python.exe" (
    set "RUN_PY=.venv\Scripts\python.exe"
    echo [*] Using virtual environment: .venv\Scripts\python.exe
) else (
    set "RUN_PY=!PY_EXE!"
    echo [*] Using detected Python: !PY_EXE!
)

REM Fast check if core dependencies are already installed (enables instant offline startup)
echo [*] Checking dependencies (Flask, PyMuPDF, Pillow, OpenCV)...
if "!RUN_PY!"=="py -3" (
    py -3 -c "import flask, fitz, PIL, reportlab, docx, pptx" >nul 2>&1
) else (
    "!RUN_PY!" -c "import flask, fitz, PIL, reportlab, docx, pptx" >nul 2>&1
)
if !errorlevel! neq 0 (
    REM Verify pip is available
    if "!RUN_PY!"=="py -3" (
        py -3 -m pip --version >nul 2>&1
        if !errorlevel! neq 0 py -3 -m ensurepip --default-pip >nul 2>&1
    ) else (
        "!RUN_PY!" -m pip --version >nul 2>&1
        if !errorlevel! neq 0 "!RUN_PY!" -m ensurepip --default-pip >nul 2>&1
    )

    echo [*] Installing/verifying packages via domestic mirror (Tsinghua / Aliyun)...
    if "!RUN_PY!"=="py -3" (
        py -3 -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --quiet
        if !errorlevel! neq 0 (
            echo [WARN] Tsinghua mirror failed, trying Aliyun mirror...
            py -3 -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --quiet
        )
        if !errorlevel! neq 0 (
            echo [WARN] Domestic mirrors failed, trying standard PyPI repository...
            py -3 -m pip install -r requirements.txt --quiet
        )
        py -3 -c "import flask, fitz, PIL" >nul 2>&1
        if !errorlevel! neq 0 (
            echo [*] Installing essential core packages (Flask, PyMuPDF, Pillow, ReportLab)...
            py -3 -m pip install flask pymupdf Pillow reportlab python-docx python-pptx requests -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --quiet
        )
        py -3 -c "import flask, fitz, PIL" >nul 2>&1
    ) else (
        "!RUN_PY!" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --quiet
        if !errorlevel! neq 0 (
            echo [WARN] Tsinghua mirror failed, trying Aliyun mirror...
            "!RUN_PY!" -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --quiet
        )
        if !errorlevel! neq 0 (
            echo [WARN] Domestic mirrors failed, trying standard PyPI repository...
            "!RUN_PY!" -m pip install -r requirements.txt --quiet
        )
        "!RUN_PY!" -c "import flask, fitz, PIL" >nul 2>&1
        if !errorlevel! neq 0 (
            echo [*] Installing essential core packages (Flask, PyMuPDF, Pillow, ReportLab)...
            "!RUN_PY!" -m pip install flask pymupdf Pillow reportlab python-docx python-pptx requests -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --quiet
        )
        "!RUN_PY!" -c "import flask, fitz, PIL" >nul 2>&1
    )
)

set "CORE_CHECK_CODE=!errorlevel!"
if !CORE_CHECK_CODE! neq 0 (
    echo.
    echo =================================================================
    echo   [ERROR] Core Python modules failed to load (exit code: !CORE_CHECK_CODE!)!
    echo   Please check your network connection and run:
    echo     pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo =================================================================
    echo.
    pause
    exit /b 1
)

REM Probe OpenCV / NumPy C-extensions separately (prevent AVX2 CPU crash from blocking server)
if "!RUN_PY!"=="py -3" (
    py -3 -c "import numpy as np, cv2; _ = np.array([1.0], dtype=np.float32) * 4.0" >nul 2>&1
) else (
    "!RUN_PY!" -c "import numpy as np, cv2; _ = np.array([1.0], dtype=np.float32) * 4.0" >nul 2>&1
)
set "CV2_CHECK_CODE=!errorlevel!"
if !CV2_CHECK_CODE! neq 0 (
    echo [WARN] Native OpenCV/NumPy probe returned code !CV2_CHECK_CODE! on this CPU.
    echo [*] Installing CPU-compatible wheels (numpy^<2.0.0, opencv-python-headless==4.8.1.78)...
    set "INKYARD_REPAIR_ATTEMPTED=1"
    if "!RUN_PY!"=="py -3" (
        py -3 -m pip install --upgrade "numpy>=1.24.0,<2.0.0" "opencv-python-headless==4.8.1.78" -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --quiet
        py -3 -c "import numpy as np, cv2; _ = np.array([1.0], dtype=np.float32) * 4.0" >nul 2>&1
    ) else (
        "!RUN_PY!" -m pip install --upgrade "numpy>=1.24.0,<2.0.0" "opencv-python-headless==4.8.1.78" -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --quiet
        "!RUN_PY!" -c "import numpy as np, cv2; _ = np.array([1.0], dtype=np.float32) * 4.0" >nul 2>&1
    )
    if !errorlevel! neq 0 (
        echo [INFO] Enabling pure-Pillow compatibility mode for older classroom CPU...
        set "INKYARD_SKIP_CV2=1"
        if "!RUN_PY!"=="py -3" (
            py -3 -c "import numpy as np; _ = np.array([1.0], dtype=np.float32) * 4.0" >nul 2>&1
        ) else (
            "!RUN_PY!" -c "import numpy as np; _ = np.array([1.0], dtype=np.float32) * 4.0" >nul 2>&1
        )
        if !errorlevel! neq 0 set "INKYARD_SKIP_NUMPY=1"
    )
)

echo.
echo =================================================================
echo   INKYARD SERVER STARTING...
echo.
echo   Classroom PC IPv4 Address:
ipconfig | findstr /i "IPv4" | findstr /v "169.254."
echo.
echo   Local Browser URL (on this PC):
echo   --^> http://localhost:5000   (IMPORTANT: include :5000)
echo.
echo   Students on iPad, Mac, and Windows can open in browser:
echo   --^> http://[IPv4_ADDRESS_ABOVE]:5000 (or :5050 if 5000 is busy)
echo.
echo   Target Printer: Canon Multifunction @ 172.16.4.9
echo =================================================================
echo.

if "!RUN_PY!"=="py -3" (
    py -3 -u server.py
) else (
    "!RUN_PY!" -u server.py
)
set "SRV_EXIT=!errorlevel!"

if !SRV_EXIT! neq 0 (
    echo.
    echo =================================================================
    echo   [ERROR] Server process exited with non-zero code: !SRV_EXIT!
    if "!SRV_EXIT!"=="-1073741795" (
        echo   [CAUSE] 0xC000001D Illegal Instruction - CPU AVX2 incompatibility in C extension.
    )
    if "!SRV_EXIT!"=="-1073741819" (
        echo   [CAUSE] 0xC0000005 Access Violation - Native DLL crash in C extension.
    )
    if "!SRV_EXIT!"=="-1073741515" (
        echo   [CAUSE] 0xC0000135 DLL Not Found - Missing Visual C++ Redistributable runtime.
    )
    echo =================================================================
)

echo.
echo Server has stopped (exit code: !SRV_EXIT!).
pause
