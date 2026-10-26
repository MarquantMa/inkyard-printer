#  InkYard — Cross-Platform Deployment Guide

A unified, zero-install, zero-cost eco-print web portal for schools and campuses.

---

##  The Philosophy: Why a Web Portal Beats an App

| Factor | Native App (App Store) | Local Web Print Portal (This Project) |
|---|---|---|
| **Cost** | \$99/yr Apple Developer Fee + code signing | **\$0.00 completely free & open source** |
| **iPadOS Support** | Blocked without App Store approval | **100% Native via Safari (Zero install)** |
| **Windows Driver Issues** | Users need Canon UFRII/PCL6 drivers | **Zero drivers needed by students** |
| **Sustainability** | Deprecates when OS updates break apps | **Runs itself on school LAN 24/7** |
| **Maintenance** | Constant certificate renewals | **Leave it running on an idle classroom PC** |

---

##  Architecture Overview

```
 [iPadOS / macOS / Windows / Android]  (Students on school Wi-Fi)
             │
             │ Opens browser: http://192.168.x.x:5050 (or :5000)
             ▼
 ┌─────────────────────────────────────────────────────────┐
 │   Host Machine (Classroom Windows 10 PC or macOS)       │
 │   - Flask Local Web Server                              │
 │   - Universal Converter (PDF, Pages, DOCX, PPTX, Img)   │
 │   - OpenCV & PyMuPDF Ink-Saving Engine                  │
 │   - Telemetry Logger (print_log.csv)                    │
 └───────────────────────────┬─────────────────────────────┘
                             │ Direct LPD / PJL (Port 515 / 9100)
                             ▼
                 ┌───────────────────────────┐
                 │ Canon Multifunction       │
                 │ IP: 172.16.4.9            │
                 │ Hold / Secure Print Queue │
                 └───────────────────────────┘
                             │
                             ▼
  Student walks up, taps their name on touchscreen, hits Start!
```

---

## 1. 临时将这台 Mac 用作 1 天服务器进行测试 (Temporary 1-Day Mac Server Test)

**完全可以！现在就可以直接用你的电脑作为服务器进行测试，换另一台电脑或手机/iPad立即连接：**

### 快速启动与防休眠 (Quick Start with Sleep Prevention)
1. 在终端运行启动脚本：
   ```bash
   cd "/Users/marquant/Documents/Printer InkSaver"
   ./run_server_mac.sh
   ```
   *该脚本会自动调用 `caffeinate -dimsu` 全面防止系统与显示屏休眠，保持服务全天在线。*
2. 启动后终端会打印出当前 Wi-Fi 的局域网地址，例如：
   ```
    Localhost:  http://localhost:5050
    School/LAN: http://172.21.8.174:5050
   ```
3. **换另一台电脑、iPad 或手机进行测试：**
   - 确保那台设备与你的 Mac 连接在**同一个 Wi-Fi**（校园网或热点）。
   - 在那台设备的浏览器（Safari、Chrome、Edge）直接打开：
     ```
     http://<YOUR_MAC_IP>:5050
     ```
     （或者直接在 Mac 屏幕上点击右上角“ Connect iPad / QR”扫码打开）。
   - 无需在那台电脑上安装任何驱动、软件或 Python，直接拖入 PDF、Office 或图片即可实时预览与打印！
4. **Mac 测试一整天的注意事项：**
   - 建议连接电源适配器（充电器）。
   - 保持屏幕打开（如果合上盖子且未接外接显示器，macOS 底层电源策略可能会强行挂起系统）。

---

## 2. Permanent 24/7 Deployment: Idle Windows 10/11 Classroom PC

Classrooms frequently have teacher podium PCs or projector computers that stay plugged in all day. Turning one into the dedicated **InkYard** print server costs **\$0** and keeps the service available 24/7 for all students.

### Prerequisites on the Windows PC
- Windows 10 or Windows 11 (64-bit or 32-bit, including Seewo 希沃 touch screens).
- Connected to the campus / classroom Wi-Fi or Ethernet (same subnet as student iPads/laptops).
- Python 3.9+ (If Python is not installed yet, simply double-click `install_python.bat` or follow the automated prompt in `run_server_windows.bat` to install it in 1 click).

### Step-by-Step Deployment

#### Step 1: Transfer the Deployment Zip
1. On your Mac/source machine, run:
   ```bash
   python3 package_for_windows.py
   ```
   This generates `InkYard_Windows10.zip` (approx 110 KB).
2. Copy `InkYard_Windows10.zip` to a USB flash drive, or transfer it to the classroom Windows PC via email, WeChat, or local file sharing.
3. On the Windows PC, extract `InkYard_Windows10.zip` to a permanent location, such as:
   `C:\InkYard` or `D:\InkYard`.

