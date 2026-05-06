"""
pdf_builder.py
Generates a professional internship report PDF using ReportLab.
No pdflatex / LaTeX installation required.
"""

import os
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, Image, HRFlowable, KeepTogether
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.pdfgen import canvas

# ── Colours ──────────────────────────────────────────────────────────────────
BLACK   = colors.HexColor("#000000")
DARK    = colors.HexColor("#1a1a2e")
ACCENT  = colors.HexColor("#16213e")
TITLE_C = colors.HexColor("#0f3460")
GREY    = colors.HexColor("#555555")
LGREY   = colors.HexColor("#f5f5f5")

W, H = A4
MARGIN = 2.5 * cm

# ── AI content parser (same as builder.py) ───────────────────────────────────

def parse_ai_content(ai_text):
    sections = {}
    pattern = re.compile(r"===([A-Z0-9_]+)===\s*(.*?)(?====|$)", re.DOTALL)
    for m in pattern.finditer(ai_text):
        sections[m.group(1).strip()] = m.group(2).strip()
    return sections

def clean_text(text):
    """Remove leading/trailing whitespace and normalize newlines."""
    return (text or "").strip().replace("\r\n", "\n").replace("\r", "\n")

# ── Styles ────────────────────────────────────────────────────────────────────

def make_styles():
    base = getSampleStyleSheet()

    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    styles = {
        "cover_uni":    S("cu", fontName="Helvetica-Bold", fontSize=14, alignment=TA_CENTER, textColor=TITLE_C, spaceAfter=4),
        "cover_sub":    S("cs", fontName="Helvetica",      fontSize=11, alignment=TA_CENTER, textColor=GREY,    spaceAfter=3),
        "cover_title":  S("ct", fontName="Helvetica-Bold", fontSize=16, alignment=TA_CENTER, textColor=BLACK,   spaceAfter=6),
        "cover_name":   S("cn", fontName="Helvetica-Bold", fontSize=13, alignment=TA_CENTER, textColor=TITLE_C, spaceAfter=3),
        "cover_dept":   S("cd", fontName="Helvetica-Bold", fontSize=12, alignment=TA_CENTER, textColor=BLACK,   spaceAfter=3),
        "chapter_h":    S("ch", fontName="Helvetica-Bold", fontSize=18, alignment=TA_LEFT,   textColor=TITLE_C, spaceBefore=12, spaceAfter=10),
        "section_h":    S("sh", fontName="Helvetica-Bold", fontSize=13, alignment=TA_LEFT,   textColor=DARK,    spaceBefore=10, spaceAfter=5),
        "body":         S("bd", fontName="Helvetica",      fontSize=11, alignment=TA_JUSTIFY, leading=17, spaceAfter=6),
        "body_c":       S("bc", fontName="Helvetica",      fontSize=11, alignment=TA_CENTER,  leading=17, spaceAfter=4),
        "bullet":       S("bl", fontName="Helvetica",      fontSize=11, alignment=TA_LEFT,    leading=17, spaceAfter=3, leftIndent=18, bulletIndent=6),
        "caption":      S("cp", fontName="Helvetica-Oblique", fontSize=9, alignment=TA_CENTER, textColor=GREY, spaceAfter=8),
        "cert_head":    S("ceh", fontName="Helvetica-Bold", fontSize=13, alignment=TA_CENTER, spaceBefore=6, spaceAfter=4),
        "cert_body":    S("ceb", fontName="Helvetica",      fontSize=11, alignment=TA_JUSTIFY, leading=18, spaceAfter=6),
        "sig_label":    S("sl",  fontName="Helvetica",      fontSize=10, alignment=TA_CENTER, textColor=GREY),
        "sig_name":     S("sn",  fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER),
        "toc_title":    S("tt",  fontName="Helvetica-Bold", fontSize=14, alignment=TA_CENTER, spaceBefore=10, spaceAfter=12, textColor=TITLE_C),
        "toc_entry":    S("te",  fontName="Helvetica",      fontSize=11, alignment=TA_LEFT,   leading=20),
        "toc_ch":       S("tc",  fontName="Helvetica-Bold", fontSize=11, alignment=TA_LEFT,   leading=20),
        "page_h":       S("ph",  fontName="Helvetica-Bold", fontSize=9,  alignment=TA_CENTER, textColor=GREY),
        "small_c":      S("sc",  fontName="Helvetica",      fontSize=9,  alignment=TA_CENTER, textColor=GREY),
    }
    return styles

# ── Helper flowables ──────────────────────────────────────────────────────────

def HR():
    return HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc"), spaceAfter=6, spaceBefore=4)

