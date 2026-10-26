"""
Universal File Converter for Printer InkSaver
Converts various document and image formats into standard PDF:
- .pdf (direct validation)
- .pages (Apple Pages package extraction of QuickLook/Preview.pdf)
- .docx / .doc (LibreOffice headless or pure Python docx+ReportLab fallback)
- .pptx / .ppt (LibreOffice headless or pure Python pptx+ReportLab fallback)
- .png, .jpg, .jpeg, .webp, .bmp, .tiff (Image to PDF)
- .txt, .md (Text to formatted PDF)
"""

import io
import os
import re
import plistlib
import shutil
import subprocess
import zipfile
import warnings
from pathlib import Path
from PIL import Image
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import fitz  # PyMuPDF


def find_libreoffice_executable() -> str:
    """Find LibreOffice / soffice executable if installed."""
    candidates = [
        shutil.which("soffice"),
        shutil.which("libreoffice"),
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        os.path.expandvars(r"%ProgramFiles%\LibreOffice\program\soffice.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\LibreOffice\program\soffice.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\LibreOffice\program\soffice.exe"),
        "/usr/bin/libreoffice",
        "/usr/bin/soffice",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def _merge_quicklook_attachments(ql_dir: str, output_path: str) -> bool:
    """
    Merge QuickLook generated PDF attachments (Attachment1.pdf, Attachment2.pdf...)
    into a single cohesive multi-page PDF in the exact visual presentation order.
    """
    # 1. Inspect Preview.html for visual sequence of <img src="AttachmentX.pdf">
    html_path = os.path.join(ql_dir, "Preview.html")
    ordered_files = []
    if os.path.exists(html_path):
        try:
            with open(html_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            candidates = re.findall(r"""(?:src|data)=["\x27]([^"\x27]+\.pdf)["\x27]""", content, re.IGNORECASE)
            ordered_files = [c for c in candidates if os.path.exists(os.path.join(ql_dir, c))]
        except Exception:
            pass

    # 2. Inspect PreviewProperties.plist for index-mapped previewN.pdf -> AttachmentX.pdf
    if not ordered_files:
        plist_path = os.path.join(ql_dir, "PreviewProperties.plist")
        if os.path.exists(plist_path):
            try:
                with open(plist_path, "rb") as f:
                    pl = plistlib.load(f)
                attachments = pl.get("Attachments", {})
                page_map = []
                for k, v in attachments.items():
                    m = re.search(r"preview(\d+)\.pdf", k, re.IGNORECASE)
                    if m and isinstance(v, dict):
                        idx = int(m.group(1))
                        target_file = v.get("DumpedAttachmentFileName")
                        if target_file and os.path.exists(os.path.join(ql_dir, target_file)):
                            page_map.append((idx, target_file))
                if page_map:
                    page_map.sort(key=lambda x: x[0])
                    ordered_files = [x[1] for x in page_map]
            except Exception:
                pass

    # 3. Fallback: natural sort of all .pdf files in directory
    if not ordered_files:
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)]
        ordered_files = [f for f in os.listdir(ql_dir) if f.lower().endswith(".pdf")]
        ordered_files.sort(key=natural_sort_key)

    if not ordered_files:
        return False

    if len(ordered_files) == 1:
        shutil.copyfile(os.path.join(ql_dir, ordered_files[0]), output_path)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0

    merged_doc = fitz.open()
    for fname in ordered_files:
        fpath = os.path.join(ql_dir, fname)
        try:
            sub_doc = fitz.open(fpath)
            merged_doc.insert_pdf(sub_doc)
            sub_doc.close()
        except Exception:
            continue

    if len(merged_doc) > 0:
        merged_doc.save(output_path, garbage=3, deflate=True)
        merged_doc.close()
        return True
    merged_doc.close()
    return False


