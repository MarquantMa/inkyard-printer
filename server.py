"""
InkYard - Local Web Print Server
Universal, zero-install print portal for Mac, Windows, iPad, iPhone, and Android.
Delivers Apple-style minimalist UI, OpenCV ink-saving engine, and direct Canon printer dispatch.
"""

import os
import sys

# Reconfigure stdout/stderr immediately with errors="replace" and line_buffering=True
# so Windows GBK consoles never raise UnicodeEncodeError or buffer output before a native crash.
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass

print(
    f"[InkYard] Bootstrapping server... (Python {sys.version.split()[0]} on {sys.platform})",
    flush=True
)

import io
import json
import uuid
import socket
import logging
import subprocess
import threading
import webbrowser
from pathlib import Path

# Ensure current dir is in Python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))


def _get_probe_cache_key() -> str:
    """Build a cache key from Python executable, version, host, and native package mtimes without importing them."""
    import importlib.util
    import platform

    parts = [sys.executable, sys.version, platform.node()]
    for mod_name in ("numpy", "PIL", "fitz", "cv2"):
        try:
            spec = importlib.util.find_spec(mod_name)
            if spec and spec.origin:
                p = Path(spec.origin)
                mtime = int(p.stat().st_mtime) if p.exists() else 0
                parts.append(f"{mod_name}:{mtime}")
            else:
                parts.append(f"{mod_name}:missing")
        except Exception:
            parts.append(f"{mod_name}:err")
    return "|".join(parts)