def parse_body_to_flowables(text, styles):
    """Convert AI text (with bullets) to ReportLab flowables."""
    flowables = []
    if not text:
        return flowables
    lines = clean_text(text).split("\n")
    para_buf = []
    in_bullet = False

    def flush_para():
        if para_buf:
            combined = " ".join(para_buf).strip()
            if combined:
                flowables.append(Paragraph(combined, styles["body"]))
            para_buf.clear()

    for line in lines:
        s = line.strip()
        is_bullet = s.startswith(("• ", "- ", "* ")) or (len(s) > 2 and s[0].isdigit() and s[1] in ".):")
        if is_bullet:
            flush_para()
            item = re.sub(r"^[•\-\*\d]+[\.\):\s]+", "", s).strip()
            flowables.append(Paragraph(f"• &nbsp; {item}", styles["bullet"]))
        elif s == "":
            flush_para()
        else:
            para_buf.append(s)

    flush_para()
    return flowables

def img_flowable(path, caption, styles, max_w=12*cm, max_h=8*cm):
    """Return [Image, caption Paragraph] if path exists, else []."""
    if not path or not os.path.exists(path):
        return []
    try:
        img = Image(path, max_w, max_h, kind="proportional")
        img.hAlign = "CENTER"
        cap = Paragraph(caption, styles["caption"])
        return [Spacer(1, 6), img, cap, Spacer(1, 4)]
    except Exception:
        return []

# ── Chapter header helper ─────────────────────────────────────────────────────

def chapter_header(num, title, styles):
    return [
        Paragraph(f"Chapter {num}", ParagraphStyle("cnum", fontName="Helvetica", fontSize=11, textColor=GREY, alignment=TA_LEFT)),
        Paragraph(title.upper(), styles["chapter_h"]),
        HR(),
        Spacer(1, 6),
    ]

def section_header(title, styles):
    return [Paragraph(title, styles["section_h"]), Spacer(1, 2)]

# ── Page template (header/footer) ─────────────────────────────────────────────

class ReportDoc(SimpleDocTemplate):
    def __init__(self, path, student_name, usn, title, **kw):
        super().__init__(path, **kw)
        self.student_name = student_name
        self.usn          = usn
        self.title        = title

    def handle_pageBegin(self):
        super().handle_pageBegin()

    def afterPage(self):
        pass


def _header_footer(canvas_obj, doc, student_name, title):
    canvas_obj.saveState()
    # Footer line
    canvas_obj.setStrokeColor(colors.HexColor("#cccccc"))
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(MARGIN, 1.8*cm, W - MARGIN, 1.8*cm)
    # Footer text
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(GREY)
    canvas_obj.drawString(MARGIN, 1.3*cm, student_name)
    canvas_obj.drawRightString(W - MARGIN, 1.3*cm, title[:60])
    canvas_obj.drawCentredString(W/2, 1.3*cm, str(doc.page))
    # Header line (not on first few pages)
    if doc.page > 4:
        canvas_obj.line(MARGIN, H - 1.8*cm, W - MARGIN, H - 1.8*cm)
        canvas_obj.drawCentredString(W/2, H - 1.4*cm, "Internship Report — Vemana Institute of Technology")
    canvas_obj.restoreState()

# ── MAIN BUILD FUNCTION ───────────────────────────────────────────────────────