def convert_pages_to_pdf(input_path: str, output_path: str) -> bool:
    """
    Extract or convert Apple .pages documents into standard multi-page PDF:
    1. macOS native QuickLook generation via /usr/bin/qlmanage (merges all pages)
    2. Directory package extraction (if uploaded as folder/bundle)
    3. Zip package extraction of embedded QuickLook/Preview.pdf
    4. Headless LibreOffice conversion if installed (Linux / Windows)
    """
    # 1. macOS native qlmanage (Produces full multi-page attachments)
    if os.path.exists("/usr/bin/qlmanage"):
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as tmp_dir:
                cmd = ["/usr/bin/qlmanage", "-p", input_path, "-o", tmp_dir]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
                for root, _, files in os.walk(tmp_dir):
                    if any(f.lower().endswith(".pdf") for f in files):
                        if _merge_quicklook_attachments(root, output_path):
                            return True
        except Exception:
            pass

    # 2. Directory package (QuickLook subfolder)
    if os.path.isdir(input_path):
        ql_sub = os.path.join(input_path, "QuickLook")
        if os.path.isdir(ql_sub):
            if _merge_quicklook_attachments(ql_sub, output_path):
                return True
        preview_candidates = [
            os.path.join(input_path, "QuickLook", "Preview.pdf"),
            os.path.join(input_path, "preview.pdf"),
            os.path.join(input_path, "Preview.pdf")
        ]
        for candidate in preview_candidates:
            if os.path.exists(candidate) and os.path.getsize(candidate) > 0:
                shutil.copyfile(candidate, output_path)
                return True

    # 3. Zip archive extraction
    if zipfile.is_zipfile(input_path):
        try:
            with zipfile.ZipFile(input_path, 'r') as zf:
                namelist = zf.namelist()

                # Check for multi-page QuickLook attachments inside the zip
                pdf_files = [n for n in namelist if n.lower().endswith(".pdf")]
                if len(pdf_files) > 1 or any("quicklook/" in n.lower() and n.lower().endswith((".pdf", ".html", ".plist")) for n in namelist):
                    import tempfile
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        for name in namelist:
                            if name.lower().endswith((".pdf", ".html", ".plist", ".css")):
                                zf.extract(name, tmp_dir)
                        for root, _, files in os.walk(tmp_dir):
                            if any(f.lower().endswith(".pdf") for f in files):
                                if _merge_quicklook_attachments(root, output_path):
                                    return True

                preview_candidates = [
                    "QuickLook/Preview.pdf",
                    "preview.pdf",
                    "Preview.pdf",
                ]
                for candidate in preview_candidates:
                    if candidate in namelist:
                        with open(output_path, "wb") as f_out:
                            f_out.write(zf.read(candidate))
                        return True

                if len(pdf_files) == 1:
                    with open(output_path, "wb") as f_out:
                        f_out.write(zf.read(pdf_files[0]))
                    return True
        except Exception:
            pass

    # 4. Headless LibreOffice (cross-platform converter for Windows & Linux)
    # Checked BEFORE single-page thumbnail image fallback so multi-page documents get converted
    soffice = find_libreoffice_executable()
    if soffice:
        try:
            out_dir = os.path.dirname(os.path.abspath(output_path))
            cmd = [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, input_path]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            expected_name = Path(input_path).stem + ".pdf"
            expected_path = os.path.join(out_dir, expected_name)
            if os.path.exists(expected_path):
                if expected_path != output_path:
                    shutil.move(expected_path, output_path)
                return True
        except Exception:
            pass

    # 5. Last resort fallback: check for high-res preview image (Pages 13+)
    if zipfile.is_zipfile(input_path):
        try:
            with zipfile.ZipFile(input_path, 'r') as zf:
                namelist = zf.namelist()
                for img_candidate in ["preview.jpg", "preview-web.jpg", "QuickLook/Preview.jpg"]:
                    if img_candidate in namelist:
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                            tf.write(zf.read(img_candidate))
                            tf_path = tf.name
                        try:
                            res = convert_image_to_pdf(tf_path, output_path)
                            if res:
                                return True
                        finally:
                            if os.path.exists(tf_path):
                                os.remove(tf_path)
        except Exception:
            pass

    return False



