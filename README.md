# InkYard Autonomous Campus Print & InkSaver Suite 🖨️🌱
> **Self-Service Campus Printing Network Processing 35,000+ Pages/Month with Bayer 8×8 Spatial Halftoning & Connected-Component Stroke Protection**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)]()
[![Hardware: Ricoh IM C3000--6000](https://img.shields.io/badge/Printer-Ricoh%20SNMP%2FLPR-red.svg)]()
[![Impact: 50%+ Ink Saved](https://img.shields.io/badge/Toner%20Conservation-51.2%25-success.svg)]()
[![Author: Haoran Ma](https://img.shields.io/badge/Author-Haoran%20Ma-orange.svg)](https://github.com/marquant)

---

## 1. The Campus Crisis & Vision
At high school campuses, students wait in 20-minute queues outside faculty offices to print past exams, only to face strict page quotas and exorbitant commercial fees. **InkYard** solved this by revitalizing dormant Ricoh multifunction copiers across campus into an autonomous, 100% self-service student printing network.

By developing a custom ink-saving image processing engine, InkYard slashed carbon toner consumption by **51.2%** while preserving razor-sharp text clarity, making student printing completely free.

### System Milestones:
- **Volume:** 35,000+ student pages processed monthly.
- **Queue Latency:** Reduced peak waiting times from 20 minutes to 30 seconds.
- **Toner Conservation:** Over 50% toner saved via Bayer 8x8 spatial threshold dithering.
- **Hardware Cost:** ¥0 capital budget — deployed entirely on recycled school copiers and Seewo interactive touchscreens.

---

## 2. Core Halftoning & Chinese Typography Protection

### Bayer 8×8 Matrix Discretization
To prevent toner bleeding and heavy carbon accumulation in background fills, gray levels are discretized across an 8×8 threshold pattern scaled by 4.0:
$$D_{\text{bayer}}(x, y) = M_{8 \times 8}[y \bmod 8, x \bmod 8] \times 4.0$$
$$\text{Output}(x, y) = \begin{cases} 255 & \text{Gray}(x, y) > D_{\text{bayer}}(x, y) \\ 0 & \text{otherwise} \end{cases}$$

### Connected-Component Hanzi Stroke Lock
Standard Floyd-Steinberg or error diffusion halftoning destroys intricate Chinese character radicals (Hanzi strokes). InkYard runs an 8-connectivity component analysis:
1. Connected pixel regions with bounding areas $< 3,500$ pixels are identified.
2. Distance transform checks ($D_{L2} \le 4.0$) isolate essential stroke spines.
3. Protected text glyphs bypass dithering and remain 100% solid black, guaranteeing perfect legibility for formulas and Chinese characters.

---

## 3. Architecture & Repository Structure

```
inkyard-printer/
├── core/
│   ├── converter.py            # PDF / Office document to image rasterizer
│   ├── ink_saver.py            # Bayer 8x8 dithering & text-lock algorithm
│   ├── printer_dispatcher.py   # Windows LPR / CUPS RAW printer spooler
│   └── telemetry.py            # Ricoh SNMP ink counter & logging service
├── server.py                   # Flask REST server & mobile QR upload portal
├── static/                     # Web UI, QR code generator, and CSS styles
├── templates/                  # Responsive web dashboard
├── tests/                      # Pytest automated verification suite
│   ├── test_converter.py
│   ├── test_ink_saver.py
│   ├── test_printer.py
│   └── test_server.py
├── spool/                      # Temporary print job queue directory
├── deploy_seewo.bat            # Automated deployment script for Seewo touchscreens
├── DEPLOYMENT_GUIDE.md         # Production field setup guide
├── requirements.txt
├── LICENSE
└── README.md
```

---

## 4. Quickstart

### Installation
```bash
git clone https://github.com/marquant/inkyard-printer.git
cd inkyard-printer

pip install -r requirements.txt
```

### Running the Server
```bash
# On macOS / Linux:
./run_server_mac.sh

# On Windows (Campus Server / Seewo Smartboard):
run_server_windows.bat
```
Navigate to `http://localhost:5000` to view the student print portal.

### Running Test Suite
```bash
pytest tests/ -v
```

---

## 5. Author & License
- **Author:** Haoran Ma (Marquant) ([GitHub @marquant](https://github.com/marquant))
- **Email:** `marquant_voldemort@icloud.com`
- **License:** MIT License
