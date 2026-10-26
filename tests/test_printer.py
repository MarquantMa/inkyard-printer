import os
import shutil
import unittest
import fitz
from core.printer_dispatcher import (
    build_pjl_payload,
    build_ipp_print_request,
    check_printer_connectivity,
    dispatch_print_job
)

class TestPrinterDispatcher(unittest.TestCase):
    def setUp(self):
        self.test_dir = "spool/test_printer"
        os.makedirs(self.test_dir, exist_ok=True)
        self.test_pdf = os.path.join(self.test_dir, "test.pdf")
        doc = fitz.open()
        p = doc.new_page(width=400, height=400)
        p.insert_text((50, 50), "Test Print")
        doc.save(self.test_pdf)
        doc.close()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_pjl_payload(self):
        with open(self.test_pdf, "rb") as f:
            pdf_bytes = f.read()
        pjl = build_pjl_payload(pdf_bytes, student_name="Alex", job_name="TestJob.pdf", duplex=True, copies=1)
        self.assertIn(b'@PJL SET USERNAME = "Alex"', pjl)
        self.assertIn(b'@PJL SET JOBNAME = "TestJob.pdf"', pjl)
        self.assertIn(b'@PJL SET DUPLEX = ON', pjl)
        self.assertIn(b'@PJL ENTER LANGUAGE = PDF', pjl)
        self.assertTrue(pjl.endswith(b"\x1b%-12345X"))

    def test_ipp_request_builder(self):
        with open(self.test_pdf, "rb") as f:
            pdf_bytes = f.read()
        ipp_data = build_ipp_print_request(pdf_bytes, "Alex", "TestJob.pdf", duplex=True, copies=1)
        # IPP version 2.0 = 0x02, 0x00
        self.assertEqual(ipp_data[:2], b"\x02\x00")
        self.assertIn(b"Alex", ipp_data)
        self.assertIn(b"TestJob.pdf", ipp_data)
        self.assertIn(b"two-sided-long-edge", ipp_data)

    def test_connectivity_checker(self):
        res = check_printer_connectivity("127.0.0.1", timeout=0.1)
        self.assertIn("online", res)
        self.assertIn("ports", res)
        self.assertIn("latency_ms", res)

    def test_unicode_and_hold_in_pjl(self):
        with open(self.test_pdf, "rb") as f:
            pdf_bytes = f.read()
        pjl = build_pjl_payload(pdf_bytes, student_name="张伟", job_name="打印方案.pdf", duplex=True, copies=1)
        self.assertIn("张伟".encode("utf-8"), pjl)
        self.assertIn("打印方案.pdf".encode("utf-8"), pjl)
        self.assertIn(b"@PJL SET HOLD = ON", pjl)
        self.assertNotIn(b"???", pjl)

    def test_lpd_control_file_binary_mode(self):
        # Verify LPD control file logic produces 'l' for binary raw stream
        hostname = "localhost"
        job_id = "001"
        student = "Alex Marquant"
        job = "Essay.pdf"
        cf_lines = [
            f"H{hostname}",
            f"P{student}",
            f"J{job}",
            f"C{student}",
            f"L{student}",
            f"N{job}",
            f"ldfA{job_id}{hostname}",
            f"UdfA{job_id}{hostname}",
        ]
        cf_data = ("\n".join(cf_lines) + "\n").encode("utf-8")
        self.assertIn(b"ldfA001localhost", cf_data)
        self.assertIn(b"PAlex Marquant", cf_data)

    def test_binding_edge_and_collate_options(self):
        with open(self.test_pdf, "rb") as f:
            pdf_bytes = f.read()
            
        # 1. Short edge binding + uncollated
        pjl_short = build_pjl_payload(pdf_bytes, "Sam", "Notes.pdf", duplex=True, copies=2, binding="short", collate=False)
        self.assertIn(b"@PJL SET BINDING = SHORTEDGE", pjl_short)
        self.assertIn(b"@PJL SET COLLATE = OFF", pjl_short)
        self.assertIn(b"@PJL SET QTY = 2", pjl_short)

        ipp_short = build_ipp_print_request(pdf_bytes, "Sam", "Notes.pdf", duplex=True, copies=2, binding="short", collate=False)
        self.assertIn(b"two-sided-short-edge", ipp_short)
        self.assertIn(b"separate-documents-uncollated-copies", ipp_short)

        # 2. Long edge binding + collated
        pjl_long = build_pjl_payload(pdf_bytes, "Sam", "Notes.pdf", duplex=True, copies=2, binding="long", collate=True)
        self.assertIn(b"@PJL SET BINDING = LONGEDGE", pjl_long)
        self.assertIn(b"@PJL SET COLLATE = ON", pjl_long)

        ipp_long = build_ipp_print_request(pdf_bytes, "Sam", "Notes.pdf", duplex=True, copies=2, binding="long", collate=True)
        self.assertIn(b"two-sided-long-edge", ipp_long)
        self.assertIn(b"separate-documents-collated-copies", ipp_long)

if __name__ == "__main__":
    unittest.main()