def build_pdf(data, images_dir, output_pdf_path):
    """
    Build the full internship report PDF.
    data: dict with all form fields + ai_content + chapter_images list
    images_dir: folder where uploaded images are stored
    output_pdf_path: where to save the PDF
    """
    styles = make_styles()

    # ── Unpack data ──────────────────────────────────────────────────────────
    name             = (data.get("name", "Student Name")).upper()
    name_title       = data.get("name", "Student Name")
    usn              = data.get("usn", "")
    department       = data.get("department", "")
    degree           = data.get("degree", "Bachelor of Engineering")
    academic_year    = data.get("academic_year", "2025-2026")
    company          = data.get("company_name", "Company")
    intern_title     = data.get("internship_title", "Internship")
    start_date       = data.get("start_date", "")
    end_date         = data.get("end_date", "")
    duration         = f"{start_date} to {end_date}" if start_date and end_date else ""
    ext_sup          = data.get("external_supervisor", "")
    int_sup          = data.get("internal_supervisor", "")
    hod              = data.get("hod", "")
    principal        = "Dr. Vijayasimha Reddy B G"

    dept_logo_fn     = data.get("dept_logo_filename", "")
    company_logo_fn  = data.get("company_logo_filename", "")
    cert_image_fn    = data.get("cert_image_filename", "")

    dept_logo_path    = os.path.join(images_dir, dept_logo_fn)    if dept_logo_fn    else ""
    company_logo_path = os.path.join(images_dir, company_logo_fn) if company_logo_fn else ""
    cert_path         = os.path.join(images_dir, cert_image_fn)   if cert_image_fn   else ""

    # Chapter images dict: {ch_key: [{filename, caption}]}
    ch_img_map = {}
    for item in data.get("chapter_images", []):
        ch  = item.get("chapter", "ch1")
        fn  = item.get("filename", "")
        cap = item.get("caption", "Figure")
        ch_img_map.setdefault(ch, []).append({"path": os.path.join(images_dir, fn), "caption": cap})

    def ch_imgs(key):
        flowables = []
        for img in ch_img_map.get(key, []):
            flowables.extend(img_flowable(img["path"], img["caption"], styles))
        return flowables

    # AI content
    ai_raw = data.get("ai_content", "")
    sec    = parse_ai_content(ai_raw)

    def S(key, fallback=""):
        return clean_text(sec.get(key, fallback))

    def body(key, fallback=""):
        return parse_body_to_flowables(S(key, fallback), styles)

    # ── Document ─────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=2.5*cm, bottomMargin=2.5*cm,
        title=f"Internship Report — {name_title}",
        author=name_title,
    )

    story = []
    hf = lambda c, d: _header_footer(c, d, name_title, intern_title)

    # ═══════════════════════════════════════════════════════════════════
    # TITLE PAGE
    # ═══════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 0.5*cm))

    # Dept logo
    logo_flws = img_flowable(dept_logo_path, "", styles, max_w=4*cm, max_h=3*cm)
    if logo_flws:
        story.extend(logo_flws)
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("VISVESVARAYA TECHNOLOGICAL UNIVERSITY", styles["cover_uni"]))
    story.append(Paragraph("Jnana Sangama, Belagavi – 590018", styles["cover_sub"]))
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("An Internship Report", styles["cover_title"]))
    story.append(Paragraph("On", styles["cover_sub"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(f'"{intern_title}"', styles["cover_title"]))
    if duration:
        story.append(Paragraph(duration, styles["cover_sub"]))
    story.append(Spacer(1, 0.8*cm))
    story.append(Paragraph("Submitted in partial fulfillment of the requirements for the award of the degree of", styles["body_c"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(degree, styles["cover_name"]))
    story.append(Paragraph("in", styles["cover_sub"]))
    story.append(Paragraph(department, styles["cover_name"]))
    story.append(Spacer(1, 0.8*cm))
    story.append(Paragraph("Submitted by", styles["cover_sub"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(name, styles["cover_name"]))
    story.append(Paragraph(usn, styles["cover_name"]))
    story.append(Spacer(1, 1.2*cm))
    story.append(HR())
    story.append(Paragraph(f"DEPARTMENT OF {department.upper()}", styles["cover_dept"]))
    story.append(Paragraph("VEMANA INSTITUTE OF TECHNOLOGY", styles["cover_dept"]))
    story.append(Paragraph("BENGALURU – 560034", styles["cover_sub"]))
    story.append(Paragraph(academic_year, styles["cover_sub"]))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # CERTIFICATE PAGE
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("Karnataka ReddyJana Sangha", styles["cert_head"]))
    story.append(Paragraph("VEMANA INSTITUTE OF TECHNOLOGY", styles["cert_head"]))
    story.append(Paragraph("(Affiliated to Visvesvaraya Technological University, Belagavi)", styles["body_c"]))
    story.append(Paragraph("Koramangala, Bengaluru – 560034", styles["body_c"]))
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph(f"DEPARTMENT OF {department.upper()}", styles["cert_head"]))
    story.append(Spacer(1, 0.6*cm))
    story.append(HR())
    story.append(Paragraph("CERTIFICATE", ParagraphStyle("CERT", fontName="Helvetica-Bold", fontSize=16, alignment=TA_CENTER, textColor=TITLE_C, spaceBefore=8, spaceAfter=12)))
    story.append(HR())
    story.append(Spacer(1, 0.4*cm))

    cert_text = (
        f'This is to certify that the internship entitled "<b>{intern_title}</b>" is a bonafide work carried out by '
        f'<b>{name} ({usn})</b> in partial fulfilment of the requirements for the award of {degree} degree in '
        f'{department}, Visvesvaraya Technological University, Belagavi, during the academic year {academic_year}.'
    )
    story.append(Paragraph(cert_text, styles["cert_body"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "It is certified that all corrections and suggestions indicated for internal assessment have been duly "
        "incorporated in the report. The internship report has been approved as it satisfies the academic "
        "requirements prescribed for the said degree.",
        styles["cert_body"]
    ))
    story.append(Spacer(1, 1.2*cm))

    # Signature table
    sig_data = [
        [Paragraph("Internal Supervisor", styles["sig_label"]),
         Paragraph("External Supervisor", styles["sig_label"]),
         Paragraph("HOD", styles["sig_label"]),
         Paragraph("Principal", styles["sig_label"])],
        [Paragraph(f"({int_sup})", styles["sig_name"]),
         Paragraph(f"({ext_sup})", styles["sig_name"]),
         Paragraph(f"({hod})", styles["sig_name"]),
         Paragraph(f"({principal})", styles["sig_name"])],
    ]
    sig_table = Table(sig_data, colWidths=[(W - 2*MARGIN)/4]*4)
    sig_table.setStyle(TableStyle([
        ("ALIGN",       (0,0), (-1,-1), "CENTER"),
        ("VALIGN",      (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",  (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 0.8*cm))
    story.append(Paragraph("Name of the Examiners" + "&nbsp;" * 60 + "Signature with Date", styles["cert_body"]))
    story.append(Paragraph("1.", styles["cert_body"]))
    story.append(Paragraph("2.", styles["cert_body"]))

    # Company certificate image (full page)
    if cert_path and os.path.exists(cert_path):
        story.append(PageBreak())
        try:
            ci = Image(cert_path, W - 2*MARGIN, H - 4*cm, kind="proportional")
            ci.hAlign = "CENTER"
            story.append(ci)
        except Exception:
            pass

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # ACKNOWLEDGEMENT
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("ACKNOWLEDGEMENT", styles["chapter_h"]))
    story.append(HR())
    story.append(Spacer(1, 0.3*cm))
    ack_text = S("ACKNOWLEDGEMENT",
        f"I sincerely thank Visvesvaraya Technological University (VTU) for providing this invaluable "
        f"opportunity to undertake the internship as part of my academic curriculum. I express my sincere gratitude "
        f"to Dr. Vijayasimha Reddy B G, Principal, Vemana Institute of Technology, for providing the necessary "
        f"support and infrastructure. I extend my heartfelt thanks to {hod}, Head of the Department, for constant "
        f"guidance and encouragement. I am grateful to my internal supervisor {int_sup} and external supervisor "
        f"{ext_sup} from {company} for their valuable guidance. I also thank all faculty and staff of the "
        f"Department of {department} for their continuous support."
    )
    story.extend(parse_body_to_flowables(ack_text, styles))
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(name_title, styles["body"]))
    story.append(Paragraph(usn, styles["body"]))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # ABSTRACT
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("ABSTRACT", styles["chapter_h"]))
    story.append(HR())
    story.append(Spacer(1, 0.3*cm))
    story.extend(body("ABSTRACT", "Abstract not provided."))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # TABLE OF CONTENTS (manual)
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("TABLE OF CONTENTS", styles["toc_title"]))
    story.append(HR())

    toc_entries = [
        ("Acknowledgement",              None),
        ("Abstract",                     None),
        ("Chapter 1: Introduction",      [
            "1.1 Internship Scope and Objectives",
            f"1.2 Relevance of {intern_title} to {department}",
            "1.3 Evolution of Practices in the Field",
            "1.4 Current Trends and Technologies",
        ]),
        ("Chapter 2: Organisation Profile", [
            "2.1 Introduction",
            "2.2 Vision and Mission of the Organization",
            "2.3 Programs and Services Offered",
            "2.4 Organizational Impact and Reach",
            "2.5 Core Values",
        ]),
        ("Chapter 3: Work Done / Methodology", [
            "3.1 Overview of Internship Work",
            "3.2 Tools and Technologies Used",
            "3.3 Work Process and Methodology",
            "3.4 Key Project and Case Study",
            "3.5 Challenges Faced",
            "3.6 Solutions Implemented",
        ]),
        ("Chapter 4: Results and Discussion", [
            "4.1 Outcomes of the Work",
            "4.2 Learning Outcomes",
            "4.3 Analysis",
        ]),
        ("Chapter 5: Conclusion", [
            "5.1 Summary",
            "5.2 Personal Growth",
            "5.3 Future Scope",
        ]),
    ]

    for title, subs in toc_entries:
        story.append(Paragraph(title, styles["toc_ch"]))
        if subs:
            for sub in subs:
                story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;{sub}", styles["toc_entry"]))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # CHAPTER 1 — INTRODUCTION
    # ═══════════════════════════════════════════════════════════════════
    story.extend(chapter_header(1, "Introduction", styles))
    story.extend(body("CH1_INTRO"))
    story.extend(section_header("1.1 Internship Scope and Objectives", styles))
    story.extend(body("CH1_SCOPE"))
    story.extend(section_header(f"1.2 Relevance of {intern_title} to {department}", styles))
    story.extend(body("CH1_RELEVANCE"))
    story.extend(section_header("1.3 Evolution of Practices in the Field", styles))
    story.extend(body("CH1_EVOLUTION"))
    story.extend(section_header("1.4 Current Trends and Technologies", styles))
    story.extend(body("CH1_TRENDS"))
    story.extend(ch_imgs("ch1"))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # CHAPTER 2 — ORGANISATION PROFILE
    # ═══════════════════════════════════════════════════════════════════
    story.extend(chapter_header(2, "Organisation Profile", styles))
    story.extend(body("CH2_INTRO"))
    story.extend(section_header("2.1 Introduction", styles))
    story.extend(parse_body_to_flowables(
        f"{company} is a leading organization that provides structured learning, "
        f"training, and internship programs to engineering students and professionals.", styles))
    # Company logo
    story.extend(img_flowable(company_logo_path, f"{company} — Company Logo", styles, max_w=8*cm, max_h=5*cm))
    story.extend(section_header("2.2 Vision and Mission of the Organization", styles))
    story.extend(body("CH2_VISION"))
    story.extend(section_header("2.3 Programs and Services Offered", styles))
    story.extend(body("CH2_PROGRAMS"))
    story.extend(section_header("2.4 Organizational Impact and Reach", styles))
    story.extend(body("CH2_IMPACT"))
    story.extend(section_header("2.5 Core Values", styles))
    story.extend(body("CH2_VALUES"))
    story.extend(ch_imgs("ch2"))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # CHAPTER 3 — WORK DONE / METHODOLOGY
    # ═══════════════════════════════════════════════════════════════════
    story.extend(chapter_header(3, "Work Done / Methodology", styles))
    story.extend(body("CH3_OVERVIEW"))
    story.extend(section_header("3.1 Overview of Internship Work", styles))
    story.extend(parse_body_to_flowables(
        f"The internship at {company} provided structured exposure to the field of {intern_title}. "
        f"The work involved hands-on application of domain knowledge in a professional setting.", styles))
    story.extend(section_header("3.2 Tools and Technologies Used", styles))
    story.extend(body("CH3_TOOLS"))
    story.extend(section_header("3.3 Work Process and Methodology", styles))
    story.extend(body("CH3_PROCESS"))
    story.extend(section_header("3.4 Key Project and Case Study", styles))
    story.extend(body("CH3_CASESTUDY"))
    story.extend(ch_imgs("ch3"))
    story.extend(section_header("3.5 Challenges Faced", styles))
    story.extend(body("CH3_CHALLENGES"))
    story.extend(section_header("3.6 Solutions Implemented", styles))
    story.extend(body("CH3_SOLUTIONS"))
    story.extend(ch_imgs("ch3_extra"))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # CHAPTER 4 — RESULTS AND DISCUSSION
    # ═══════════════════════════════════════════════════════════════════
    story.extend(chapter_header(4, "Results and Discussion", styles))
    story.extend(body("CH4_INTRO"))
    story.extend(ch_imgs("ch4"))
    story.extend(section_header("4.1 Outcomes of the Work", styles))
    story.extend(body("CH4_OUTCOMES"))
    story.extend(section_header("4.2 Learning Outcomes", styles))
    story.extend(body("CH4_LEARNING"))
    story.extend(section_header("4.3 Analysis", styles))
    story.extend(body("CH4_ANALYSIS"))
    story.extend(ch_imgs("ch4_extra"))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # CHAPTER 5 — CONCLUSION
    # ═══════════════════════════════════════════════════════════════════
    story.extend(chapter_header(5, "Conclusion", styles))
    story.extend(body("CH5_INTRO"))
    story.extend(ch_imgs("ch5"))
    story.extend(section_header("5.1 Summary", styles))
    story.extend(body("CH5_SUMMARY"))
    story.extend(section_header("5.2 Personal Growth", styles))
    story.extend(body("CH5_GROWTH"))
    story.extend(section_header("5.3 Future Scope", styles))
    story.extend(body("CH5_FUTURE"))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # BUILD
    # ═══════════════════════════════════════════════════════════════════
    doc.build(story, onFirstPage=hf, onLaterPages=hf)
    return output_pdf_path