def _probe_native_modules(force: bool = False) -> dict:
    """
    Lightweight subprocess probe for native C-extensions (numpy, PIL, fitz, cv2).
    Prevents Windows hardware SEH crashes (0xC000001D Illegal Instruction AVX2 or
    0xC0000005 Access Violation) from silently killing the main server process with 0 output.
    Caches probe state in logs/.native_probe_ok keyed by executable, version, host, and package mtimes.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            # SEM_FAILCRITICALERRORS (0x0001) | SEM_NOGPFAULTERRORBOX (0x0002) | SEM_NOOPENFILEERRORBOX (0x8000)
            # Suppresses Windows "python.exe has stopped working" modal dialog in child probe processes.
            ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
        except Exception:
            pass

    results = {"numpy": True, "PIL": True, "fitz": True, "cv2": True}
    if not force:
        if os.environ.get("INKYARD_SKIP_NUMPY") == "1":
            results["numpy"] = False
            results["cv2"] = False
            os.environ["INKYARD_SKIP_CV2"] = "1"
        elif os.environ.get("INKYARD_SKIP_CV2") == "1":
            results["cv2"] = False

        if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("INKYARD_SKIP_PROBE") == "1":
            return results

    cache_dir = BASE_DIR / "logs"
    cache_file = cache_dir / ".native_probe_ok"
    cache_key = _get_probe_cache_key()

    if not force and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if cached.get("key") == cache_key and isinstance(cached.get("results"), dict):
                saved_res = cached["results"]
                if not saved_res.get("numpy", True) or os.environ.get("INKYARD_SKIP_NUMPY") == "1":
                    saved_res["numpy"] = False
                    saved_res["cv2"] = False
                    os.environ["INKYARD_SKIP_NUMPY"] = "1"
                    os.environ["INKYARD_SKIP_CV2"] = "1"
                elif not saved_res.get("cv2", True) or os.environ.get("INKYARD_SKIP_CV2") == "1":
                    saved_res["cv2"] = False
                    os.environ["INKYARD_SKIP_CV2"] = "1"
                if saved_res.get("PIL", True) and saved_res.get("fitz", True):
                    return saved_res
        except Exception:
            pass

    # Fast batch check when not forced and no modules are pre-skipped
    if not force and results["numpy"] and results["cv2"]:
        try:
            batch_cmd = (
                "import warnings; warnings.simplefilter('ignore'); "
                "import numpy as np, PIL.Image, fitz, cv2; "
                "_ = np.array([1.0], dtype=np.float32) * 4.0"
            )
            res = subprocess.run(
                [sys.executable, "-c", batch_cmd],
                capture_output=True,
                timeout=10
            )
            if res.returncode == 0:
                try:
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    cache_file.write_text(
                        json.dumps({"key": cache_key, "results": results}),
                        encoding="utf-8"
                    )
                except Exception:
                    pass
                return results
        except Exception:
            pass

    # Individual module probing to isolate any crashing C extension
    probes = [
        ("numpy", "import numpy as np; _ = np.array([1.0], dtype=np.float32) * 4.0", "INKYARD_SKIP_NUMPY"),
        ("PIL", "from PIL import Image, ImageOps, ImageFilter", None),
        ("fitz", "import warnings; warnings.simplefilter('ignore'); import fitz", None),
        ("cv2", "import cv2", "INKYARD_SKIP_CV2"),
    ]

    crashed_modules = []
    failure_codes = {}
    for mod_name, stmt, skip_env in probes:
        if not force and not results.get(mod_name, True):
            continue
        try:
            res = subprocess.run(
                [sys.executable, "-c", stmt],
                capture_output=True,
                timeout=10
            )
            rc = res.returncode
        except Exception as e:
            rc = -1
            print(f"[InkYard] [WARN] Subprocess probe for '{mod_name}' timed out or failed: {e}", flush=True)

        if rc != 0:
            results[mod_name] = False
            failure_codes[mod_name] = rc
            unsigned_rc = rc & 0xFFFFFFFF
            hex_code = f"0x{unsigned_rc:08X}"
            reason = "ImportError / Module missing"
            if unsigned_rc == 0xC000001D:
                reason = "Illegal Instruction (AVX2/SIMD CPU instruction unsupported on this PC)"
            elif unsigned_rc == 0xC0000005:
                reason = "Access Violation (Native C-extension DLL crash)"
            elif unsigned_rc == 0xC0000135:
                reason = "DLL Not Found (Missing Visual C++ Redistributable runtime)"
            elif rc < 0 or rc > 128:
                reason = "Native C-extension hardware/SEH crash"

            print(
                f"[InkYard] [WARN] Native module '{mod_name}' failed health probe "
                f"(exit={rc}, code={hex_code}: {reason}).",
                flush=True
            )
            if skip_env:
                os.environ[skip_env] = "1"
            crashed_modules.append((mod_name, stmt, skip_env))

    # Optional auto-repair on Windows when a native extension crashes due to an incompatible wheel
    if (
        crashed_modules
        and sys.platform == "win32"
        and os.environ.get("INKYARD_AUTO_REPAIR", "1") != "0"
        and os.environ.get("INKYARD_REPAIR_ATTEMPTED") != "1"
    ):
        os.environ["INKYARD_REPAIR_ATTEMPTED"] = "1"
        repair_pkgs = []
        crashed_names = {m[0] for m in crashed_modules}
        if "numpy" in crashed_names or "cv2" in crashed_names:
            if sys.version_info[:2] < (3, 13):
                repair_pkgs.extend(["numpy>=1.24.0,<2.0.0", "opencv-python-headless==4.8.1.78"])
            else:
                repair_pkgs.extend(["numpy>=2.0.0", "opencv-python-headless>=4.10.0"])
        if "PIL" in crashed_names:
            repair_pkgs.append("Pillow>=10.0.0")
        if "fitz" in crashed_names:
            repair_pkgs.append("pymupdf>=1.23.0")

        if repair_pkgs:
            print(
                f"[InkYard] [*] Attempting automatic wheel repair for classroom CPU ({', '.join(repair_pkgs)})...",
                flush=True
            )
            try:
                repair_cmd = [
                    sys.executable, "-m", "pip", "install",
                    "--upgrade", "--force-reinstall",
                    *repair_pkgs,
                    "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
                    "--trusted-host", "pypi.tuna.tsinghua.edu.cn",
                    "--quiet"
                ]
                subprocess.run(repair_cmd, capture_output=True, timeout=120)
                for mod_name, stmt, skip_env in crashed_modules:
                    recheck = subprocess.run([sys.executable, "-c", stmt], capture_output=True, timeout=10)
                    if recheck.returncode == 0:
                        print(f"[InkYard] [OK] Repaired native module '{mod_name}'!", flush=True)
                        results[mod_name] = True
                        failure_codes.pop(mod_name, None)
                        if skip_env:
                            os.environ.pop(skip_env, None)
                    elif skip_env:
                        print(
                            f"[InkYard] [INFO] Using pure-Pillow compatibility fallback for '{mod_name}'.",
                            flush=True
                        )
            except Exception as e:
                print(f"[InkYard] [INFO] Auto-repair skipped ({e}); continuing with pure-Pillow fallback.", flush=True)

    if not results.get("numpy", True):
        results["cv2"] = False
        os.environ["INKYARD_SKIP_CV2"] = "1"

    # Cache probe outcome whenever mandatory modules (PIL, fitz) are healthy
    # so subsequent startups on older CPUs skip redundant crash probes and pip repair attempts.
    if not force and results.get("PIL", False) and results.get("fitz", False):
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(
                json.dumps({"key": _get_probe_cache_key(), "results": results}),
                encoding="utf-8"
            )
        except Exception:
            pass

    return results


# Defensive import wrapper so double-clicking server.py on Windows never flashes closed
try:
    from flask import Flask, request, jsonify, render_template, send_file, url_for
except ImportError as e:
    print("\n" + "=" * 65, flush=True)
    print("  [ERROR] Python 依赖库未安装或不完整 / Missing required libraries!", flush=True)
    print(f"  详细错误: {e}", flush=True)
    print("-----------------------------------------------------------------", flush=True)
    print("  请在当前目录下打开 CMD / PowerShell 运行以下命令安装依赖：", flush=True)
    print("  python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple", flush=True)
    print("=" * 65 + "\n", flush=True)
    try:
        input("按任意键退出 / Press Enter to exit...")
    except Exception:
        pass
    sys.exit(1)

# Probe C extensions before importing core.* modules
_NATIVE_PROBE_RESULTS = _probe_native_modules()

if not (_NATIVE_PROBE_RESULTS.get("PIL", True) and _NATIVE_PROBE_RESULTS.get("fitz", True)):
    print("\n" + "=" * 65, flush=True)
    print("  [ERROR] 核心 PDF/图像引擎 (PyMuPDF / Pillow) 未能加载或发生硬件指令冲突!", flush=True)
    print("  [FIX]   请在当前目录下打开 CMD 运行以下命令修复依赖：", flush=True)
    print("  python -m pip install --upgrade --force-reinstall pymupdf Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple", flush=True)
    print("=" * 65 + "\n", flush=True)
    try:
        input("按任意键退出 / Press Enter to exit...")
    except Exception:
        pass
    sys.exit(1)

try:
    from core.converter import convert_to_pdf
    from core.ink_saver import generate_page_preview, process_pdf_document
    from core.printer_dispatcher import check_printer_connectivity, dispatch_print_job
    from core.telemetry import log_print_job, get_telemetry_stats, get_student_ads, add_student_ad, ensure_telemetry_setup
except ImportError as e:
    print("\n" + "=" * 65, flush=True)
    print("  [ERROR] 缺少核心图像/PDF处理库 (PyMuPDF / Pillow)!", flush=True)
    print(f"  详细错误: {e}", flush=True)
    print("-----------------------------------------------------------------", flush=True)
    print("  请运行: python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple", flush=True)
    print("=" * 65 + "\n", flush=True)
    try:
        input("按任意键退出 / Press Enter to exit...")
    except Exception:
        pass
    sys.exit(1)

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static")
)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB max upload
SPOOL_DIR = BASE_DIR / "spool"
SPOOL_DIR.mkdir(parents=True, exist_ok=True)
ensure_telemetry_setup()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def parse_bool(val, default: bool = False) -> bool:
    """Robust parser for booleans from JSON / query strings."""
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        s = val.strip().lower()
        if s in ("true", "1", "yes", "on"):
            return True
        if s in ("false", "0", "no", "off", ""):
            return False
    return bool(val)


def is_valid_lan_ip(ip: str) -> bool:
    """Check if an IPv4 address is a valid, reachable physical LAN address."""
    if not ip or not isinstance(ip, str):
        return False
    ip = ip.strip()
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    for p in parts:
        if not p.isdigit() or not (0 <= int(p) <= 255):
            return False
    # Avoid loopback, APIPA link-local, VPN/tunnel clash ranges, and zero IP
    if ip.startswith("127.") or ip.startswith("169.254.") or ip.startswith("198.18.") or ip.startswith("0."):
        return False
    return True


def get_local_ip(target_hint: str = "172.16.4.9") -> str:
    """
    Retrieve machine's primary local IP for network devices (iPad, other laptops).
    Prioritizes real physical LAN adapters (Wi-Fi/Ethernet) and avoids virtual/VPN tunnel adapters.
    """
    import subprocess
    import re

    # 1. On macOS, query active physical Wi-Fi / Ethernet interface (en0, en1, en2, en3, en4)
    if sys.platform == "darwin":
        for iface in ["en0", "en1", "en2", "en3", "en4"]:
            try:
                res = subprocess.run(["ipconfig", "getifaddr", iface], stdout=subprocess.PIPE, text=True, timeout=1)
                ip = res.stdout.strip()
                if is_valid_lan_ip(ip):
                    return ip
            except Exception:
                pass

    # 2. On Windows, parse ipconfig for active Wi-Fi / Ethernet IPv4 address (English & Multilingual)
    if sys.platform == "win32":
        try:
            res = subprocess.run(["ipconfig"], stdout=subprocess.PIPE, timeout=2)
            # Safely decode with mbcs/gbk or fallback to utf-8, avoiding UnicodeDecodeError
            try:
                stdout_text = res.stdout.decode("mbcs", errors="replace")
            except Exception:
                stdout_text = res.stdout.decode("utf-8", errors="replace")
            # Matches both English ('IPv4 Address . . . : 192.168.x.x') and Chinese ('IPv4 地址 . . . : 192.168.x.x')
            matches = re.findall(r"(?:IPv4 Address|IPv4 地址|IPv4|IP Address)[^\r\n:]*:\s*([\d\.]+)", stdout_text, re.IGNORECASE)
            for cand in matches:
                cand = cand.strip()
                if is_valid_lan_ip(cand):
                    return cand
        except Exception:
            pass

    # 3. Inspect active network interfaces via socket route to printer target
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((target_hint, 80))
        ip = s.getsockname()[0]
        s.close()
        if is_valid_lan_ip(ip):
            return ip
    except Exception:
        pass

    # 4. Fallback to connecting towards common DNS / gateway routes
    for gateway_cand in ["8.8.8.8", "1.1.1.1", "192.168.1.1", "10.0.0.1", "172.16.0.1"]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((gateway_cand, 80))
            ip = s.getsockname()[0]
            s.close()
            if is_valid_lan_ip(ip):
                return ip
        except Exception:
            pass

    # 5. Hostname fallback / address enumeration
    try:
        host_ip = socket.gethostbyname(socket.gethostname())
        if is_valid_lan_ip(host_ip):
            return host_ip
    except Exception:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            cand = info[4][0]
            if is_valid_lan_ip(cand):
                return cand
    except Exception:
        pass

    return "127.0.0.1"




@app.route("/")
def index():
    """Render Apple-minimalist student print dashboard."""
    local_ip = get_local_ip()
    host_header = request.host or ""
    if ":" in host_header:
        port = host_header.split(":")[1]
    else:
        port = request.environ.get("SERVER_PORT", os.environ.get("PORT", 5000))
    return render_template("index.html", local_ip=local_ip, port=port)


@app.route("/api/network_info", methods=["GET"])
def network_info():
    """Return local IP and network portal access URL for mobile/iPad devices."""
    local_ip = get_local_ip()
    host_header = request.host or ""
    if ":" in host_header:
        port = host_header.split(":")[1]
    else:
        port = request.environ.get("SERVER_PORT", os.environ.get("PORT", 5000))
    return jsonify({
        "local_ip": local_ip,
        "port": port,
        "portal_url": f"http://{local_ip}:{port}",
        "localhost_url": f"http://localhost:{port}"
    })


@app.route("/api/printer_status", methods=["GET"])
def printer_status():
    """Check connectivity to printer (defaults to 172.16.4.9)."""
    ip = request.args.get("ip", "172.16.4.9").strip()
    status = check_printer_connectivity(ip=ip)
    return jsonify(status)


@app.route("/api/stats", methods=["GET"])
def telemetry_stats():
    """Return aggregated paper, ink, and tree savings."""
    stats = get_telemetry_stats()
    return jsonify(stats)


@app.route("/api/ads", methods=["GET", "POST"])
def ads_endpoint():
    """Get active student ads or submit a new one."""
    if request.method == "POST":
        data = request.get_json() or {}
        title = data.get("title", "").strip()
        tagline = data.get("tagline", "").strip()
        desc = data.get("desc", "").strip()
        contact = data.get("contact", "").strip()
        badge = data.get("badge", "Student Club").strip()
        if not title:
            return jsonify({"error": "Title is required"}), 400
        new_ad = add_student_ad(title, tagline, desc, contact, badge)
        return jsonify(new_ad)
    return jsonify(get_student_ads())


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """
    Handle document upload (single or multiple files).
    Accepts: PDF, DOCX, PPTX, PAGES, PNG, JPG, WEBP, TXT.
    Converts documents to PDF and generates first page preview.
    """
    file_objs = request.files.getlist("files") or request.files.getlist("file")
    if not file_objs or not file_objs[0] or not file_objs[0].filename:
        return jsonify({"error": "No file uploaded"}), 400

    docs = []
    import fitz

    for uploaded in file_objs:
        if not uploaded or not uploaded.filename:
            continue
        orig_filename = uploaded.filename
        doc_id = str(uuid.uuid4())[:12]
        ext = Path(orig_filename).suffix.lower()

        saved_input_path = SPOOL_DIR / f"{doc_id}_orig{ext}"
        uploaded.save(str(saved_input_path))

        converted_pdf_path = SPOOL_DIR / f"{doc_id}_converted.pdf"

        try:
            convert_to_pdf(str(saved_input_path), str(converted_pdf_path))
        except Exception as e:
            app.logger.error(f"Conversion error for {orig_filename}: {e}")
            return jsonify({"error": f"Failed to convert {orig_filename} to PDF: {str(e)}"}), 422

        # Get page count & file size
        try:
            doc = fitz.open(str(converted_pdf_path))
            total_pages = len(doc)
            doc.close()
        except Exception as e:
            return jsonify({"error": f"Invalid PDF output: {e}"}), 422

        file_size_bytes = os.path.getsize(str(converted_pdf_path))
        if file_size_bytes > 1024 * 1024:
            size_str = f"{file_size_bytes / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{max(1, file_size_bytes // 1024)} KB"

        # Generate initial preview with default eco mode
        preview_data = generate_page_preview(str(converted_pdf_path), page_num=0, mode="eco")

        docs.append({
            "doc_id": doc_id,
            "filename": orig_filename,
            "clean_title": Path(orig_filename).stem,
            "total_pages": total_pages,
            "file_size": size_str,
            "preview": preview_data
        })

    if not docs:
        return jsonify({"error": "No valid documents processed"}), 400

    primary = docs[0]
    return jsonify({
        "success": True,
        "doc_id": primary["doc_id"],
        "filename": primary["filename"],
        "clean_title": primary["clean_title"],
        "total_pages": primary["total_pages"],
        "file_size": primary["file_size"],
        "preview": primary["preview"],
        "docs": docs
    })


@app.route("/api/thumbnail/<doc_id>/<int:page>", methods=["GET"])
def get_page_thumbnail(doc_id, page):
    """
    Renders high-speed thumbnail of a specific page for the Apple-style sidebar gallery.
    """
    pdf_path = SPOOL_DIR / f"{doc_id}_converted.pdf"
    if not pdf_path.exists():
        return jsonify({"error": "Document not found or expired"}), 404

    import fitz
    try:
        doc = fitz.open(str(pdf_path))
        if page < 1 or page > len(doc):
            doc.close()
            return jsonify({"error": "Page out of range"}), 400
        p = doc[page - 1]
        rect = p.rect
        scale = 260.0 / max(rect.width, rect.height, 1)
        pix = p.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        img_bytes = pix.tobytes("jpeg")
        doc.close()
        response = send_file(io.BytesIO(img_bytes), mimetype="image/jpeg")
        response.headers["Cache-Control"] = "public, max-age=3600"
        return response
    except Exception as e:
        app.logger.error(f"Thumbnail error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/preview", methods=["POST"])
def preview_page():
    """
    Generate instant before/after preview for a specific page and ink-saving mode.
    Supports inverse color.
    """
    data = request.get_json() or {}
    doc_id = data.get("doc_id")
    page_num = int(data.get("page", 1)) - 1
    mode = data.get("mode", "eco")
    invert_color = parse_bool(data.get("invert_color", False))

    pdf_path = SPOOL_DIR / f"{doc_id}_converted.pdf"
    if not pdf_path.exists():
        return jsonify({"error": "Document not found or expired"}), 404

    try:
        preview = generate_page_preview(str(pdf_path), page_num=page_num, mode=mode, invert_color=invert_color)
        return jsonify(preview)
    except Exception as e:
        app.logger.error(f"Preview error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/print", methods=["POST"])
def print_document():
    """
    Process document with selected ink mode, page range, duplex, binding edge,
    collate, color inversion, and N-up layout, then dispatch directly to printer.
    """
    data = request.get_json() or {}
    doc_id = data.get("doc_id")
    student_name = (data.get("student_name") or "Student").strip()
    job_name = (data.get("job_name") or "Document.pdf").strip()
    ink_mode = data.get("ink_mode", "eco")
    page_range = data.get("page_range", "all")
    duplex = parse_bool(data.get("duplex", True), default=True)  # Default is Duplex ON
    copies = max(1, min(int(data.get("copies", 1)), 50))
    printer_ip = (data.get("printer_ip") or "172.16.4.9").strip()
    protocol = data.get("protocol", "auto")
    binding = (data.get("binding") or "long").strip().lower()
    collate = parse_bool(data.get("collate", True), default=True)
    invert_color = parse_bool(data.get("invert_color", False), default=False)
    nup = int(data.get("nup", 1))

    input_pdf = SPOOL_DIR / f"{doc_id}_converted.pdf"
    if not input_pdf.exists():
        return jsonify({"error": "Document not found"}), 404

    output_pdf = SPOOL_DIR / f"{doc_id}_{ink_mode}_print.pdf"

    # 1. Process PDF with selected ink-saving mode & layout
    try:
        process_res = process_pdf_document(
            str(input_pdf),
            str(output_pdf),
            mode=ink_mode,
            page_range_str=page_range,
            dpi=180,
            invert_color=invert_color,
            nup=nup
        )
    except Exception as e:
        app.logger.error(f"Processing error: {e}")
        return jsonify({"error": f"Ink processing failed: {str(e)}"}), 500

    # 2. Dispatch to printer
    dispatch_res = dispatch_print_job(
        str(output_pdf),
        student_name=student_name,
        job_name=job_name,
        duplex=duplex,
        copies=copies,
        printer_ip=printer_ip,
        preferred_protocol=protocol,
        binding=binding,
        collate=collate
    )

    # 3. Telemetry log
    status_label = "Sent to Hold Queue" if dispatch_res.get("success") else "Failed / Spooled"
    log_info = log_print_job(
        student_name=student_name,
        job_name=job_name,
        file_type=Path(job_name).suffix.replace(".", "") or "pdf",
        total_pages=process_res["input_pages"],
        printed_pages=process_res["printed_pages"],
        duplex=duplex,
        ink_mode=ink_mode,
        ink_saved_pct=process_res["avg_ink_saved_pct"],
        est_ink_saved_ml=process_res["est_ink_saved_ml"],
        status=status_label
    )

    return jsonify({
        "success": dispatch_res.get("success", False),
        "dispatch": dispatch_res,
        "metrics": process_res,
        "log": log_info,
        "student_name": student_name,
        "job_name": job_name,
        "duplex": duplex,
        "binding": binding,
        "collate": collate,
        "nup": nup,
        "invert_color": invert_color,
        "hold_queue_tip": f"Go to Canon printer screen ({printer_ip}), find '{student_name}', and press Start to release your print."
    })


@app.route("/api/batch_print", methods=["POST"])
def batch_print():
    """
    Print multiple documents in a single queue request.
    """
    data = request.get_json() or {}
    jobs = data.get("jobs", [])
    if not jobs:
        return jsonify({"error": "No print jobs specified"}), 400

    results = []
    for item in jobs:
        doc_id = item.get("doc_id")
        student_name = (item.get("student_name") or "Student").strip()
        job_name = (item.get("job_name") or "Document.pdf").strip()
        ink_mode = item.get("ink_mode", "eco")
        page_range = item.get("page_range", "all")
        duplex = parse_bool(item.get("duplex", True), default=True)
        copies = max(1, min(int(item.get("copies", 1)), 50))
        printer_ip = (item.get("printer_ip") or "172.16.4.9").strip()
        protocol = item.get("protocol", "auto")
        binding = (item.get("binding") or "long").strip().lower()
        collate = parse_bool(item.get("collate", True), default=True)
        invert_color = parse_bool(item.get("invert_color", False), default=False)
        nup = int(item.get("nup", 1))

        input_pdf = SPOOL_DIR / f"{doc_id}_converted.pdf"
        if not input_pdf.exists():
            results.append({"doc_id": doc_id, "success": False, "error": "Document not found"})
            continue

        output_pdf = SPOOL_DIR / f"{doc_id}_{ink_mode}_batch_print.pdf"
        try:
            process_res = process_pdf_document(
                str(input_pdf),
                str(output_pdf),
                mode=ink_mode,
                page_range_str=page_range,
                dpi=180,
                invert_color=invert_color,
                nup=nup
            )
            dispatch_res = dispatch_print_job(
                str(output_pdf),
                student_name=student_name,
                job_name=job_name,
                duplex=duplex,
                copies=copies,
                printer_ip=printer_ip,
                preferred_protocol=protocol,
                binding=binding,
                collate=collate
            )
            log_print_job(
                student_name=student_name,
                job_name=job_name,
                file_type=Path(job_name).suffix.replace(".", "") or "pdf",
                total_pages=process_res["input_pages"],
                printed_pages=process_res["printed_pages"],
                duplex=duplex,
                ink_mode=ink_mode,
                ink_saved_pct=process_res["avg_ink_saved_pct"],
                est_ink_saved_ml=process_res["est_ink_saved_ml"],
                status="Sent to Hold Queue" if dispatch_res.get("success") else "Failed / Spooled"
            )
            results.append({
                "doc_id": doc_id,
                "job_name": job_name,
                "success": dispatch_res.get("success", False),
                "dispatch": dispatch_res,
                "metrics": process_res
            })
        except Exception as e:
            results.append({"doc_id": doc_id, "success": False, "error": str(e)})

    return jsonify({
        "success": all(r.get("success", False) for r in results),
        "total_jobs": len(jobs),
        "results": results
    })


@app.route("/api/download", methods=["POST"])
def download_document():
    """
    Process PDF with ink-saver engine and return directly as a downloadable file.
    """
    data = request.get_json() or {}
    doc_id = data.get("doc_id")
    ink_mode = data.get("ink_mode", "eco")
    page_range = data.get("page_range", "all")
    clean_name = data.get("clean_name", "document")
    invert_color = parse_bool(data.get("invert_color", False), default=False)
    nup = int(data.get("nup", 1))

    input_pdf = SPOOL_DIR / f"{doc_id}_converted.pdf"
    if not input_pdf.exists():
        return jsonify({"error": "Document not found"}), 404

    output_pdf = SPOOL_DIR / f"{doc_id}_{ink_mode}_download.pdf"

    process_pdf_document(
        str(input_pdf),
        str(output_pdf),
        mode=ink_mode,
        page_range_str=page_range,
        dpi=180,
        invert_color=invert_color,
        nup=nup
    )

    download_filename = f"{clean_name}_{ink_mode}_inkyard.pdf"
    return send_file(
        str(output_pdf),
        as_attachment=True,
        download_name=download_filename,
        mimetype="application/pdf"
    )


def find_available_port(preferred_port: int = 5000) -> int:
    """
    Find an open port, gracefully handling macOS AirPlay Receiver on port 5000
    and avoiding Windows SO_REUSEADDR port-hijacking conflicts.
    """
    raw_candidates = [preferred_port, 5000, 5050, 8080, 8000, 3000]
    candidates = []
    for c in raw_candidates:
        if c not in candidates:
            candidates.append(c)

    for p in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if sys.platform == "win32":
                excl_opt = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
                if excl_opt is not None:
                    try:
                        s.setsockopt(socket.SOL_SOCKET, excl_opt, 1)
                    except OSError:
                        pass
            else:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", p))
                return p
            except OSError:
                continue
    return preferred_port


def start_server(host="0.0.0.0", port=None):
    """Entrypoint to run the server."""
    if port is None:
        env_port = os.environ.get("PORT")
        if env_port:
            port = int(env_port)
        else:
            port = find_available_port(5000)
    os.environ["PORT"] = str(port)

    local_ip = get_local_ip()
    print("=" * 65, flush=True)
    print("  [InkYard - Apple Style Local Print Portal]", flush=True)
    print(f"  * Local access:    http://localhost:{port}", flush=True)
    print(f"  * Network access:  http://{local_ip}:{port} (iPad / Phone / Laptops)", flush=True)
    print(f"  * NOTE: Always include ':{port}' in browser URL (not bare 'localhost')", flush=True)
    print(f"  * Default Printer: Canon Multifunction @ 172.16.4.9", flush=True)
    print("=" * 65, flush=True)

    if sys.platform == "win32" and os.environ.get("INKYARD_NO_BROWSER") != "1":
        def _open_portal():
            try:
                webbrowser.open(f"http://localhost:{port}")
            except Exception:
                pass
        timer = threading.Timer(1.5, _open_portal)
        timer.daemon = True
        timer.start()

    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    try:
        start_server(host="0.0.0.0")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] 服务启动异常 / Server failed to start: {e}", flush=True)
        try:
            input("按任意键退出 / Press Enter to exit...")
        except Exception:
            pass
        sys.exit(1)