#### Step 2: One-Time Windows Auto-Configuration & Python Setup
1. Open the extracted `InkYard` folder.
2. **If Python is not installed yet**:
   - Double-click **`install_python.bat`** for 1-click automated installation. It automatically downloads Python 3.11 using a high-speed domestic mirror, installs it silently, and enables "Add Python to PATH".
3. Right-click **`setup_windows.ps1`** and select **Run with PowerShell** (or open PowerShell as Administrator and run `.\setup_windows.ps1`).
4. What `setup_windows.ps1` does automatically:
   - **Disables sleep & hibernation**: Sets `powercfg` standby timeout to 0 so the classroom PC stays active 24/7 when plugged in (monitor turns off after 15 min to conserve electricity).
   - **Opens Firewall Ports**: Adds an inbound rule in Windows Defender Firewall for TCP ports `5000, 5050, 8080, 8000` so iPads and student laptops can connect.
   - **Verifies Python**: Confirms Python environment is ready.
   - **Creates Desktop 1-Click Shortcut**: Creates **`Start InkYard.lnk`** directly on the Windows Desktop.

#### Step 3: Launch the Server
1. Double-click the **`Start InkYard`** desktop shortcut (or `run_server_windows.bat`).
2. The batch script will automatically:
   - Scan for Python in standard PATH and `%LOCALAPPDATA%\Programs\Python` locations (even if "Add Python to PATH" was unchecked).
   - Create a Python virtual environment (`.venv`) if not present.
   - Install required packages (`pip install -r requirements.txt`) using high-speed domestic mirrors.
   - Detect the machine's physical LAN IPv4 address (e.g. `172.16.x.x` or `192.168.x.x`).
   - Start the server on `0.0.0.0:5000` (or `5050`).
3. Keep the terminal window open or minimized.

#### Step 4 (Optional): Auto-Start on Windows Boot
To make InkYard survive computer restarts without human intervention:
1. Press `Win + R`, type `shell:startup`, and press Enter.
2. Copy the **`Start InkYard.lnk`** shortcut from your desktop into this Startup folder.
3. Done! Now whenever the classroom computer turns on, InkYard boots up in the background automatically.

#### Step 5: Put Up the QR Code Poster for Students
1. Open `http://localhost:5050` (or `http://localhost:5000`) on the classroom PC.
2. Click ** Connect iPad / QR** in the top navigation bar.
3. Click ** Print QR Poster for Canon**.
4. Tape the printed page right above the physical Canon printer touchscreen!
5. Any student with an iPad, iPhone, Mac, or Windows laptop points their camera at the QR code, opens InkYard instantly, and prints without installing drivers!


---

## 3. Client Experience (iPadOS, macOS, Windows 10/11)

- **iPadOS (Safari)**:
  - Open portal URL.
  - Drag file from Files app or tap to browse.
  - Toggle ink modes, check live before/after slider.
  - Tap **Send to Canon Printer**.
- **macOS (Safari / Chrome)**:
  - Full drag-and-drop support for `.pages`, `.pdf`, `.docx`, `.pptx`, `.png`.
  - Live split preview.
- **Windows 10/11 (Edge / Chrome)**:
  - Identical web experience.
  - Bypasses all Windows driver installation requirements!

---

## 4. The Canon Hold Queue & Secure Print Workflow

The school Canon printer at `172.16.4.9` is configured with a hold queue:

1. **Job Dispatch**: When a student clicks print, the server embeds:
   - `@PJL SET USERNAME = "<Student_Name>"`
   - `LPD Control File: P<Student_Name> J<Doc_Title>`
   - `Duplex: Two-Sided Long Edge (Default ON)`
2. **Printer Display**:
   - The Canon printer holds the job in memory without immediately printing it.
   - The LCD touchscreen displays the student's name in the hold job list.
3. **Release**:
   - The student walks to the printer.
   - Taps their name.
   - Taps **Start Printing**.
   - **Zero paper wasted** from accidental clicks or abandoned print jobs!

---

## 5. Telemetry & Sustainability Metrics (`logs/print_log.csv`)

Every print job automatically logs:
- `Timestamp`: Date and time
- `Student_Name`: Name entered by student
- `Job_Name`: Document title
- `Total_Pages`: Page count
- `Duplex_Used`: True / False
- `Paper_Sheets_Saved`: Sheets spared by duplex
- `Ink_Mode_Selected`: Matrix / Eco / Slide Clean / Line Art / Normal
- `Ink_Saved_Pct`: % reduction
- `Est_Ink_Saved_mL`: Volume in mL

Click the **Impact Stats** button in the web navigation bar to view real-time aggregate charts:
- Total paper sheets spared
- Trees preserved
- Liters of ink prevented from entering landfills
- Duplex adoption percentage
- Data ready to be cited in sustainability clubs, administrative reports, or college applications!
