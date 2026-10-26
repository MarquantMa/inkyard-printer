"""
Telemetry & Impact Logger for Printer InkSaver
Logs all print activity to `logs/print_log.csv` and provides
sustainability analytics and propaganda metrics.
"""

import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "print_log.csv"
ADS_FILE = LOG_DIR / "student_ads.json"

CSV_HEADERS = [
    "Timestamp",
    "Student_Name",
    "Job_Name",
    "File_Type",
    "Total_Pages",
    "Printed_Pages",
    "Duplex_Used",
    "Paper_Sheets_Used",
    "Paper_Sheets_Saved",
    "Ink_Mode_Selected",
    "Ink_Saved_Pct",
    "Est_Ink_Saved_mL",
    "Status"
]

DEFAULT_ADS = [
    {
        "id": "ad-1",
        "title": "Robotics Club Expo",
        "tagline": "Build the future with us",
        "desc": "Join our autonomous drone demonstration this Friday @ Lab 204. Free boba & stickers!",
        "contact": "@school_robotics",
        "badge": "Student Club"
    },
    {
        "id": "ad-2",
        "title": "Peer Tutoring & Coffee",
        "tagline": "AP Calculus & Physics Mechanics",
        "desc": "Stuck on problem sets? Drop in Tuesday evenings at the library. Coffee provided!",
        "contact": "tutoring@campus.edu",
        "badge": "Academic Hub"
    },
    {
        "id": "ad-3",
        "title": "Eco-Ink Fundraiser",
        "tagline": "Help keep campus printing free",
        "desc": "Love the InkYard portal? Buy the dev team a coffee or sponsor organic soybean toner!",
        "contact": "Support InkYard",
        "badge": "Community"
    }
]


def ensure_telemetry_setup():
    """Ensure logs directory and CSV file exist with proper headers."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if not LOG_FILE.exists():
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
            
    if not ADS_FILE.exists():
        with open(ADS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_ADS, f, indent=2, ensure_ascii=False)


def log_print_job(
    student_name: str,
    job_name: str,
    file_type: str,
    total_pages: int,
    printed_pages: int,
    duplex: bool,
    ink_mode: str,
    ink_saved_pct: float,
    est_ink_saved_ml: float,
    status: str = "Dispatched"
) -> dict:
    """Append a print job record to print_log.csv."""
    ensure_telemetry_setup()
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Calculate paper sheets: duplex cuts sheets in half (ceil(pages / 2))
    if duplex:
        sheets_used = (printed_pages + 1) // 2
        sheets_saved = printed_pages - sheets_used
    else:
        sheets_used = printed_pages
        sheets_saved = 0

    record = [
        timestamp,
        student_name,
        job_name,
        file_type,
        total_pages,
        printed_pages,
        "True" if duplex else "False",
        sheets_used,
        sheets_saved,
        ink_mode,
        round(ink_saved_pct, 1),
        round(est_ink_saved_ml, 3),
        status
    ]
    
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(record)
        
    return {
        "timestamp": timestamp,
        "sheets_used": sheets_used,
        "sheets_saved": sheets_saved,
        "ink_saved_ml": round(est_ink_saved_ml, 3)
    }


def get_telemetry_stats() -> dict:
    """
    Read print_log.csv and aggregate total impact metrics.
    """
    ensure_telemetry_setup()
    
    total_jobs = 0
    total_printed_pages = 0
    total_sheets_used = 0
    total_sheets_saved = 0
    total_ink_saved_ml = 0.0
    mode_counts = {}
    duplex_count = 0

    if LOG_FILE.exists():
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    total_jobs += 1
                    pp = int(row.get("Printed_Pages", 1))
                    total_printed_pages += pp
                    
                    duplex_used = row.get("Duplex_Used", "True") == "True"
                    if duplex_used:
                        duplex_count += 1
                        
                    sheets_saved = int(row.get("Paper_Sheets_Saved", 0))
                    total_sheets_saved += sheets_saved
                    total_sheets_used += int(row.get("Paper_Sheets_Used", pp))
                    
                    ink_ml = float(row.get("Est_Ink_Saved_mL", 0.0))
                    total_ink_saved_ml += ink_ml
                    
                    m = row.get("Ink_Mode_Selected", "eco")
                    mode_counts[m] = mode_counts.get(m, 0) + 1
                except Exception:
                    continue

    # Environmental formulas:
    # 1 standard mature tree produces ~8,333 sheets of standard office paper
    # 1 sheet of paper ~ 4.5 grams CO2 eq in production
    # 1 standard ink cartridge holds ~15-20 mL of ink
    trees_saved = total_sheets_saved / 8333.0
    co2_saved_kg = (total_sheets_saved * 4.5) / 1000.0
    cartridges_saved = total_ink_saved_ml / 18.0
    duplex_adoption_rate = round((duplex_count / max(1, total_jobs)) * 100, 1)

    # Dynamic humorous slogans
    slogans = [
        f"If the entire school prints like this, we'll save {max(1, int(trees_saved * 50 + 12))} trees and enough ink to fill an Olympic pool!",
        "Every double-sided page is a high-five to Mother Nature.",
        "Zero driver installs, zero waste, 100% sustainable engineering.",
        "Matrix mode: Retro dot-matrix swagger with 50% toner liberation.",
        "Printing smart: Your tuition wasn't meant to be burned on black toner cartridges."
    ]

    return {
        "total_jobs": total_jobs,
        "total_pages": total_printed_pages,
        "total_sheets_used": total_sheets_used,
        "total_sheets_saved": total_sheets_saved,
        "total_ink_saved_ml": round(total_ink_saved_ml, 2),
        "total_ink_saved_liters": round(total_ink_saved_ml / 1000.0, 3),
        "cartridges_saved": round(cartridges_saved, 1),
        "trees_saved": round(trees_saved, 4),
        "co2_saved_kg": round(co2_saved_kg, 2),
        "duplex_adoption_rate": duplex_adoption_rate,
        "mode_breakdown": mode_counts,
        "propaganda_slogans": slogans
    }


def get_student_ads() -> list:
    """Return active student ads."""
    ensure_telemetry_setup()
    try:
        with open(ADS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_ADS


def add_student_ad(title: str, tagline: str, desc: str, contact: str, badge: str = "Club") -> dict:
    """Add a new student ad to the rotation."""
    ensure_telemetry_setup()
    ads = get_student_ads()
    new_ad = {
        "id": f"ad-{int(time.time())}",
        "title": title[:60],
        "tagline": tagline[:80],
        "desc": desc[:200],
        "contact": contact[:50],
        "badge": badge[:20]
    }
    ads.insert(0, new_ad)
    # Keep up to 15 ads
    ads = ads[:15]
    with open(ADS_FILE, "w", encoding="utf-8") as f:
        json.dump(ads, f, indent=2, ensure_ascii=False)
    return new_ad
