import os
import io
import unittest
import fitz
from pathlib import Path
from server import app

class TestServerAPI(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_index_route(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"InkYard", res.data)
        self.assertIn(b"easterEggModal", res.data)
        self.assertIn(b"signature.png", res.data)
        self.assertIn(b"qrcode.min.js", res.data)
        self.assertIn(b"Double-Sided", res.data)

    def test_printer_status_endpoint(self):
        res = self.client.get("/api/printer_status?ip=127.0.0.1")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("online", data)

    def test_stats_endpoint(self):
        res = self.client.get("/api/stats")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("total_jobs", data)
        self.assertIn("total_sheets_saved", data)

    def test_ads_endpoints(self):
        # GET ads
        res = self.client.get("/api/ads")
        self.assertEqual(res.status_code, 200)
        ads = res.get_json()
        self.assertIsInstance(ads, list)

        # POST new ad
        new_ad = {
            "title": "Debate Club",
            "tagline": "Speak up",
            "desc": "Join us on Wednesdays",
            "contact": "@debate",
            "badge": "Club"
        }
        res_post = self.client.post("/api/ads", json=new_ad)
        self.assertEqual(res_post.status_code, 200)
        created = res_post.get_json()
        self.assertEqual(created["title"], "Debate Club")

    def test_upload_and_preview_workflow(self):
        # Create a test PDF in memory
        doc = fitz.open()
        p = doc.new_page(width=500, height=700)
        p.insert_text((50, 100), "API Test PDF Page 1", fontsize=18)
        p = doc.new_page(width=500, height=700)
        p.insert_text((50, 100), "API Test PDF Page 2", fontsize=18)
        pdf_bytes = doc.tobytes()
        doc.close()

        # 1. Upload
        data = {
            "file": (io.BytesIO(pdf_bytes), "test_doc.pdf")
        }
        res_up = self.client.post("/api/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res_up.status_code, 200)
        up_data = res_up.get_json()
        self.assertTrue(up_data["success"])
        self.assertEqual(up_data["total_pages"], 2)
        doc_id = up_data["doc_id"]

        # 2. Preview
        preview_req = {
            "doc_id": doc_id,
            "page": 2,
            "mode": "matrix"
        }
        res_prev = self.client.post("/api/preview", json=preview_req)
        self.assertEqual(res_prev.status_code, 200)
        prev_data = res_prev.get_json()
        self.assertEqual(prev_data["page"], 2)
        self.assertTrue(prev_data["proc_b64"].startswith("data:image/jpeg;base64,"))

        # 3. Print (with mock protocol for test stability)
        print_req = {
            "doc_id": doc_id,
            "student_name": "TestStudent",
            "job_name": "test_doc.pdf",
            "ink_mode": "matrix",
            "page_range": "1-2",
            "duplex": True,
            "copies": 1,
            "protocol": "mock"
        }
        res_print = self.client.post("/api/print", json=print_req)
        self.assertEqual(res_print.status_code, 200)
        print_data = res_print.get_json()
        self.assertTrue(print_data["success"])
        self.assertEqual(print_data["student_name"], "TestStudent")
        self.assertTrue(print_data["duplex"])

        # 4. Download
        dl_req = {
            "doc_id": doc_id,
            "ink_mode": "matrix",
            "page_range": "1",
            "clean_name": "test_doc"
        }
        res_dl = self.client.post("/api/download", json=dl_req)
        self.assertEqual(res_dl.status_code, 200)
        self.assertEqual(res_dl.mimetype, "application/pdf")
        self.assertGreater(len(res_dl.data), 100)
        res_dl.close()

    def test_upload_png_and_eco_mode_preview(self):
        from PIL import Image
        import numpy as np
        # Create a test PNG image (landscape 1600x900)
        im = Image.new("RGB", (1600, 900), (255, 200, 150))
        png_buf = io.BytesIO()
        im.save(png_buf, format="PNG")
        png_bytes = png_buf.getvalue()

        # 1. Upload PNG
        data = {
            "file": (io.BytesIO(png_bytes), "sample_photo.png")
        }
        res_up = self.client.post("/api/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res_up.status_code, 200)
        up_data = res_up.get_json()
        self.assertTrue(up_data["success"])
        self.assertEqual(up_data["total_pages"], 1)
        doc_id = up_data["doc_id"]

        # 2. Preview in Eco Mode
        preview_req = {
            "doc_id": doc_id,
            "page": 1,
            "mode": "eco"
        }
        res_prev = self.client.post("/api/preview", json=preview_req)
        self.assertEqual(res_prev.status_code, 200)
        prev_data = res_prev.get_json()
        self.assertEqual(prev_data["mode"], "eco")
        self.assertTrue(prev_data["proc_b64"].startswith("data:image/jpeg;base64,"))
        self.assertGreater(prev_data["ink_saved_pct"], 0.0)

    def test_upload_sample_pages_multipage(self):
        sample_path = "spool/c832b1b2-40d_orig.pages"
        if os.path.exists(sample_path) and os.path.exists("/usr/bin/qlmanage"):
            with open(sample_path, "rb") as f:
                pages_bytes = f.read()
            data = {
                "file": (io.BytesIO(pages_bytes), "class_reading.pages")
            }
            res_up = self.client.post("/api/upload", data=data, content_type="multipart/form-data")
            self.assertEqual(res_up.status_code, 200)
            up_data = res_up.get_json()
            self.assertTrue(up_data["success"])
            # Must convert all 6 pages, not just 1
            self.assertEqual(up_data["total_pages"], 6)

    def test_thumbnail_endpoint(self):
        doc = fitz.open()
        p = doc.new_page(width=400, height=500)
        p.insert_text((40, 80), "Thumbnail Test")
        pdf_bytes = doc.tobytes()
        doc.close()

        data = {"file": (io.BytesIO(pdf_bytes), "thumb_doc.pdf")}
        res_up = self.client.post("/api/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res_up.status_code, 200)
        doc_id = res_up.get_json()["doc_id"]

        res_thumb = self.client.get(f"/api/thumbnail/{doc_id}/1")
        self.assertEqual(res_thumb.status_code, 200)
        self.assertEqual(res_thumb.mimetype, "image/jpeg")
        self.assertGreater(len(res_thumb.data), 100)

        # Boundary tests: page 0, page 99, nonexistent doc
        res_zero = self.client.get(f"/api/thumbnail/{doc_id}/0")
        self.assertEqual(res_zero.status_code, 400)
        res_oob = self.client.get(f"/api/thumbnail/{doc_id}/99")
        self.assertEqual(res_oob.status_code, 400)
        res_nodoc = self.client.get("/api/thumbnail/nonexistent_123/1")
        self.assertEqual(res_nodoc.status_code, 404)

    def test_multi_file_upload_and_batch_print(self):
        # Create two test PDFs
        doc1 = fitz.open()
        doc1.new_page().insert_text((50, 50), "Batch Doc 1")
        b1 = doc1.tobytes()
        doc1.close()

        doc2 = fitz.open()
        doc2.new_page().insert_text((50, 50), "Batch Doc 2")
        b2 = doc2.tobytes()
        doc2.close()

        data = {
            "files": [
                (io.BytesIO(b1), "doc1.pdf"),
                (io.BytesIO(b2), "doc2.pdf")
            ]
        }
        res_up = self.client.post("/api/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res_up.status_code, 200)
        data_up = res_up.get_json()
        self.assertTrue(data_up["success"])
        self.assertIn("docs", data_up)
        self.assertEqual(len(data_up["docs"]), 2)

        # Batch print
        batch_req = {
            "jobs": [
                {
                    "doc_id": data_up["docs"][0]["doc_id"],
                    "student_name": "Student A",
                    "job_name": "doc1.pdf",
                    "protocol": "mock"
                },
                {
                    "doc_id": data_up["docs"][1]["doc_id"],
                    "student_name": "Student A",
                    "job_name": "doc2.pdf",
                    "protocol": "mock"
                }
            ]
        }
        res_bp = self.client.post("/api/batch_print", json=batch_req)
        self.assertEqual(res_bp.status_code, 200)
        bp_data = res_bp.get_json()
        self.assertTrue(bp_data["success"])
        self.assertEqual(bp_data["total_jobs"], 2)

    def test_advanced_print_parameters(self):
        doc = fitz.open()
        doc.new_page().insert_text((50, 50), "Advanced Print Page 1")
        doc.new_page().insert_text((50, 50), "Advanced Print Page 2")
        pdf_bytes = doc.tobytes()
        doc.close()

        res_up = self.client.post("/api/upload", data={"file": (io.BytesIO(pdf_bytes), "adv.pdf")}, content_type="multipart/form-data")
        doc_id = res_up.get_json()["doc_id"]

        print_req = {
            "doc_id": doc_id,
            "student_name": "Alice",
            "job_name": "adv.pdf",
            "ink_mode": "eco",
            "page_range": "all",
            "duplex": True,
            "copies": 2,
            "binding": "short",
            "collate": False,
            "invert_color": True,
            "nup": 2,
            "protocol": "mock"
        }
        res_print = self.client.post("/api/print", json=print_req)
        self.assertEqual(res_print.status_code, 200)
        p_data = res_print.get_json()
        self.assertTrue(p_data["success"])
        self.assertEqual(p_data["binding"], "short")
        self.assertFalse(p_data["collate"])
        self.assertTrue(p_data["invert_color"])
        self.assertEqual(p_data["nup"], 2)

    def test_network_info_endpoint(self):
        res = self.client.get("/api/network_info")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("local_ip", data)
        self.assertIn("portal_url", data)
        self.assertTrue(data["portal_url"].startswith("http://"))

    def test_default_mode_eco_across_endpoints(self):
        # 1. Index page has eco mode active
        res_index = self.client.get("/")
        self.assertEqual(res_index.status_code, 200)
        self.assertIn(b'mode-card active" data-mode="eco"', res_index.data)
        self.assertNotIn(b'mode-card active" data-mode="matrix"', res_index.data)

        # 2. Upload defaults to eco preview
        doc = fitz.open()
        doc.new_page().insert_text((50, 50), "Test Document Page")
        pdf_bytes = doc.tobytes()
        doc.close()

        data = {"file": (io.BytesIO(pdf_bytes), "eco_test.pdf")}
        res_up = self.client.post("/api/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res_up.status_code, 200)
        up_data = res_up.get_json()
        self.assertEqual(up_data["preview"]["mode"], "eco")
        doc_id = up_data["doc_id"]

        # 3. Preview without explicit mode defaults to eco
        res_prev = self.client.post("/api/preview", json={"doc_id": doc_id, "page": 1})
        self.assertEqual(res_prev.status_code, 200)
        self.assertEqual(res_prev.get_json()["mode"], "eco")

        # 4. Preview with invert_color on white doc protects against black toner
        res_inv = self.client.post("/api/preview", json={"doc_id": doc_id, "page": 1, "invert_color": True})
        self.assertEqual(res_inv.status_code, 200)
        inv_data = res_inv.get_json()
        self.assertTrue(inv_data["invert_color"])
        # proc_ink_density must stay low, not turn into solid black
        self.assertLess(inv_data["proc_ink_density"], 10.0)

        # 5. Print without explicit ink_mode defaults to eco
        res_print = self.client.post("/api/print", json={"doc_id": doc_id, "protocol": "mock"})
        self.assertEqual(res_print.status_code, 200)
        self.assertEqual(res_print.get_json()["metrics"]["mode"], "eco")

    def test_parse_bool_string_robustness(self):
        doc = fitz.open()
        doc.new_page().insert_text((50, 50), "Test Document")
        pdf_bytes = doc.tobytes()
        doc.close()

        data = {"file": (io.BytesIO(pdf_bytes), "bool_test.pdf")}
        res_up = self.client.post("/api/upload", data=data, content_type="multipart/form-data")
        doc_id = res_up.get_json()["doc_id"]

        # String "false" for invert_color must NOT evaluate to True
        res_prev = self.client.post("/api/preview", json={"doc_id": doc_id, "page": 1, "invert_color": "false"})
        self.assertEqual(res_prev.status_code, 200)
        self.assertFalse(res_prev.get_json()["invert_color"])

        # String "0" must evaluate to False
        res_prev0 = self.client.post("/api/preview", json={"doc_id": doc_id, "page": 1, "invert_color": "0"})
        self.assertEqual(res_prev0.status_code, 200)
        self.assertFalse(res_prev0.get_json()["invert_color"])

        # String "true" must evaluate to True
        res_prev1 = self.client.post("/api/preview", json={"doc_id": doc_id, "page": 1, "invert_color": "true"})
        self.assertEqual(res_prev1.status_code, 200)
        self.assertTrue(res_prev1.get_json()["invert_color"])

    def test_lan_ip_validator(self):
        from server import is_valid_lan_ip
        self.assertFalse(is_valid_lan_ip("127.0.0.1"))
        self.assertFalse(is_valid_lan_ip("198.18.0.1"))
        self.assertFalse(is_valid_lan_ip("169.254.1.1"))
        self.assertFalse(is_valid_lan_ip("0.0.0.0"))
        self.assertFalse(is_valid_lan_ip(""))
        self.assertFalse(is_valid_lan_ip(None))
        self.assertFalse(is_valid_lan_ip("abc.def.ghi.jkl"))
        self.assertFalse(is_valid_lan_ip("192.168.1.999"))
        self.assertFalse(is_valid_lan_ip("192.168.1"))
        self.assertTrue(is_valid_lan_ip("192.168.1.100"))
        self.assertTrue(is_valid_lan_ip("172.16.4.50"))
        self.assertTrue(is_valid_lan_ip("10.0.0.25"))

    def test_qr_css_quiet_zone_and_no_forced_block(self):
        css_path = Path(__file__).resolve().parent.parent / "static" / "css" / "apple_style.css"
        css_text = css_path.read_text(encoding="utf-8")
        # Ensure display: block !important is NOT present on .qr-canvas-box canvas/img (which causes dual-render bug)
        self.assertNotIn(".qr-canvas-box canvas, .qr-canvas-box img {\n  display: block !important;", css_text)
        # Ensure display none rule exists for hidden canvas or img
        self.assertIn('.qr-canvas-box canvas[style*="none"]', css_text)
        # Ensure pure white background on qr-wrapper and qr-canvas-box for quiet zone
        self.assertIn(".qr-wrapper {", css_text)
        self.assertIn(".qr-canvas-box {", css_text)

    def test_windows_package_exists(self):
        from pathlib import Path
        import zipfile
        base_dir = Path(__file__).resolve().parent.parent
        for pkg_name in ["InkYard_Windows10.zip"]:
            pkg_path = base_dir / pkg_name
            self.assertTrue(pkg_path.exists(), f"Missing package: {pkg_name}")
            with zipfile.ZipFile(pkg_path, "r") as zf:
                names = zf.namelist()
                self.assertIn("InkYard/server.py", names)
                self.assertIn("InkYard/run_server.bat", names)
                self.assertIn("InkYard/run_server_windows.bat", names)
                self.assertIn("InkYard/install_python.bat", names)
                self.assertIn("InkYard/deploy_seewo.bat", names)
                self.assertIn("InkYard/setup_windows.ps1", names)
                self.assertIn("InkYard/static/js/qrcode.min.js", names)
                self.assertIn("InkYard/static/images/signature.png", names)

                # Ensure Windows scripts inside the zip have CRLF and are pure ASCII
                for script_name in [
                    "InkYard/run_server.bat",
                    "InkYard/run_server_windows.bat",
                    "InkYard/install_python.bat",
                    "InkYard/deploy_seewo.bat",
                    "InkYard/setup_windows.ps1"
                ]:
                    content = zf.read(script_name)
                    self.assertTrue(b"\r\n" in content, f"{script_name} must contain CRLF in {pkg_name}")
                    self.assertEqual(
                        content.replace(b"\r\n", b"").count(b"\n"),
                        0,
                        f"{script_name} contains bare LF line endings in {pkg_name}"
                    )
                    self.assertTrue(content.isascii(), f"{script_name} must be pure ASCII in {pkg_name}")

    def test_windows_batch_scripts_crlf_and_ascii(self):
        """Verify on-disk Windows scripts strictly adhere to pure ASCII and Windows CRLF."""
        from pathlib import Path
        base_dir = Path(__file__).resolve().parent.parent
        scripts = [
            "run_server.bat",
            "run_server_windows.bat",
            "install_python.bat",
            "deploy_seewo.bat",
            "setup_windows.ps1"
        ]

        for s in scripts:
            p = base_dir / s
            self.assertTrue(p.exists(), f"File {s} does not exist")
            raw = p.read_bytes()
            # 1. Pure ASCII (cmd.exe in Chinese Windows GBK mode corrupts on multi-byte UTF-8)
            self.assertTrue(raw.isascii(), f"{s} contains non-ASCII characters or emojis")
            # 2. Windows CRLF (\r\n) line endings (Unix LF causes cmd.exe seek desynchronization)
            self.assertTrue(b"\r\n" in raw, f"{s} must contain CRLF")
            self.assertEqual(raw.replace(b"\r\n", b"").count(b"\n"), 0, f"{s} has bare LF line endings")

    def test_windows_batch_script_robustness(self):
        """Verify Windows batch scripts use proper cmd syntax, avoid negative errorlevel bugs, and pin safe versions."""
        from pathlib import Path
        base_dir = Path(__file__).resolve().parent.parent
        run_bat = (base_dir / "run_server_windows.bat").read_text(encoding="ascii")
        run_simple_bat = (base_dir / "run_server.bat").read_text(encoding="ascii")
        install_bat = (base_dir / "install_python.bat").read_text(encoding="ascii")
        deploy_bat = (base_dir / "deploy_seewo.bat").read_text(encoding="ascii")
        reqs = (base_dir / "requirements.txt").read_text(encoding="utf-8")

        # 1. Must set UTF-8 code page (chcp 65001) and delayed expansion
        for bat_name, bat_text in [
            ("run_server.bat", run_simple_bat),
            ("run_server_windows.bat", run_bat),
            ("install_python.bat", install_bat),
            ("deploy_seewo.bat", deploy_bat),
        ]:
            self.assertIn("@chcp 65001 >nul", bat_text, f"{bat_name} missing chcp 65001")
            self.assertIn("setlocal enabledelayedexpansion", bat_text, f"{bat_name} missing enabledelayedexpansion")
            # Must NEVER use 'errorlevel 1' which fails on negative NTSTATUS crash codes (-1073741795 / 0xC000001D)
            self.assertNotIn("errorlevel 1", bat_text.lower(), f"{bat_name} contains unsafe 'errorlevel 1' check")
            self.assertIn("!errorlevel!", bat_text, f"{bat_name} must check !errorlevel!")

        # 2. Must set UTF-8 environment variables for Python
        self.assertIn('set "PYTHONIOENCODING=utf-8"', run_bat)
        self.assertIn('set "PYTHONUTF8=1"', run_bat)

        # 3. Must use for /d for directory iteration (never dir /b /ad with wildcards which enters directories)
        self.assertNotIn('dir /b /ad', run_bat)
        self.assertIn('for /d %%D in ("%LOCALAPPDATA%\\Programs\\Python\\Python3*")', run_bat)
        self.assertIn('for /d %%D in ("%ProgramFiles%\\Python3*")', run_bat)
        self.assertIn('for /d %%D in ("C:\\Python3*")', run_bat)

        # 4. Must include domestic mirror options and size validation in install_python.bat
        self.assertIn("huaweicloud.com", install_bat)
        self.assertIn("npmmirror.com", install_bat)
        self.assertIn("15000000", install_bat)  # >15MB size check to prevent corrupt installer execution

        # 5. install_python.bat must support --from-launcher parameter
        self.assertIn("--from-launcher", install_bat)

        # 6. requirements.txt must pin numpy<2.0.0 for older classroom CPU compatibility (<3.13) and support >=3.13
        self.assertIn("numpy>=1.24.0,<2.0.0", reqs)
        self.assertIn('python_version < "3.13"', reqs)
        self.assertIn('python_version >= "3.13"', reqs)

        # 7. deploy_seewo.bat must not have unescaped nested quotes around && in cmd /k
        self.assertNotIn('cmd /k "chcp 65001 >nul && "', deploy_bat)
        self.assertIn('start "InkYard Server" cmd /k ""!RUN_PY!" -u "%BASE%server.py""', deploy_bat)

        # 8. install_python.bat must pass InstallLauncherAllUsers=0 so non-admin install doesn't trigger UAC
        self.assertIn("InstallLauncherAllUsers=0", install_bat)

    def test_find_available_port_windows_vs_unix(self):
        """Verify find_available_port avoids SO_REUSEADDR on win32 and sets it on Unix."""
        from unittest.mock import patch, MagicMock
        import socket
        from server import find_available_port

        # 1. On Windows (win32), SO_REUSEADDR must NOT be called
        mock_sock = MagicMock()
        mock_sock.__enter__.return_value = mock_sock
        with patch("server.sys.platform", "win32"), patch("server.socket.socket", return_value=mock_sock):
            port = find_available_port(5000)
            self.assertEqual(port, 5000)
            for call in mock_sock.setsockopt.call_args_list:
                self.assertNotEqual(call[0][1], socket.SO_REUSEADDR)

        # 2. On macOS/Unix (darwin), SO_REUSEADDR is called and fallback port works when 5000 is busy
        mock_sock_unix = MagicMock()
        mock_sock_unix.__enter__.return_value = mock_sock_unix
        mock_sock_unix.bind.side_effect = [OSError("Port 5000 busy"), None]
        with patch("server.sys.platform", "darwin"), patch("server.socket.socket", return_value=mock_sock_unix):
            port = find_available_port(5000)
            self.assertEqual(port, 5050)
            mock_sock_unix.setsockopt.assert_called_with(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def test_probe_native_modules_handles_avx2_crash(self):
        """Verify _probe_native_modules catches negative Windows NTSTATUS crash codes (-1073741795 / 0xC000001D)."""
        from unittest.mock import patch, MagicMock
        from server import _probe_native_modules, _get_probe_cache_key

        cache_key = _get_probe_cache_key()
        self.assertIn("numpy:", cache_key)
        self.assertIn("PIL:", cache_key)
        self.assertIn("fitz:", cache_key)
        self.assertIn("cv2:", cache_key)

        old_skip_cv2 = os.environ.get("INKYARD_SKIP_CV2")
        old_auto_repair = os.environ.get("INKYARD_AUTO_REPAIR")
        os.environ["INKYARD_AUTO_REPAIR"] = "0"
        try:
            def fake_run(cmd, *args, **kwargs):
                res = MagicMock()
                stmt = cmd[2] if len(cmd) > 2 else ""
                if "import cv2" in stmt:
                    # Simulate Windows STATUS_ILLEGAL_INSTRUCTION (0xC000001D = -1073741795)
                    res.returncode = -1073741795
                else:
                    res.returncode = 0
                return res

            with patch("server.subprocess.run", side_effect=fake_run):
                probe_res = _probe_native_modules(force=True)
                self.assertTrue(probe_res["numpy"])
                self.assertTrue(probe_res["PIL"])
                self.assertTrue(probe_res["fitz"])
                self.assertFalse(probe_res["cv2"])
                self.assertEqual(os.environ.get("INKYARD_SKIP_CV2"), "1")
        finally:
            if old_skip_cv2 is None:
                os.environ.pop("INKYARD_SKIP_CV2", None)
            else:
                os.environ["INKYARD_SKIP_CV2"] = old_skip_cv2
            if old_auto_repair is None:
                os.environ.pop("INKYARD_AUTO_REPAIR", None)
            else:
                os.environ["INKYARD_AUTO_REPAIR"] = old_auto_repair


if __name__ == "__main__":
    unittest.main()