def convert_docx_with_pages(input_path: str, output_path: str) -> bool:
    """
    On macOS, converts .docx/.doc to high-fidelity PDF using Apple Pages AppleScript.
    """
    if not os.path.exists("/Applications/Pages.app") or not os.path.exists("/usr/bin/osascript"):
        return False
    try:
        abs_in = os.path.abspath(input_path)
        abs_out = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(abs_out), exist_ok=True)
        pgrep_res = subprocess.run(["/usr/bin/pgrep", "-x", "Pages"], stdout=subprocess.DEVNULL)
        was_running = (pgrep_res.returncode == 0)

        esc_in = abs_in.replace('"', '\\"')
        esc_out = abs_out.replace('"', '\\"')
        scpt = f'''
        tell application "Pages"
            set myDoc to open POSIX file "{esc_in}"
            export myDoc to POSIX file "{esc_out}" as PDF
            close myDoc saving no
        end tell
        '''
        res = subprocess.run(["/usr/bin/osascript", "-e", scpt], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
        if not was_running:
            subprocess.run(["/usr/bin/osascript", "-e", 'tell application "Pages" to quit saving no'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        return os.path.exists(abs_out) and os.path.getsize(abs_out) > 0
    except Exception:
        return False


def convert_pptx_with_keynote(input_path: str, output_path: str) -> bool:
    """
    On macOS, converts .pptx/.ppt to high-fidelity PDF using Apple Keynote AppleScript.
    """
    if not os.path.exists("/Applications/Keynote.app") or not os.path.exists("/usr/bin/osascript"):
        return False
    try:
        abs_in = os.path.abspath(input_path)
        abs_out = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(abs_out), exist_ok=True)
        pgrep_res = subprocess.run(["/usr/bin/pgrep", "-x", "Keynote"], stdout=subprocess.DEVNULL)
        was_running = (pgrep_res.returncode == 0)

        esc_in = abs_in.replace('"', '\\"')
        esc_out = abs_out.replace('"', '\\"')
        scpt = f'''
        tell application "Keynote"
            set myDoc to open POSIX file "{esc_in}"
            export myDoc to POSIX file "{esc_out}" as PDF
            close myDoc saving no
        end tell
        '''
        res = subprocess.run(["/usr/bin/osascript", "-e", scpt], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
        if not was_running:
            subprocess.run(["/usr/bin/osascript", "-e", 'tell application "Keynote" to quit saving no'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        return os.path.exists(abs_out) and os.path.getsize(abs_out) > 0
    except Exception:
        return False


def convert_docx_fallback(input_path: str, output_path: str) -> bool:
    """
    Fallback converter for .docx using python-docx and ReportLab.
    Used when LibreOffice and Apple Pages are not installed.
    """
    import docx
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib import colors

    # Try to load a unicode font for CJK / international text
    system_font_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/STHeiti Light.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    font_name = "Helvetica"
    for fp in system_font_paths:
        if os.path.exists(fp):
            try:
                sub = 0 if fp.lower().endswith(".ttc") else 0
                pdfmetrics.registerFont(TTFont("DocFont", fp, subfontIndex=sub))
                font_name = "DocFont"
                break
            except Exception:
                continue

    doc = docx.Document(input_path)
    page_width = 595.27 - 80  # A4 width (595.27) minus left+right margins (40 each) = 515.27 pt
    pdf = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    styles = getSampleStyleSheet()

    body_style = ParagraphStyle(
        'DocxBody',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10.0,
        leading=14.0,
        textColor=colors.black
    )
    heading_style = ParagraphStyle(
        'DocxHeading',
        parent=styles['Heading1'],
        fontName=font_name,
        fontSize=14.0,
        leading=18.0,
        spaceAfter=6,
        textColor=colors.HexColor("#1d1d1f")
    )

    story = []
    # Iterate through body elements in true sequential document order
    for child in doc.element.body:
        if child.tag.endswith('p'):
            p = docx.text.paragraph.Paragraph(child, doc)
            txt = p.text.strip()
            if not txt:
                story.append(Spacer(1, 4))
                continue
            clean_text = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if p.style and ('Heading' in p.style.name or 'Title' in p.style.name):
                story.append(Paragraph(clean_text, heading_style))
            else:
                story.append(Paragraph(clean_text, body_style))
                story.append(Spacer(1, 3))
        elif child.tag.endswith('tbl'):
            tbl = docx.table.Table(child, doc)
            n_rows = len(tbl.rows)
            n_cols = len(tbl.columns)
            if n_rows == 0 or n_cols == 0:
                continue

            # Calculate proportional column widths
            col_widths = None
            try:
                raw_w = [col.width for col in tbl.columns if col.width]
                if len(raw_w) == n_cols and sum(raw_w) > 0:
                    tot = sum(raw_w)
                    col_widths = [(w / tot) * page_width for w in raw_w]
            except Exception:
                pass

            if not col_widths or any(w <= 0 for w in col_widths):
                col_w_acc = [0.0] * n_cols
                col_w_cnt = [0] * n_cols
                for row in tbl.rows:
                    for c_idx, cell in enumerate(row.cells):
                        if cell.width:
                            col_w_acc[c_idx] += float(cell.width)
                            col_w_cnt[c_idx] += 1
                if all(cnt > 0 for cnt in col_w_cnt) and sum(col_w_acc) > 0:
                    tot = sum(col_w_acc)
                    col_widths = [(col_w_acc[c] / tot) * page_width for c in range(n_cols)]
                else:
                    col_widths = [page_width / n_cols] * n_cols

            table_data = []
            t_styles = [
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ]

            # Detect horizontal merged cells using cell._tc identity
            for r_idx, row in enumerate(tbl.rows):
                row_data = []
                visited_tcs = set()
                c = 0
                while c < len(row.cells):
                    cell = row.cells[c]
                    tc_id = id(cell._tc)
                    if tc_id in visited_tcs:
                        row_data.append('')
                        c += 1
                        continue
                    visited_tcs.add(tc_id)
                    span_end = c
                    while span_end + 1 < len(row.cells) and id(row.cells[span_end + 1]._tc) == tc_id:
                        span_end += 1
                    ct = cell.text.strip().replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    row_data.append(Paragraph(ct, body_style))
                    if span_end > c:
                        t_styles.append(('SPAN', (c, r_idx), (span_end, r_idx)))
                        for _ in range(c + 1, span_end + 1):
                            row_data.append('')
                    c = span_end + 1
                table_data.append(row_data)

            t = Table(table_data, colWidths=col_widths)
            t.setStyle(TableStyle(t_styles))
            story.append(t)
            story.append(Spacer(1, 6))

    if not story:
        story.append(Paragraph("Empty Document", body_style))

    pdf.build(story)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0


def convert_pptx_fallback(input_path: str, output_path: str) -> bool:
    """
    Fallback converter for .pptx using python-pptx and ReportLab.
    """
    from pptx import Presentation
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib import colors

    font_name = "Helvetica"
    system_font_paths = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for fp in system_font_paths:
        if os.path.exists(fp):
            try:
                sub = 0 if fp.lower().endswith(".ttc") else 0
                pdfmetrics.registerFont(TTFont("PPTFont", fp, subfontIndex=sub))
                font_name = "PPTFont"
                break
            except Exception:
                continue

    prs = Presentation(input_path)
    # Standard A4 slide layout landscape (841.89 x 595.28 pt)
    pdf = SimpleDocTemplate(
        output_path,
        pagesize=landscape(A4),
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'SlideTitle',
        parent=styles['Heading1'],
        fontName=font_name,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1d1d1f"),
        spaceAfter=12
    )
    body_style = ParagraphStyle(
        'SlideBody',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#333333")
    )

    from reportlab.platypus import PageBreak
    story = []

    for i, slide in enumerate(prs.slides):
        if i > 0:
            story.append(PageBreak())
        story.append(Paragraph(f"Slide {i+1}", ParagraphStyle('SlideNum', fontName=font_name, fontSize=9, textColor=colors.gray)))
        story.append(Spacer(1, 8))

        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    txt = paragraph.text.strip()
                    if txt:
                        clean_txt = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        story.append(Paragraph(clean_txt, body_style))
                        story.append(Spacer(1, 4))

    if not story:
        story.append(Paragraph("Empty Presentation", body_style))

    pdf.build(story)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0


def convert_image_to_pdf(input_path: str, output_path: str) -> bool:
    """
    Convert common image formats (.png, .jpg, .webp, .tiff, etc.) to standard A4 PDF.
    - Fits the image proportionally within standard A4 paper (595.28 x 841.89 pt).
    - Auto-selects Portrait or Landscape orientation to match image aspect ratio.
    - Centers image with standard printer-safe margins (18 pt ~ 6.35 mm).
    - Eliminates printer-clipping issues where only 1/4 of bottom-left was printed.
    - Handles RGBA / transparency cleanly with white background composite.
    - Applies EXIF orientation (ImageOps.exif_transpose) for mobile/camera images.
    - Supports multi-frame images (e.g. multi-page TIFF).
    """
    try:
        from PIL import ImageOps, ImageSequence

        frames = []
        with Image.open(input_path) as raw_img:
            for frame in ImageSequence.Iterator(raw_img):
                f = ImageOps.exif_transpose(frame)
                if f is None:
                    f = frame
                # Handle transparency (flatten onto white background)
                if f.mode in ("RGBA", "LA") or (f.mode == "P" and "transparency" in f.info):
                    rgba = f.convert("RGBA")
                    white_bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                    rgb_frame = Image.alpha_composite(white_bg, rgba).convert("RGB")
                elif f.mode != "RGB":
                    rgb_frame = f.convert("RGB")
                else:
                    rgb_frame = f.copy()
                frames.append(rgb_frame)

        if not frames:
            return False

        # A4 standard dimensions in PostScript points (72 pt/inch)
        A4_W = 595.28
        A4_H = 841.89
        margin = 18.0

        doc = fitz.open()
        for rgb_img in frames:
            img_w, img_h = rgb_img.size
            if img_w <= 0 or img_h <= 0:
                continue

            # Auto orientation: Landscape if wider than tall, else Portrait
            if img_w > img_h:
                page_w, page_h = A4_H, A4_W
            else:
                page_w, page_h = A4_W, A4_H

            # Safe margins for laser printers (18 pt ~ 6.35 mm)
            avail_w = max(10.0, page_w - (2 * margin))
            avail_h = max(10.0, page_h - (2 * margin))

            # Proportional scale
            scale = min(avail_w / img_w, avail_h / img_h)
            target_w = img_w * scale
            target_h = img_h * scale

            # Center on A4 sheet
            x0 = margin + (avail_w - target_w) / 2.0
            y0 = margin + (avail_h - target_h) / 2.0
            rect = fitz.Rect(x0, y0, x0 + target_w, y0 + target_h)

            # Save frame to memory buffer
            img_buf = io.BytesIO()
            rgb_img.save(img_buf, format="JPEG", quality=95)
            img_bytes = img_buf.getvalue()

            page = doc.new_page(width=page_w, height=page_h)
            page.insert_image(rect, stream=img_bytes)

        if len(doc) > 0:
            doc.save(output_path, garbage=3, deflate=True)
            doc.close()
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        doc.close()
        return False
    except Exception as e:
        print(f"Error converting image to PDF: {e}")
        return False



def convert_text_to_pdf(input_path: str, output_path: str) -> bool:
    """Convert .txt or .md files to PDF."""
    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    doc = fitz.open()
    lines = content.splitlines()
    lines_per_page = 45
    for i in range(0, max(1, len(lines)), lines_per_page):
        page = doc.new_page(width=595, height=842) # A4
        chunk = "\n".join(lines[i:i + lines_per_page])
        page.insert_text((40, 50), chunk, fontsize=10)
    doc.save(output_path)
    doc.close()
    return True


def convert_to_pdf(input_file: str, output_pdf_path: str) -> str:
    """
    Universal converter entrypoint.
    Takes any input document/image and converts to a standardized PDF.
    Returns the absolute path to the output PDF.
    """
    ext = Path(input_file).suffix.lower()

    # Ensure output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)

    # 1. Native PDF
    if ext == ".pdf":
        shutil.copyfile(input_file, output_pdf_path)
        return output_pdf_path

    # 2. Apple Pages (.pages)
    if ext == ".pages":
        success = convert_pages_to_pdf(input_file, output_pdf_path)
        if success:
            return output_pdf_path
        raise ValueError(
            "Apple Pages document could not be converted: QuickLook preview not found. "
            "Please export as PDF from Pages on your Mac/iPad."
        )

    # 3. Images
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".gif"):
        if convert_image_to_pdf(input_file, output_pdf_path):
            return output_pdf_path
        raise ValueError(f"Failed to convert image {ext} to PDF.")

    # 4. Plain Text / Markdown
    if ext in (".txt", ".md", ".log", ".csv"):
        if convert_text_to_pdf(input_file, output_pdf_path):
            return output_pdf_path

    # 5. Word / PowerPoint (.docx, .doc, .pptx, .ppt)
    # 5a. macOS Native Apple Pages / Keynote conversion (highest visual fidelity)
    if ext in (".docx", ".doc"):
        if convert_docx_with_pages(input_file, output_pdf_path):
            return output_pdf_path

    if ext in (".pptx", ".ppt"):
        if convert_pptx_with_keynote(input_file, output_pdf_path):
            return output_pdf_path

    # 5b. Headless LibreOffice
    soffice = find_libreoffice_executable()
    if soffice:
        out_dir = os.path.dirname(os.path.abspath(output_pdf_path))
        cmd = [
            soffice,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", out_dir,
            input_file
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
        # Check generated PDF name
        expected_name = Path(input_file).stem + ".pdf"
        expected_path = os.path.join(out_dir, expected_name)
        if os.path.exists(expected_path):
            if expected_path != output_pdf_path:
                shutil.move(expected_path, output_pdf_path)
            return output_pdf_path

    # 5c. Python fallbacks (ReportLab with Unicode support & table SPAN)
    if ext in (".docx", ".doc"):
        if convert_docx_fallback(input_file, output_pdf_path):
            return output_pdf_path

    if ext in (".pptx", ".ppt"):
        if convert_pptx_fallback(input_file, output_pdf_path):
            return output_pdf_path

    raise ValueError(f"Unsupported file format '{ext}' or conversion failed.")
