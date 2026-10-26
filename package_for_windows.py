#!/usr/bin/env python3
"""
InkYard - Windows 10/11 Deployment Packaging Script
Bundles the server application and configuration scripts into a clean,
zero-friction zip package for idle classroom PCs.
"""

import os
import shutil
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_ZIP = BASE_DIR / "InkYard_Windows10.zip"
DESKTOP_DIR = Path.home() / "Desktop"

INCLUDE_FILES = [
    "server.py",
    "requirements.txt",
    "run_server.bat",
    "run_server_windows.bat",
    "run_server_mac.sh",
    "install_python.bat",
    "deploy_seewo.bat",
    "setup_windows.ps1",
    "DEPLOYMENT_GUIDE.md",
    "README.md"
]

INCLUDE_DIRS = [
    "core",
    "templates",
    "static"
]


def _normalize_windows_script_bytes(file_path: Path) -> bytes:
    raw_bytes = file_path.read_bytes()
    text = raw_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n")
    return text.replace("\n", "\r\n").encode("utf-8")


def create_windows_package():
    print("[*] Packaging InkYard for Windows 10/11 Classroom Server...")

    # Ensure on-disk Windows scripts have CRLF line endings
    for fname in INCLUDE_FILES:
        fpath = BASE_DIR / fname
        if fpath.exists() and fname.endswith((".bat", ".cmd", ".ps1")):
            fpath.write_bytes(_normalize_windows_script_bytes(fpath))

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add root files
        for filename in INCLUDE_FILES:
            file_path = BASE_DIR / filename
            if file_path.exists():
                arcname = f"InkYard/{filename}"
                if filename.endswith((".bat", ".cmd", ".ps1")):
                    zf.writestr(arcname, _normalize_windows_script_bytes(file_path))
                else:
                    zf.write(file_path, arcname)
                print(f"  + Added: {arcname}")

        # Add directories
        for dirname in INCLUDE_DIRS:
            dir_path = BASE_DIR / dirname
            if dir_path.exists():
                for root, dirs, files in os.walk(dir_path):
                    dirs[:] = [d for d in dirs if d != "__pycache__"]
                    for file in files:
                        if file.endswith((".pyc", ".pyo", ".DS_Store")):
                            continue
                        full_path = Path(root) / file
                        rel_path = full_path.relative_to(BASE_DIR)
                        arcname = f"InkYard/{rel_path}"
                        zf.write(full_path, arcname)
                        print(f"  + Added: {arcname}")

        # Add empty spool directory placeholder
        zf.writestr("InkYard/spool/.keep", "")
        # Add default student ads to logs
        default_ads_path = BASE_DIR / "logs" / "student_ads.json"
        if default_ads_path.exists():
            zf.write(default_ads_path, "InkYard/logs/student_ads.json")

    # Clean legacy zip in workspace if it exists
    legacy_zip = BASE_DIR / "Printer_InkSaver_Windows10.zip"
    if legacy_zip.exists():
        legacy_zip.unlink(missing_ok=True)

    # Sync only the single primary zip to Desktop if Desktop exists
    if DESKTOP_DIR.exists():
        dest_zip = DESKTOP_DIR / "InkYard_Windows10.zip"
        try:
            shutil.copyfile(OUTPUT_ZIP, dest_zip)
            print(f"  + Synced Desktop archive: {dest_zip}")
        except Exception as e:
            print(f"  [WARN] Could not sync {dest_zip}: {e}")

        # Clean redundant zip files on Desktop
        for redundant_zip_name in ("InkYard_Original.zip", "IYT_1.4.zip", "Printer_InkSaver_Windows10.zip"):
            redundant_zip = DESKTOP_DIR / redundant_zip_name
            if redundant_zip.exists():
                redundant_zip.unlink(missing_ok=True)
                print(f"  - Removed redundant Desktop archive: {redundant_zip_name}")

    size_mb = os.path.getsize(OUTPUT_ZIP) / (1024 * 1024)
    print("=" * 65)
    print(f"  [SUCCESS] Created Windows 10 Package ({size_mb:.2f} MB)")
    print(f"  Primary: {OUTPUT_ZIP}")
    print("  Copy this zip file onto a USB drive or classroom PC, unzip, and:")
    print("    1. Right-click setup_windows.ps1 -> Run with PowerShell (Admin)")
    print("    2. Double-click run_server_windows.bat (or run_server.bat) to start the server")
    print("=" * 65)

if __name__ == "__main__":
    create_windows_package()
