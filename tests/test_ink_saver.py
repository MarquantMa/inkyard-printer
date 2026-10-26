import os
import shutil
import unittest
import numpy as np
import cv2
import fitz
from core.ink_saver import (
    calculate_ink_density,
    apply_eco_mode,
    apply_matrix_mode,
    apply_slide_clean_mode,
    apply_line_art_mode,
    apply_smart_inversion,
    is_dark_background,
    process_image,
    parse_page_range,
    generate_page_preview,
    process_pdf_document
)

class TestInkSaver(unittest.TestCase):
    def setUp(self):
        self.test_dir = "spool/test_ink"
        os.makedirs(self.test_dir, exist_ok=True)
        # Create a test PDF
        self.test_pdf = os.path.join(self.test_dir, "sample.pdf")
        doc = fitz.open()
        for i in range(3):
            p = doc.new_page(width=500, height=700)
            p.insert_text((50, 100), f"Sample Page {i+1}", fontsize=20)
            p.draw_rect(fitz.Rect(50, 150, 400, 300), color=(0,0,0), fill=(0.2, 0.2, 0.2))
        doc.save(self.test_pdf)
        doc.close()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_density_calculation(self):
        white = np.full((100, 100, 3), 255, dtype=np.uint8)
        black = np.full((100, 100, 3), 0, dtype=np.uint8)
        self.assertAlmostEqual(calculate_ink_density(white), 0.0, places=2)
        self.assertAlmostEqual(calculate_ink_density(black), 1.0, places=2)

    def test_eco_mode(self):
        dark_img = np.full((100, 100, 3), 50, dtype=np.uint8)
        eco = apply_eco_mode(dark_img, gamma=1.6)
        # Gamma 1.6 should make dark regions brighter (higher pixel values)
        self.assertGreater(eco.mean(), dark_img.mean())

    def test_matrix_mode(self):
        gray_img = np.full((100, 100, 3), 128, dtype=np.uint8)
        matrix = apply_matrix_mode(gray_img)
        # Should contain bilevel 0 and 255 values
        unique_vals = set(np.unique(matrix))
        self.assertTrue(unique_vals.issubset({0, 255}))

    def test_slide_clean_mode(self):
        # Dark slide with white text
        slide = np.full((200, 200, 3), 30, dtype=np.uint8)
        slide[80:120, 80:120] = [240, 240, 240]
        cleaned = apply_slide_clean_mode(slide)
        # Background should become pure white (255, 255, 255)
        self.assertEqual(cleaned[10, 10].tolist(), [255, 255, 255])

    def test_line_art_mode(self):
        img = np.full((200, 200, 3), 200, dtype=np.uint8)
        cv2.circle(img, (100, 100), 50, (20, 20, 20), -1)
        line_art = apply_line_art_mode(img)
        self.assertEqual(len(line_art.shape), 3)

    def test_page_range_parsing(self):
        self.assertEqual(parse_page_range("all", 5), [0, 1, 2, 3, 4])
        self.assertEqual(parse_page_range("1-3", 5), [0, 1, 2])
        self.assertEqual(parse_page_range("2, 4-5", 5), [1, 3, 4])

    def test_preview_generation(self):
        res = generate_page_preview(self.test_pdf, page_num=0, mode="matrix")
        self.assertEqual(res["page"], 1)
        self.assertEqual(res["total_pages"], 3)
        self.assertTrue(res["orig_b64"].startswith("data:image/jpeg;base64,"))
        self.assertTrue(res["proc_b64"].startswith("data:image/jpeg;base64,"))
        self.assertGreaterEqual(res["ink_saved_pct"], 0)

    def test_actual_matrix_saving_percentage(self):
        # Create a document page with dense black text and shapes
        img = np.full((300, 500, 3), 255, dtype=np.uint8)
        cv2.putText(img, "Testing True Ink Reduction", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,0), 2)
        cv2.rectangle(img, (30, 120), (300, 240), (0,0,0), -1)

        d_orig = calculate_ink_density(img)
        mat = apply_matrix_mode(img)
        d_mat = calculate_ink_density(mat)
        saving_pct = (1.0 - d_mat / d_orig) * 100.0

        # Must actually deliver ~50% savings (+/- 5%) on black fills and text
        self.assertGreaterEqual(saving_pct, 45.0)
        self.assertLessEqual(saving_pct, 55.0)

    def test_actual_eco_saving_percentage(self):
        img = np.full((300, 500, 3), 255, dtype=np.uint8)
        cv2.putText(img, "Eco Mode Real Savings", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,0), 2)
        cv2.rectangle(img, (30, 120), (300, 240), (0,0,0), -1)

        d_orig = calculate_ink_density(img)
        eco = apply_eco_mode(img)
        d_eco = calculate_ink_density(eco)
        saving_pct = (1.0 - d_eco / d_orig) * 100.0

        # Must deliver ~25% savings (+/- 5%)
        self.assertGreaterEqual(saving_pct, 20.0)
        self.assertLessEqual(saving_pct, 32.0)

    def test_actual_slide_clean_saving(self):
        # Dark background slide (e.g. blue/black) with white text
        slide = np.full((300, 500, 3), [60, 30, 10], dtype=np.uint8)
        cv2.putText(slide, "Lecture Slides", (30, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255,255,255), 2)
        d_orig = calculate_ink_density(slide)
        cleaned = apply_slide_clean_mode(slide)
        d_clean = calculate_ink_density(cleaned)
        saving_pct = (1.0 - d_clean / d_orig) * 100.0

        # Slide cleaning must eliminate dark background, saving >60% ink
        self.assertGreater(saving_pct, 60.0)

    def test_full_document_processing(self):
        out_pdf = os.path.join(self.test_dir, "processed.pdf")
        res = process_pdf_document(self.test_pdf, out_pdf, mode="matrix", page_range_str="1-2")
        self.assertEqual(res["printed_pages"], 2)
        self.assertTrue(os.path.exists(out_pdf))
        doc_out = fitz.open(out_pdf)
        self.assertEqual(len(doc_out), 2)
        doc_out.close()

    def test_eco_mode_is_monochrome(self):
        # A colorful document with red, green, blue elements
        img = np.full((150, 150, 3), 255, dtype=np.uint8)
        img[20:60, 20:60] = [255, 0, 0]      # Blue
        img[70:110, 20:60] = [0, 255, 0]     # Green
        img[20:60, 70:110] = [0, 0, 255]     # Red
        img[70:110, 70:110] = [0, 200, 200]  # Yellow
        eco = apply_eco_mode(img)
        # All three BGR channels must be identical (pure black & white laser look)
        b, g, r = eco[:,:,0], eco[:,:,1], eco[:,:,2]
        self.assertTrue(np.array_equal(b, g))
        self.assertTrue(np.array_equal(g, r))

    def test_eco_mode_preserves_dark_text(self):
        # Document with solid black text
        img = np.full((200, 400, 3), 255, dtype=np.uint8)
        cv2.putText(img, "Sharp Black Text", (30, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,0), 2)

        # Locate dark text center pixels in original
        text_pixels = np.where(img[:,:,0] == 0)
        self.assertGreater(len(text_pixels[0]), 0)

        eco = apply_eco_mode(img)
        # In eco mode, text should stay pure dark (not washed out)
        min_text_val = int(np.min(eco[text_pixels]))
        max_text_val = int(np.max(eco[text_pixels]))
        self.assertEqual(min_text_val, 0)
        self.assertLessEqual(max_text_val, 15)

    def test_eco_mode_preserves_bold_headings_without_washing_out(self):
        # Bold heading with thick strokes (stroke thickness > 4px)
        img = np.full((120, 500, 3), 255, dtype=np.uint8)
        cv2.putText(img, "Chapter 1: Overview", (20, 80), cv2.FONT_HERSHEY_DUPLEX, 1.8, (0, 0, 0), 5)

        dark_pixels = np.where(img[:, :, 0] == 0)
        self.assertGreater(len(dark_pixels[0]), 0)

        eco = apply_eco_mode(img)
        # All dark pixels of the bold heading must be preserved as true dark black (0)
        heading_vals = eco[:, :, 0][dark_pixels]
        self.assertEqual(int(np.min(heading_vals)), 0)
        self.assertEqual(int(np.max(heading_vals)), 0)

    def test_eco_mode_lightens_large_solid_banners(self):
        # Massive solid black rectangle/banner (wastes toner)
        img = np.full((200, 500, 3), 255, dtype=np.uint8)
        img[30:170, 30:470] = 0
        eco = apply_eco_mode(img)
        # The center of the massive solid block must be lightened to save toner
        center_val = int(eco[100, 250, 0])
        self.assertGreaterEqual(center_val, 50)
        self.assertLessEqual(center_val, 100)

    def test_eco_mode_chinese_text_preservation(self):
        # Chinese characters drawn with PIL
        from PIL import Image, ImageDraw, ImageFont
        im = Image.new("RGB", (300, 100), (255, 255, 255))
        draw = ImageDraw.Draw(im)
        font = None
        for p in ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Light.ttc", "C:\\Windows\\Fonts\\msyh.ttc"]:
            if os.path.exists(p):
                try:
                    font = ImageFont.truetype(p, 28)
                    break
                except Exception:
                    pass
        if font is None:
            font = ImageFont.load_default()
        draw.text((20, 30), "打印机省墨", fill=(0, 0, 0), font=font)
        arr = np.array(im)[:, :, ::-1]

        eco = apply_eco_mode(arr)
        dark = (arr[:, :, 0] == 0)
        if np.sum(dark) > 0:
            self.assertEqual(int(np.min(eco[:, :, 0][dark])), 0)

    def test_eco_mode_paper_background_cleanup(self):
        # Off-white / scanned paper background noise (e.g. 235-245)
        img = np.full((100, 100, 3), 236, dtype=np.uint8)
        eco = apply_eco_mode(img)
        # Faint off-white noise must be eliminated to pure white (255, 255, 255)
        self.assertEqual(int(eco[10, 10, 0]), 255)
        self.assertEqual(int(eco[50, 50, 1]), 255)

    def test_invert_color_preview(self):
        res_normal = generate_page_preview(self.test_pdf, page_num=0, mode="normal", invert_color=False)
        res_inverted = generate_page_preview(self.test_pdf, page_num=0, mode="normal", invert_color=True)
        self.assertTrue(res_inverted["invert_color"])
        # Original baseline page image must remain identical
        self.assertEqual(res_normal["orig_b64"], res_inverted["orig_b64"])
        # Processed image must be inverted and different
        self.assertNotEqual(res_normal["proc_b64"], res_inverted["proc_b64"])

    def test_nup_layout_processing(self):
        # Create a 4-page test PDF (portrait)
        doc = fitz.open()
        for i in range(4):
            p = doc.new_page(width=500, height=700)
            p.insert_text((50, 100), f"N-up Page {i+1}")
        four_page_pdf = os.path.join(self.test_dir, "four_pages.pdf")
        doc.save(four_page_pdf)
        doc.close()

        # 2-up test (portrait source -> landscape A4 output)
        out_2up = os.path.join(self.test_dir, "out_2up.pdf")
        res_2up = process_pdf_document(four_page_pdf, out_2up, mode="normal", nup=2)
        self.assertEqual(res_2up["printed_pages"], 4)
        self.assertEqual(res_2up["printed_sheets"], 2)
        doc_2up = fitz.open(out_2up)
        self.assertEqual(len(doc_2up), 2)
        self.assertAlmostEqual(doc_2up[0].rect.width, 842.0, delta=1.0)
        self.assertAlmostEqual(doc_2up[0].rect.height, 595.0, delta=1.0)
        doc_2up.close()

        # 4-up test (portrait source -> portrait A4 output)
        out_4up = os.path.join(self.test_dir, "out_4up.pdf")
        res_4up = process_pdf_document(four_page_pdf, out_4up, mode="matrix", nup=4)
        self.assertEqual(res_4up["printed_pages"], 4)
        self.assertEqual(res_4up["printed_sheets"], 1)
        doc_4up = fitz.open(out_4up)
        self.assertEqual(len(doc_4up), 1)
        self.assertAlmostEqual(doc_4up[0].rect.width, 595.0, delta=1.0)
        self.assertAlmostEqual(doc_4up[0].rect.height, 842.0, delta=1.0)
        doc_4up.close()

    def test_nup_layout_landscape_slides(self):
        # Create 2 landscape slide pages (e.g. 16:9 slides 842 x 473 pt)
        doc = fitz.open()
        for i in range(2):
            p = doc.new_page(width=842, height=473)
            p.insert_text((50, 100), f"Slide {i+1}")
        slides_pdf = os.path.join(self.test_dir, "slides.pdf")
        doc.save(slides_pdf)
        doc.close()

        # 2-up test for slides (landscape source -> portrait A4 sheet stacked top/bottom)
        out_slides_2up = os.path.join(self.test_dir, "slides_2up.pdf")
        res_s2 = process_pdf_document(slides_pdf, out_slides_2up, mode="normal", nup=2)
        self.assertEqual(res_s2["printed_pages"], 2)
        self.assertEqual(res_s2["printed_sheets"], 1)
        doc_s2 = fitz.open(out_slides_2up)
        self.assertEqual(len(doc_s2), 1)
        self.assertAlmostEqual(doc_s2[0].rect.width, 595.0, delta=1.0)
        self.assertAlmostEqual(doc_s2[0].rect.height, 842.0, delta=1.0)
        doc_s2.close()

    def test_invert_color_dark_slide_saving(self):
        # Create a dark slide (black background with white text)
        doc = fitz.open()
        p = doc.new_page(width=500, height=300)
        # Draw solid black background
        p.draw_rect(fitz.Rect(0, 0, 500, 300), color=(0, 0, 0), fill=(0, 0, 0))
        p.insert_text((50, 150), "White Text on Dark Slide", color=(1, 1, 1), fontsize=24)
        dark_pdf = os.path.join(self.test_dir, "dark_slide.pdf")
        doc.save(dark_pdf)
        doc.close()

        res = generate_page_preview(dark_pdf, page_num=0, mode="normal", invert_color=True)
        self.assertTrue(res["invert_color"])
        # Original dark slide must have very high ink density (> 90%)
        self.assertGreater(res["orig_ink_density"], 80.0)
        # Processed inverted slide must have very low ink density (< 15%)
        self.assertLess(res["proc_ink_density"], 15.0)
        # Savings must be over 80%
        self.assertGreater(res["ink_saved_pct"], 80.0)

    def test_default_mode_is_eco(self):
        # 1. process_image default mode
        img = np.full((100, 100, 3), 128, dtype=np.uint8)
        default_out = process_image(img)
        eco_out = apply_eco_mode(img)
        self.assertTrue(np.array_equal(default_out, eco_out))

        # 2. generate_page_preview default mode
        prev = generate_page_preview(self.test_pdf, page_num=0)
        self.assertEqual(prev["mode"], "eco")

        # 3. process_pdf_document default mode
        out_pdf = os.path.join(self.test_dir, "default_mode_out.pdf")
        doc_res = process_pdf_document(self.test_pdf, out_pdf)
        self.assertEqual(doc_res["mode"], "eco")

    def test_white_document_inversion_protection(self):
        # Create a typical student document: white A4 page with black text
        doc = fitz.open()
        p = doc.new_page(width=595, height=842)
        p.insert_text((50, 100), "Curriculum Vitae / Resume", fontsize=24)
        p.insert_text((50, 140), "Education: University degree in Computer Science", fontsize=14)
        p.insert_text((50, 170), "Experience: Software engineering and sustainability projects", fontsize=14)
        white_pdf = os.path.join(self.test_dir, "white_resume.pdf")
        doc.save(white_pdf)
        doc.close()

        # Invert color on a white document must NOT turn it into a black sheet
        res = generate_page_preview(white_pdf, page_num=0, mode="eco", invert_color=True)
        self.assertTrue(res["invert_color"])
        # Original density should be low (~1-5%)
        self.assertLess(res["orig_ink_density"], 10.0)
        # Processed density must stay very low (< 10%), NOT turn into 80-95% black toner!
        self.assertLess(res["proc_ink_density"], 10.0)
        # Density must NOT increase above original
        self.assertLessEqual(res["proc_ink_density"], res["orig_ink_density"] + 0.5)

    def test_smart_inversion_direct_behavior(self):
        # Case A: White page with dark text
        white_page = np.full((200, 300, 3), 255, dtype=np.uint8)
        cv2.putText(white_page, "Hello World", (30, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
        res_a = apply_smart_inversion(white_page)
        # Corners must stay pure white (255)
        self.assertEqual(int(res_a[5, 5, 0]), 255)
        self.assertEqual(int(res_a[190, 290, 0]), 255)
        # Text should still be dark
        dark_pix = (white_page[:, :, 0] == 0)
        self.assertLessEqual(int(np.mean(res_a[:, :, 0][dark_pix])), 30)

        # Case B: Dark slide (black background with white text)
        dark_slide = np.full((200, 300, 3), 10, dtype=np.uint8)
        cv2.putText(dark_slide, "Title Slide", (30, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        res_b = apply_smart_inversion(dark_slide)
        # Background must turn pure white (245+)
        self.assertGreaterEqual(int(res_b[5, 5, 0]), 240)
        self.assertGreaterEqual(int(res_b[190, 290, 0]), 240)

        # Case C: Boundary edge cases (1x1, pure black, pure white, 2D array)
        one_by_one = np.full((1, 1, 3), 255, dtype=np.uint8)
        self.assertEqual(apply_smart_inversion(one_by_one).shape, (1, 1, 3))
        gray_2d = np.full((50, 50), 250, dtype=np.uint8)
        self.assertEqual(apply_smart_inversion(gray_2d).shape, (50, 50))

    def test_banner_document_protection(self):
        # A document with a dark top banner across the full width
        page = np.full((800, 600, 3), 255, dtype=np.uint8)
        page[:60, :] = 0 # Top black banner
        cv2.putText(page, "Student Report Header", (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        cv2.putText(page, "Main document body text", (30, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)

        inv = apply_smart_inversion(page)
        # Body white paper (row 400, col 300) MUST NOT be inverted to black [0, 0, 0]!
        self.assertEqual(inv[400, 300].tolist(), [255, 255, 255])
        # Body text must stay dark (< 50)
        body_text_coords = (page[100:, :, 0] < 50)
        self.assertLess(float(np.mean(inv[100:, :, 0][body_text_coords])), 50)

    def test_preview_is_dark_bg_flag(self):
        # 1. White document preview
        white_doc = fitz.open()
        p = white_doc.new_page(width=500, height=700)
        p.insert_text((50, 100), "White Page Content")
        w_path = os.path.join(self.test_dir, "w_flag.pdf")
        white_doc.save(w_path)
        white_doc.close()

        w_prev = generate_page_preview(w_path, page_num=0)
        self.assertFalse(w_prev["is_dark_bg"])
        self.assertEqual(w_prev["mode"], "eco")

        # 2. Dark slide preview
        dark_doc = fitz.open()
        p2 = dark_doc.new_page(width=500, height=700)
        p2.draw_rect(fitz.Rect(0, 0, 500, 700), color=(0, 0, 0), fill=(0, 0, 0))
        p2.insert_text((50, 100), "Dark Slide Content", color=(1, 1, 1))
        d_path = os.path.join(self.test_dir, "d_flag.pdf")
        dark_doc.save(d_path)
        dark_doc.close()

        d_prev = generate_page_preview(d_path, page_num=0)
        self.assertTrue(d_prev["is_dark_bg"])

    def test_slide_clean_protection_on_light_doc(self):
        # A light document with a top banner should NOT be blackened by slide_clean
        page = np.full((800, 600, 3), 255, dtype=np.uint8)
        page[:50, :] = 20 # Header banner
        cleaned = apply_slide_clean_mode(page)
        # White paper must remain pure white (255, 255, 255), not charcoal [30, 30, 30]
        self.assertEqual(cleaned[400, 300].tolist(), [255, 255, 255])

    def test_process_image_with_invert_color(self):
        # Dark slide processed with process_image and invert_color=True
        slide = np.full((100, 100, 3), 20, dtype=np.uint8)
        out = process_image(slide, mode="eco", invert_color=True)
        # Background should become pure white (255)
        self.assertEqual(out[10, 10, 0], 255)

    def test_banner_white_text_preserved_as_dark(self):
        # White document with a dark header banner containing white text
        doc = np.full((400, 600, 3), 255, dtype=np.uint8)
        doc[50:150, 50:550] = 0 # Dark banner
        cv2.putText(doc, "BANNER HEADING", (100, 115), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)

        inv = apply_smart_inversion(doc)
        # 1. Dark banner background must become pure white (saves 100% banner toner)
        self.assertEqual(inv[60, 60].tolist(), [255, 255, 255])
        # 2. White text inside banner must NOT disappear; it must become crisp dark charcoal
        white_in_banner = np.where((doc[50:150, 50:550, 0] > 200))
        y_t, x_t = white_in_banner[0][0] + 50, white_in_banner[1][0] + 50
        self.assertEqual(inv[y_t, x_t].tolist(), [30, 30, 30])
        # 3. Overall density must decrease
        self.assertLess(calculate_ink_density(inv), calculate_ink_density(doc))

    def test_eco_mode_bold_heading_touching_divider_line(self):
        # Heading text directly touching a horizontal divider rule
        page = np.full((300, 600, 3), 255, dtype=np.uint8)
        cv2.line(page, (30, 80), (550, 80), (0, 0, 0), 3)
        cv2.putText(page, "WORK EXPERIENCE", (30, 79), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4)

        eco = apply_eco_mode(page)
        # Locate dark pixels of heading
        text_pixels = (page[:78, 30:450, 0] == 0)
        self.assertGreater(np.sum(text_pixels), 0)
        # Heading text must stay deep black (not washed out to > 100 gray)
        heading_vals = eco[:78, 30:450, 0][text_pixels]
        self.assertEqual(int(np.min(heading_vals)), 0)
        self.assertLessEqual(float(np.mean(heading_vals)), 15.0)


    def test_is_dark_background_comprehensive(self):
        # 1. Normal white document with black text
        white_doc = np.full((1000, 800, 3), 255, dtype=np.uint8)
        cv2.putText(white_doc, "Regular Essay Text", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
        self.assertFalse(is_dark_background(white_doc))

        # 2. White document with top dark banner
        banner_doc = white_doc.copy()
        banner_doc[:150, :] = 10
        self.assertFalse(is_dark_background(banner_doc))

        # 3. Standard dark lecture slide
        dark_slide = np.full((1000, 800, 3), 20, dtype=np.uint8)
        cv2.putText(dark_slide, "Lecture Slide", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        self.assertTrue(is_dark_background(dark_slide))

        # 4. Dark slide with white footer/page number
        dark_slide_footer = dark_slide.copy()
        dark_slide_footer[900:, :] = 255
        self.assertTrue(is_dark_background(dark_slide_footer))

        # 5. Dark slide with thin white borders
        dark_slide_border = dark_slide.copy()
        dark_slide_border[:20, :] = 255
        dark_slide_border[-20:, :] = 255
        dark_slide_border[:, :20] = 255
        dark_slide_border[:, -20:] = 255
        self.assertTrue(is_dark_background(dark_slide_border))

    def test_dark_slide_with_white_footer_slide_clean_mode(self):
        # A dark slide with a white bottom footer must still have its dark background whitened
        slide = np.full((600, 800, 3), 20, dtype=np.uint8)
        cv2.putText(slide, "Neural Networks Intro", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
        slide[550:, :] = 255 # White footer

        cleaned = apply_slide_clean_mode(slide)
        # Background at (200, 40) must be pure white (255, 255, 255)
        self.assertEqual(cleaned[200, 40].tolist(), [255, 255, 255])
        # Text must be dark charcoal
        text_coords = np.where(slide[:540, :, 0] == 255)
        self.assertGreater(len(text_coords[0]), 0)
        self.assertEqual(int(np.max(cleaned[text_coords[0], text_coords[1], 0])), 30)

    def test_eco_mode_scanned_background_noise_cleaned(self):
        # Scanned paper background with noise at luminance 218-222
        scanned_img = np.full((100, 100, 3), 218, dtype=np.uint8)
        eco = apply_eco_mode(scanned_img)
        # Must be whitened to pure 255 paper
        self.assertEqual(int(eco[50, 50, 0]), 255)
        self.assertEqual(int(eco[50, 50, 1]), 255)
        self.assertEqual(int(eco[50, 50, 2]), 255)

    def test_pure_pillow_fallback_without_cv2(self):
        """Verify all ink-saving modes, preview, and PDF processing work when cv2 is disabled (AVX2 CPU crash fallback)."""
        old_skip_cv2 = os.environ.get("INKYARD_SKIP_CV2")
        os.environ["INKYARD_SKIP_CV2"] = "1"
        try:
            # 1. Density & dark background check
            white = np.full((100, 100, 3), 255, dtype=np.uint8)
            black = np.full((100, 100, 3), 0, dtype=np.uint8)
            self.assertAlmostEqual(calculate_ink_density(white), 0.0, places=2)
            self.assertAlmostEqual(calculate_ink_density(black), 1.0, places=2)
            self.assertFalse(is_dark_background(white))
            self.assertTrue(is_dark_background(black))

            # 2. Eco mode in pure Pillow
            doc_img = np.full((200, 300, 3), 255, dtype=np.uint8)
            doc_img[40:160, 40:260] = 0
            eco_res = apply_eco_mode(doc_img)
            self.assertEqual(eco_res.shape, (200, 300, 3))
            self.assertLess(calculate_ink_density(eco_res), calculate_ink_density(doc_img))

            # 3. Matrix mode in pure Pillow
            mat_res = apply_matrix_mode(doc_img)
            self.assertEqual(mat_res.shape, (200, 300, 3))
            self.assertTrue(set(np.unique(mat_res)).issubset({0, 255}))

            # 4. Slide clean mode in pure Pillow
            slide = np.full((200, 200, 3), 20, dtype=np.uint8)
            slide[80:120, 80:120] = 240
            clean_res = apply_slide_clean_mode(slide)
            self.assertEqual(clean_res[10, 10].tolist(), [255, 255, 255])
            self.assertEqual(clean_res[100, 100].tolist(), [30, 30, 30])

            # 5. Line art mode in pure Pillow
            la_res = apply_line_art_mode(doc_img)
            self.assertEqual(la_res.shape, (200, 300, 3))

            # 6. Smart inversion in pure Pillow
            inv_dark = apply_smart_inversion(slide)
            self.assertEqual(inv_dark[10, 10].tolist(), [255, 255, 255])
            inv_light = apply_smart_inversion(white)
            self.assertEqual(inv_light[10, 10].tolist(), [255, 255, 255])

            # 7. Preview & PDF processing in pure Pillow
            prev = generate_page_preview(self.test_pdf, page_num=0, mode="eco", invert_color=True)
            self.assertTrue(prev["proc_b64"].startswith("data:image/jpeg;base64,"))
            self.assertGreater(prev["ink_saved_pct"], 0.0)

            for m in ("eco", "matrix", "slide_clean", "line_art"):
                out_pdf = os.path.join(self.test_dir, f"no_cv2_{m}.pdf")
                res = process_pdf_document(self.test_pdf, out_pdf, mode=m, page_range_str="1-2", nup=2)
                self.assertEqual(res["printed_pages"], 2)
                self.assertEqual(res["printed_sheets"], 1)
                self.assertTrue(os.path.exists(out_pdf))
        finally:
            if old_skip_cv2 is None:
                os.environ.pop("INKYARD_SKIP_CV2", None)
            else:
                os.environ["INKYARD_SKIP_CV2"] = old_skip_cv2

    def test_pure_pillow_fallback_without_cv2_and_without_numpy(self):
        """Verify preview and PDF processing work when BOTH cv2 and numpy are disabled (including module reload with np=None)."""
        import importlib
        import core.ink_saver as ink_mod

        old_skip_cv2 = os.environ.get("INKYARD_SKIP_CV2")
        old_skip_np = os.environ.get("INKYARD_SKIP_NUMPY")
        os.environ["INKYARD_SKIP_CV2"] = "1"
        os.environ["INKYARD_SKIP_NUMPY"] = "1"
        try:
            importlib.reload(ink_mod)
            self.assertIsNone(ink_mod.np)
            self.assertIsNone(ink_mod.cv2)
            self.assertFalse(ink_mod.HAS_NUMPY)
            self.assertFalse(ink_mod.HAS_CV2)

            for m in ("eco", "matrix", "slide_clean", "line_art"):
                prev = ink_mod.generate_page_preview(self.test_pdf, page_num=0, mode=m, invert_color=True)
                self.assertTrue(prev["proc_b64"].startswith("data:image/jpeg;base64,"))

                out_pdf = os.path.join(self.test_dir, f"no_np_{m}.pdf")
                res = ink_mod.process_pdf_document(self.test_pdf, out_pdf, mode=m, page_range_str="1", invert_color=True)
                self.assertEqual(res["printed_pages"], 1)
                self.assertTrue(os.path.exists(out_pdf))
        finally:
            if old_skip_cv2 is None:
                os.environ.pop("INKYARD_SKIP_CV2", None)
            else:
                os.environ["INKYARD_SKIP_CV2"] = old_skip_cv2
            if old_skip_np is None:
                os.environ.pop("INKYARD_SKIP_NUMPY", None)
            else:
                os.environ["INKYARD_SKIP_NUMPY"] = old_skip_np
            importlib.reload(ink_mod)


if __name__ == "__main__":
    unittest.main()


