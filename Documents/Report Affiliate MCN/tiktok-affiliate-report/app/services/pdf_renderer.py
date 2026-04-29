"""
PDFRenderer — clean, simple, professional report using ReportLab.
"""
from __future__ import annotations

import os
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph,
    Spacer, Table, TableStyle, PageBreak, HRFlowable, Image,
)

from app.services.report_gen import ReportData, format_rupiah, format_number

# ── Palette ──────────────────────────────────────────────────────────────────
C_PRIMARY   = colors.HexColor("#2c3e50")   # dark blue-gray — header bg
C_ACCENT    = colors.HexColor("#3498db")   # bright blue — section titles
C_ACCENT2   = colors.HexColor("#e74c3c")   # coral red — highlights
C_LIGHT     = colors.HexColor("#ecf0f1")   # light gray bg
C_LIGHT2    = colors.HexColor("#d5dbdb")   # medium gray stripe
C_BORDER    = colors.HexColor("#bdc3c7")
C_WHITE     = colors.white
C_BLACK     = colors.HexColor("#2c3e50")
C_GRAY      = colors.HexColor("#7f8c8d")
C_POSITIVE  = colors.HexColor("#27ae60")   # green
C_NEGATIVE  = colors.HexColor("#e74c3c")   # red

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


# ── Styles ───────────────────────────────────────────────────────────────────

def S(name, **kw):
    defaults = dict(fontName="Helvetica", fontSize=10, textColor=C_BLACK, leading=14)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


STYLES = {
    "cover_brand":   S("cb", fontName="Helvetica-Bold", fontSize=36, textColor=C_WHITE, alignment=TA_CENTER, leading=42),
    "cover_sub":     S("cs", fontSize=16, textColor=C_ACCENT, alignment=TA_CENTER, leading=22),
    "cover_period":  S("cp", fontSize=12, textColor=colors.HexColor("#bdc3c7"), alignment=TA_CENTER),
    "cover_meta":    S("cm", fontSize=9, textColor=colors.HexColor("#95a5a6"), alignment=TA_CENTER),
    "section":       S("sec", fontName="Helvetica-Bold", fontSize=16, textColor=C_WHITE, leading=20),
    "body":          S("body", fontSize=10, leading=15),
    "body_bold":     S("bb", fontName="Helvetica-Bold", fontSize=11, leading=16),
    "small":         S("sm", fontSize=9, textColor=C_GRAY, leading=13),
    "th":            S("th", fontName="Helvetica-Bold", fontSize=10, textColor=C_WHITE, alignment=TA_LEFT),
    "td":            S("td", fontSize=10, textColor=C_BLACK, alignment=TA_LEFT),
    "td_center":     S("tdc", fontSize=10, textColor=C_BLACK, alignment=TA_CENTER),
    "td_right":      S("tdr", fontSize=10, textColor=C_BLACK, alignment=TA_RIGHT),
    "metric_val":    S("mv", fontName="Helvetica-Bold", fontSize=18, textColor=C_ACCENT, alignment=TA_CENTER, leading=22),
    "metric_lbl":    S("ml", fontSize=9, textColor=C_GRAY, alignment=TA_CENTER, leading=11),
    "placeholder":   S("ph", fontSize=10, textColor=C_GRAY, fontName="Helvetica-Oblique"),
    "gmv_big":       S("gb", fontName="Helvetica-Bold", fontSize=28, textColor=C_WHITE, alignment=TA_CENTER, leading=34),
    "gmv_lbl":       S("gl", fontSize=11, textColor=C_LIGHT, alignment=TA_CENTER),
}


def _tbl_style(header_bg=C_ACCENT, stripe=C_LIGHT):
    return TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  header_bg),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_WHITE, stripe]),
        ("GRID",          (0, 0), (-1, -1), 0.5, C_BORDER),
        ("LINEBELOW",     (0, 0), (-1, 0),  2, header_bg),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ])


def _make_table(headers, rows, col_widths, stripe=C_LIGHT, row_height=None):
    data = [[Paragraph(h, STYLES["th"]) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), STYLES["td"]) for c in row])
    
    # Use fixed row height if provided, otherwise let ReportLab calculate
    if row_height:
        tbl = Table(data, colWidths=col_widths, rowHeights=[row_height] * len(data), repeatRows=1)
    else:
        tbl = Table(data, colWidths=col_widths, repeatRows=1)
    
    tbl.setStyle(_tbl_style(stripe=stripe))
    return tbl


def _section_title(text):
    # Modern section header dengan background warna
    tbl = Table([[Paragraph(text, STYLES["section"])]], colWidths=[CONTENT_W])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), C_ACCENT),
        ("TOPPADDING",   (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
        ("LEFTPADDING",  (0, 0), (-1, -1), 15),
        ("RIGHTPADDING", (0, 0), (-1, -1), 15),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return [tbl, Spacer(1, 4 * mm)]


def _image_grid(image_paths: list, max_width: float = None, label: str = "Screenshot") -> list:
    """
    Render daftar gambar dalam grid yang rapi.
    - Setiap gambar di halaman baru (PageBreak sebelum gambar)
    - Gambar full width, aspect ratio dipertahankan
    - 2 gambar: side by side di halaman yang sama
    - 3+ gambar: tiap gambar di halaman baru
    """
    if not image_paths:
        return []

    valid_paths = []
    for p in image_paths:
        if not os.path.isabs(p):
            p = os.path.join(os.getcwd(), p)
        if os.path.isfile(p):
            valid_paths.append(p)

    if not valid_paths:
        return []

    W = max_width or CONTENT_W
    MAX_H = PAGE_H - 2 * MARGIN - 25 * mm

    def _load_image_proportional(path, max_w, max_h):
        """Load image dengan scale proporsional, tidak pernah distorsi."""
        try:
            from PIL import Image as PILImage
            with PILImage.open(path) as pil_img:
                orig_w_px, orig_h_px = pil_img.size
                
            # Gunakan pixel langsung, asumsikan 96 DPI sebagai default
            # Convert pixel ke points (1 inch = 72 points, default screen = 96 DPI)
            orig_w_pt = orig_w_px * 72 / 96
            orig_h_pt = orig_h_px * 72 / 96

            # Scale agar fit dalam max_w x max_h, pertahankan aspect ratio
            scale_w = max_w / orig_w_pt
            scale_h = max_h / orig_h_pt
            scale = min(scale_w, scale_h)
            
            # Jangan upscale terlalu besar (max 150% dari ukuran asli)
            scale = min(scale, 1.5)

            new_w = orig_w_pt * scale
            new_h = orig_h_pt * scale

            return Image(path, width=new_w, height=new_h)
        except ImportError:
            # PIL tidak tersedia — gunakan ReportLab langsung
            img = Image(path)
            iw, ih = img.imageWidth, img.imageHeight
            if iw and ih:
                scale = min(max_w / iw, max_h / ih, 1.5)
                return Image(path, width=iw * scale, height=ih * scale)
            return Image(path, width=max_w, height=max_h * 0.6)
        except Exception as e:
            # Fallback: coba load dengan ukuran default
            try:
                img = Image(path)
                iw, ih = img.imageWidth, img.imageHeight
                if iw and ih:
                    scale = min(max_w / iw, max_h / ih, 1.5)
                    return Image(path, width=iw * scale, height=ih * scale)
            except Exception:
                pass
            return Image(path, width=max_w, height=max_h * 0.6)

    n = len(valid_paths)
    items = []

    if n == 1:
        items.append(PageBreak())
        try:
            img = _load_image_proportional(valid_paths[0], W, MAX_H)
            items.append(img)
        except Exception:
            pass

    elif n == 2:
        items.append(PageBreak())
        col_w = (W - 4 * mm) / 2
        max_h_2col = MAX_H

        row_cells = []
        for path in valid_paths:
            try:
                img = _load_image_proportional(path, col_w - 4 * mm, max_h_2col)
                cell_tbl = Table([[img]], colWidths=[col_w - 4 * mm])
                cell_tbl.setStyle(TableStyle([
                    ("BOX", (0, 0), (-1, -1), 0.5, C_BORDER),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]))
                row_cells.append(cell_tbl)
            except Exception:
                row_cells.append(Paragraph("", STYLES["small"]))

        grid = Table([row_cells], colWidths=[col_w, col_w])
        grid.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        items.append(grid)

    else:
        # 3+ gambar — tiap gambar di halaman baru
        for path in valid_paths:
            items.append(PageBreak())
            try:
                img = _load_image_proportional(path, W, MAX_H)
                items.append(img)
            except Exception:
                pass

    return items


def _metric_cards(items):
    """items: list of (label, value) — render as a row of cards."""
    n = len(items)
    gap = 5 * mm
    w = (CONTENT_W - (n - 1) * gap) / n

    # Build table with proper cell structure
    data = []
    # Value row
    val_row = []
    for label, value in items:
        # Wrap value in paragraph with proper styling and word wrap
        val_row.append(Paragraph(str(value), STYLES["metric_val"]))
    data.append(val_row)
    
    # Label row
    lbl_row = []
    for label, value in items:
        lbl_row.append(Paragraph(str(label), STYLES["metric_lbl"]))
    data.append(lbl_row)

    tbl = Table(data, colWidths=[w] * n, rowHeights=[18 * mm, 8 * mm])
    cmds = [
        ("BACKGROUND",   (0, 0), (-1, -1), C_WHITE),
        ("TOPPADDING",   (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING",(0, 0), (-1, 0), 3),
        ("TOPPADDING",   (0, 1), (-1, 1), 3),
        ("BOTTOMPADDING",(0, 1), (-1, 1), 8),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, 0), "BOTTOM"),  # Value aligned to bottom
        ("VALIGN",       (0, 1), (-1, 1), "TOP"),     # Label aligned to top
        ("BOX",          (0, 0), (-1, -1), 1.5, C_BORDER),
        ("INNERGRID",    (0, 0), (-1, -1), 0.5, C_LIGHT2),
    ]
    for i in range(n):
        cmds.append(("LINEABOVE", (i, 0), (i, 0), 4, C_ACCENT))
    tbl.setStyle(TableStyle(cmds))
    return tbl


def _text_block(text):
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
    tbl = Table([[Paragraph(safe, STYLES["body"])]], colWidths=[CONTENT_W - 10 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), C_LIGHT),
        ("LINEBEFORE",   (0, 0), (0, -1),  4, C_ACCENT2),
        ("TOPPADDING",   (0, 0), (-1, -1), 15),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 15),
        ("LEFTPADDING",  (0, 0), (-1, -1), 15),
        ("RIGHTPADDING", (0, 0), (-1, -1), 15),
    ]))
    return tbl


# ── Page numbering ────────────────────────────────────────────────────────────

def _on_page(canvas, doc, brand, batch):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(C_GRAY)
    footer = f"{brand} — Batch {batch}  |  Halaman {doc.page}"
    canvas.drawCentredString(PAGE_W / 2, 12 * mm, footer)
    canvas.restoreState()


# ── PDFRenderer ───────────────────────────────────────────────────────────────

class PDFRenderer:
    LARGE_TABLE_THRESHOLD = 50

    def render(self, report_data: ReportData, output_path: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        brand = report_data.config.brand_name
        batch = report_data.config.batch_number

        doc = BaseDocTemplate(
            output_path, pagesize=A4,
            leftMargin=MARGIN, rightMargin=MARGIN,
            topMargin=MARGIN, bottomMargin=22 * mm,
        )
        frame = Frame(MARGIN, 22 * mm, CONTENT_W, PAGE_H - MARGIN - 22 * mm, id="main")
        doc.addPageTemplates([PageTemplate(
            id="main", frames=[frame],
            onPage=lambda c, d: _on_page(c, d, brand, batch),
        )])

        story = self._build(report_data)
        doc.build(story)
        return output_path

    def render_multi_brand(self, brand_reports: dict, consolidated_config: dict, output_path: str) -> str:
        """
        Render consolidated multi-brand report.
        
        Args:
            brand_reports: Dict[brand_name, ReportData] - Individual brand report data
            consolidated_config: Dict with consolidated report configuration
            output_path: Output file path
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Use consolidated title for footer
        title = consolidated_config.get('title', 'Multi-Brand Report')
        batch = consolidated_config.get('batch_number', 'Batch 1')

        doc = BaseDocTemplate(
            output_path, pagesize=A4,
            leftMargin=MARGIN, rightMargin=MARGIN,
            topMargin=MARGIN, bottomMargin=22 * mm,
        )
        frame = Frame(MARGIN, 22 * mm, CONTENT_W, PAGE_H - MARGIN - 22 * mm, id="main")
        doc.addPageTemplates([PageTemplate(
            id="main", frames=[frame],
            onPage=lambda c, d: _on_page(c, d, title, batch),
        )])

        story = self._build_multi_brand(brand_reports, consolidated_config)
        doc.build(story)
        return output_path

    def _section_imgs(self, d: ReportData, key: str) -> list:
        """Resolve dan render gambar untuk section key."""
        images = (d.config.section_images or {}).get(key, [])
        if not images:
            return []
        resolved = []
        for img_id in images:
            for candidate in [
                img_id,
                os.path.join("uploads/images", img_id),
                os.path.join(os.getcwd(), "uploads/images", img_id),
            ]:
                if os.path.isfile(candidate):
                    resolved.append(candidate)
                    break
        return _image_grid(resolved)

    def _build(self, d: ReportData):
        story = []
        story += self._cover(d)
        story += [PageBreak()]
        story += self._performance_summary(d)
        story += [PageBreak()]
        story += self._gmv_highlight(d)
        story += [PageBreak()]
        story += self._top_performers(d)
        story += [PageBreak()]
        story += self._collaboration(d)
        story += [PageBreak()]
        story += self._engagement(d)

        large = len(d.deal_rows) > self.LARGE_TABLE_THRESHOLD
        if not large:
            story += [PageBreak()]
            story += self._detailed_data(d)

        story += [PageBreak()]
        story += self._insight_nextplan(d)

        if large:
            story += [PageBreak()]
            story += self._detailed_data(d, lampiran=True)

        return story

    def _build_multi_brand(self, brand_reports: dict, consolidated_config: dict):
        """Build consolidated multi-brand report."""
        story = []
        
        # Multi-brand cover page
        story += self._multi_brand_cover(brand_reports, consolidated_config)
        story += [PageBreak()]
        
        # Executive summary with brand comparison
        story += self._multi_brand_executive_summary(brand_reports, consolidated_config)
        story += [PageBreak()]
        
        # Brand comparison section
        story += self._brand_comparison_section(brand_reports, consolidated_config)
        story += [PageBreak()]
        
        # Individual brand sections
        for brand_name, report_data in brand_reports.items():
            story += self._brand_section_header(brand_name, report_data)
            story += [PageBreak()]
            
            # Brand-specific performance summary
            story += self._brand_performance_summary(brand_name, report_data)
            story += [PageBreak()]
            
            # Brand-specific GMV highlight
            story += self._brand_gmv_highlight(brand_name, report_data)
            story += [PageBreak()]
            
            # Brand-specific top performers
            story += self._brand_top_performers(brand_name, report_data)
            story += [PageBreak()]
        
        # Consolidated insights and next plans
        story += self._multi_brand_insights(brand_reports, consolidated_config)
        
        return story

    # ── Cover ─────────────────────────────────────────────────────────────────

    def _cover(self, d: ReportData):
        cfg = d.config
        try:
            ps = cfg.period_start.strftime("%d %B %Y")
            pe = cfg.period_end.strftime("%d %B %Y")
        except Exception:
            ps, pe = str(cfg.period_start), str(cfg.period_end)

        # Modern cover dengan accent color
        cover_rows = [
            [Paragraph("LAPORAN AFFILIATE TIKTOK", STYLES["cover_sub"])],
            [Spacer(1, 12 * mm)],
            [Paragraph(cfg.brand_name, STYLES["cover_brand"])],
            [Spacer(1, 6 * mm)],
            [HRFlowable(width=80 * mm, thickness=3, color=C_ACCENT)],
            [Spacer(1, 6 * mm)],
            [Paragraph(f"Batch {cfg.batch_number}", STYLES["cover_sub"])],
            [Spacer(1, 10 * mm)],
            [Paragraph(f"Periode: {ps} — {pe}", STYLES["cover_period"])],
            [Spacer(1, 18 * mm)],
            [Paragraph("Dokumen ini bersifat rahasia dan hanya untuk keperluan internal.", STYLES["cover_meta"])],
        ]

        tbl = Table(cover_rows, colWidths=[CONTENT_W])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), C_PRIMARY),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            ("LEFTPADDING",  (0, 0), (-1, -1), 20),
            ("RIGHTPADDING", (0, 0), (-1, -1), 20),
            ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",   (0, 0), (0, 0),   int((PAGE_H - 2 * MARGIN) * 0.25)),
        ]))
        return [tbl]

    # ── Performance Summary ───────────────────────────────────────────────────

    def _performance_summary(self, d: ReportData):
        m = d.metrics
        cfg = d.config
        items = _section_title("Performance Summary")

        # Baris 1: 4 kolom - metrics dasar
        items.append(_metric_cards([
            ("Total Deal", str(m.total_deal)),
            ("Total Posting", str(m.total_posting)),
            ("Belum Posting", str(m.total_belum_posting)),
            ("Total VT", format_number(m.total_video)),
        ]))
        items.append(Spacer(1, 4 * mm))

        # Baris 2: 1 kolom - GMV (lebih besar dan menonjol)
        items.append(_metric_cards([
            ("Total GMV", format_rupiah(m.total_gmv))
        ]))
        items.append(Spacer(1, 4 * mm))

        # Baris 3: 3 kolom - metrics tambahan (hanya jika ada data)
        row3 = []
        if m.total_create_sale:
            row3.append(("Create Sale", str(m.total_create_sale)))
        if m.total_pesanan:
            row3.append(("Total Pesanan", format_number(m.total_pesanan)))
        if m.total_produk_terjual:
            row3.append(("Produk Terjual", format_number(m.total_produk_terjual)))
        
        if row3:
            items.append(_metric_cards(row3))
            items.append(Spacer(1, 6 * mm))
        else:
            items.append(Spacer(1, 2 * mm))

        # Summary table
        headers = ["Metrik", "Nilai"]
        rows = [
            ["Total Akun Deal", f"{m.total_deal} akun"],
            ["Total Akun Posting (Up VT)", f"{m.total_posting} akun"],
            ["Total Akun Belum Posting", f"{m.total_belum_posting} akun"],
            ["Total Video (VT)", format_number(m.total_video)],
            ["Total GMV", format_rupiah(m.total_gmv)],
        ]
        if m.total_create_sale:
            rows.append(["Total Affiliate Create Sale", f"{m.total_create_sale} akun"])
        if m.total_produk_terjual:
            rows.append(["Total Produk Terjual", format_number(m.total_produk_terjual)])
        if m.total_pesanan:
            rows.append(["Total Pesanan (Settled)", format_number(m.total_pesanan)])
        if cfg.prev_gmv:
            rows.append([f"GMV Batch Sebelumnya", format_rupiah(cfg.prev_gmv)])
        if m.gmv_change is not None:
            sign = "▲" if m.gmv_change >= 0 else "▼"
            rows.append(["Perubahan GMV", f"{sign} {format_rupiah(abs(m.gmv_change))} ({m.gmv_change_pct:+.1f}%)"])

        items.append(_make_table(headers, rows, [CONTENT_W * 0.55, CONTENT_W * 0.45]))
        
        # Add section images if available
        perf_imgs = self._section_imgs(d, "affiliate_performance_summary")
        if perf_imgs:
            items.append(Spacer(1, 4 * mm))
            items += perf_imgs
        
        return items

    # ── GMV Highlight ─────────────────────────────────────────────────────────

    def _gmv_highlight(self, d: ReportData):
        m = d.metrics
        cfg = d.config
        items = _section_title("GMV Highlight")

        # Big GMV box dengan gradient effect (simulasi dengan 2 warna)
        gmv_rows = [
            [Paragraph(f"Total GMV Batch {cfg.batch_number}", STYLES["gmv_lbl"])],
            [Paragraph(format_rupiah(m.total_gmv), STYLES["gmv_big"])],
        ]
        if m.gmv_change is not None:
            sign = "▲" if m.gmv_change >= 0 else "▼"
            color = C_POSITIVE if m.gmv_change >= 0 else C_NEGATIVE
            direction = "naik" if m.gmv_change >= 0 else "turun"
            change_style = ParagraphStyle("chg", fontName="Helvetica-Bold", fontSize=12,
                                          textColor=C_LIGHT, alignment=TA_CENTER)
            gmv_rows.append([Paragraph(
                f"{sign} {format_rupiah(abs(m.gmv_change))} ({abs(m.gmv_change_pct):.1f}% {direction} vs batch sebelumnya)",
                change_style
            )])

        gmv_tbl = Table([[r[0]] for r in gmv_rows], colWidths=[CONTENT_W])
        gmv_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), C_ACCENT2),
            ("TOPPADDING",   (0, 0), (-1, -1), 15),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 15),
            ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
            ("BOX",          (0, 0), (-1, -1), 2, C_PRIMARY),
        ]))
        items.append(gmv_tbl)

        # SKU list dengan styling lebih menarik
        if d.brand_profile and d.brand_profile.sku_list:
            items.append(Spacer(1, 6 * mm))
            sku_text = "  •  ".join(d.brand_profile.sku_list)
            sku_tbl = Table([
                [Paragraph("PRODUK / SKU", STYLES["metric_lbl"])],
                [Paragraph(sku_text, STYLES["body_bold"])],
            ], colWidths=[CONTENT_W])
            sku_tbl.setStyle(TableStyle([
                ("BACKGROUND",   (0, 0), (0, 0), C_ACCENT),
                ("BACKGROUND",   (0, 1), (0, 1), C_WHITE),
                ("BOX",          (0, 0), (-1, -1), 1.5, C_ACCENT),
                ("TOPPADDING",   (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
                ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
            ]))
            items.append(sku_tbl)

        # FIX: Add section images if available
        gmv_imgs = self._section_imgs(d, "gmv_batch")
        if gmv_imgs:
            items += gmv_imgs
            
        return items

    # ── Top Performers ────────────────────────────────────────────────────────

    def _top_performers(self, d: ReportData):
        items = _section_title("Top 10 Performer")
        if not d.top_performers:
            items.append(Paragraph("Tidak ada data top performer.", STYLES["placeholder"]))
            return items

        headers = ["#", "Username", "GMV"]
        rows = [
            [str(i + 1), r.username or "—", format_rupiah(r.avg_gmv_month or 0)]
            for i, r in enumerate(d.top_performers)
        ]
        col_w = [12 * mm, CONTENT_W - 12 * mm - 55 * mm, 55 * mm]
        items.append(_make_table(headers, rows, col_w))
        
        # FIX: Add section images if available
        top_imgs = self._section_imgs(d, "gmv_affiliate")
        if top_imgs:
            items += top_imgs
            
        return items

    # ── Collaboration Metrics ─────────────────────────────────────────────────

    def _collaboration(self, d: ReportData):
        m = d.metrics
        items = _section_title("Collaboration Metrics")

        rasio = f"{m.total_deal / m.total_approached * 100:.1f}%" if m.total_approached > 0 else "0%"
        items.append(_metric_cards([
            ("Total Approached", format_number(m.total_approached)),
            ("Total Deal", format_number(m.total_deal)),
            ("Rasio Konversi", rasio),
        ]))
        # Add section images if available
        collab_imgs = self._section_imgs(d, "collaboration_metrics")
        if collab_imgs:
            items.append(Spacer(1, 4 * mm))
            items += collab_imgs
        return items

    # ── Detailed Data ─────────────────────────────────────────────────────────

    def _detailed_data(self, d: ReportData, lampiran=False):
        title = "Detailed GMV Data" + (" (Lampiran)" if lampiran else "")
        items = _section_title(title)

        if not d.deal_rows:
            items.append(Paragraph("Tidak ada data creator.", STYLES["placeholder"]))
            return items

        headers = ["#", "Username", "GMV"]
        rows = [
            [str(i + 1), r.username or "—", format_rupiah(r.avg_gmv_month or 0)]
            for i, r in enumerate(d.deal_rows)
        ]
        col_w = [12 * mm, CONTENT_W - 12 * mm - 55 * mm, 55 * mm]
        # Use fixed row height of 8mm for consistent appearance
        items.append(_make_table(headers, rows, col_w, row_height=8*mm))
        # FIX: Don't add section images here - they're not relevant for detailed GMV data
        return items

    # ── Engagement ────────────────────────────────────────────────────────────

    def _engagement(self, d: ReportData):
        items = _section_title("Engagement")
        eng = d.config.engagement
        if eng:
            items.append(_metric_cards([
                ("Total Views",    f"{eng.total_views:,}".replace(",", ".")),
                ("Total Likes",    f"{eng.total_likes:,}".replace(",", ".")),
                ("Total Comments", f"{eng.total_comments:,}".replace(",", ".")),
            ]))

            # Top 5 creator engagement — tabel dengan breakdown per video
            if eng.top_creators:
                items.append(Spacer(1, 6 * mm))
                items.append(Paragraph("Top 5 Creator Engagement", STYLES["body_bold"]))
                items.append(Spacer(1, 2 * mm))
                
                # ALWAYS use 8-column format for consistent layout
                headers = ["#", "Username", "Views (vid1)", "Likes (vid1)", "Comments (vid1)", 
                          "Views (vid2)", "Likes (vid2)", "Comments (vid2)"]
                table_rows = []
                
                for i, c in enumerate(eng.top_creators[:5]):
                    if c.videos and len(c.videos) >= 2:
                        # Creator dengan 2+ video
                        vid1 = c.videos[0]
                        vid2 = c.videos[1]
                        table_rows.append([
                            str(i + 1),
                            f"@{c.username}",
                            f"{vid1.views:,}".replace(",", "."),
                            f"{vid1.likes:,}".replace(",", "."),
                            f"{vid1.comments:,}".replace(",", "."),
                            f"{vid2.views:,}".replace(",", "."),
                            f"{vid2.likes:,}".replace(",", "."),
                            f"{vid2.comments:,}".replace(",", "."),
                        ])
                    elif c.videos and len(c.videos) == 1:
                        # Creator dengan 1 video - kolom vid2 kosong
                        vid1 = c.videos[0]
                        table_rows.append([
                            str(i + 1),
                            f"@{c.username}",
                            f"{vid1.views:,}".replace(",", "."),
                            f"{vid1.likes:,}".replace(",", "."),
                            f"{vid1.comments:,}".replace(",", "."),
                            "—", "—", "—",
                        ])
                    else:
                        # Creator tanpa breakdown video - gunakan total
                        table_rows.append([
                            str(i + 1),
                            f"@{c.username}",
                            f"{c.total_views:,}".replace(",", "."),
                            f"{c.total_likes:,}".replace(",", "."),
                            f"{c.total_comments:,}".replace(",", "."),
                            "—", "—", "—",
                        ])
                
                col_w = [8 * mm, 30 * mm, 20 * mm, 18 * mm, 18 * mm, 20 * mm, 18 * mm, 18 * mm]
                items.append(_make_table(headers, table_rows, col_w))
        else:
            items.append(Paragraph("Data tidak tersedia.", STYLES["placeholder"]))
        
        # Add section images if available
        eng_imgs = self._section_imgs(d, "total_engagement")
        if eng_imgs:
            items.append(Spacer(1, 4 * mm))
            items += eng_imgs
        return items

    # ── Insight & Next Plan ───────────────────────────────────────────────────

    def _insight_nextplan(self, d: ReportData):
        items = _section_title("Insight")
        if d.config.insight:
            items.append(_text_block(d.config.insight))
        else:
            items.append(Paragraph("Belum diisi.", STYLES["placeholder"]))

        items.append(Spacer(1, 8 * mm))
        items += _section_title("Next Plan")
        if d.config.next_plan:
            items.append(_text_block(d.config.next_plan))
        else:
            items.append(Paragraph("Belum diisi.", STYLES["placeholder"]))

        return items

    # ── Multi-Brand Report Methods ────────────────────────────────────────────

    def _multi_brand_cover(self, brand_reports: dict, consolidated_config: dict):
        """Multi-brand cover page."""
        try:
            ps = consolidated_config.get('period_start', '').strftime("%d %B %Y") if consolidated_config.get('period_start') else ''
            pe = consolidated_config.get('period_end', '').strftime("%d %B %Y") if consolidated_config.get('period_end') else ''
        except Exception:
            ps = str(consolidated_config.get('period_start', ''))
            pe = str(consolidated_config.get('period_end', ''))

        batch = consolidated_config.get('batch_number', 'Batch 1')
        brand_names = list(brand_reports.keys())
        brand_list = " • ".join(brand_names[:3])  # Show first 3 brands
        if len(brand_names) > 3:
            brand_list += f" • +{len(brand_names) - 3} more"

        cover_rows = [
            [Paragraph("LAPORAN AFFILIATE TIKTOK", STYLES["cover_sub"])],
            [Spacer(1, 8 * mm)],
            [Paragraph("MULTI-BRAND REPORT", STYLES["cover_brand"])],
            [Spacer(1, 6 * mm)],
            [HRFlowable(width=80 * mm, thickness=3, color=C_ACCENT)],
            [Spacer(1, 4 * mm)],
            [Paragraph(brand_list, STYLES["cover_sub"])],
            [Spacer(1, 6 * mm)],
            [Paragraph(f"Batch {batch}", STYLES["cover_sub"])],
            [Spacer(1, 8 * mm)],
            [Paragraph(f"Periode: {ps} — {pe}", STYLES["cover_period"])],
            [Spacer(1, 4 * mm)],
            [Paragraph(f"{len(brand_names)} brands • {sum(len(rd.deal_rows) for rd in brand_reports.values())} creators", STYLES["cover_period"])],
            [Spacer(1, 12 * mm)],
            [Paragraph("Dokumen ini bersifat rahasia dan hanya untuk keperluan internal.", STYLES["cover_meta"])],
        ]

        tbl = Table(cover_rows, colWidths=[CONTENT_W])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), C_PRIMARY),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            ("LEFTPADDING",  (0, 0), (-1, -1), 20),
            ("RIGHTPADDING", (0, 0), (-1, -1), 20),
            ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",   (0, 0), (0, 0),   int((PAGE_H - 2 * MARGIN) * 0.2)),
        ]))
        return [tbl]

    def _multi_brand_executive_summary(self, brand_reports: dict, consolidated_config: dict):
        """Executive summary with aggregated metrics."""
        items = _section_title("Executive Summary")

        # Aggregate metrics across all brands
        total_deal = sum(rd.metrics.total_deal for rd in brand_reports.values())
        total_posting = sum(rd.metrics.total_posting for rd in brand_reports.values())
        total_belum_posting = sum(rd.metrics.total_belum_posting for rd in brand_reports.values())
        total_video = sum(rd.metrics.total_video for rd in brand_reports.values())
        total_gmv = sum(rd.metrics.total_gmv for rd in brand_reports.values())
        total_approached = sum(rd.metrics.total_approached for rd in brand_reports.values())

        # Metrics cards
        items.append(_metric_cards([
            ("Total Brands", str(len(brand_reports))),
            ("Total Deal", str(total_deal)),
            ("Total Posting", str(total_posting)),
            ("Total VT", format_number(total_video)),
        ]))
        items.append(Spacer(1, 4 * mm))

        items.append(_metric_cards([
            ("Total GMV", format_rupiah(total_gmv))
        ]))
        items.append(Spacer(1, 6 * mm))

        # Summary table
        headers = ["Metrik", "Total"]
        rows = [
            ["Jumlah Brand", f"{len(brand_reports)} brands"],
            ["Total Akun Deal", f"{total_deal} akun"],
            ["Total Akun Posting", f"{total_posting} akun"],
            ["Total Video (VT)", format_number(total_video)],
            ["Total GMV", format_rupiah(total_gmv)],
        ]
        if total_approached > 0:
            conversion_rate = (total_deal / total_approached * 100) if total_approached > 0 else 0
            rows.append(["Rasio Konversi", f"{conversion_rate:.1f}%"])

        items.append(_make_table(headers, rows, [CONTENT_W * 0.6, CONTENT_W * 0.4]))
        return items

    def _brand_comparison_section(self, brand_reports: dict, consolidated_config: dict):
        """Brand comparison table."""
        items = _section_title("Brand Comparison")

        if len(brand_reports) <= 1:
            items.append(Paragraph("Perbandingan memerlukan minimal 2 brand.", STYLES["placeholder"]))
            return items

        # Comparison table
        headers = ["Brand", "Deal", "Posting", "GMV", "Avg GMV/Creator"]
        rows = []
        
        for brand_name, report_data in brand_reports.items():
            m = report_data.metrics
            avg_gmv = (m.total_gmv / m.total_deal) if m.total_deal > 0 else 0
            rows.append([
                brand_name,
                str(m.total_deal),
                str(m.total_posting),
                format_rupiah(m.total_gmv),
                format_rupiah(avg_gmv)
            ])

        # Sort by GMV descending
        rows.sort(key=lambda x: float(x[3].replace('Rp', '').replace('.', '').replace(',', '')) if 'Rp' in x[3] else 0, reverse=True)

        col_widths = [CONTENT_W * 0.25, CONTENT_W * 0.15, CONTENT_W * 0.15, CONTENT_W * 0.25, CONTENT_W * 0.2]
        items.append(_make_table(headers, rows, col_widths))

        return items

    def _brand_section_header(self, brand_name: str, report_data: ReportData):
        """Brand section header."""
        header_rows = [
            [Paragraph(f"BRAND: {brand_name}", STYLES["cover_sub"])],
            [Spacer(1, 4 * mm)],
            [HRFlowable(width=60 * mm, thickness=2, color=C_ACCENT2)],
        ]

        tbl = Table(header_rows, colWidths=[CONTENT_W])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), C_LIGHT),
            ("TOPPADDING",   (0, 0), (-1, -1), 15),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 15),
            ("LEFTPADDING",  (0, 0), (-1, -1), 20),
            ("RIGHTPADDING", (0, 0), (-1, -1), 20),
            ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("BOX",          (0, 0), (-1, -1), 1, C_BORDER),
        ]))
        return [tbl]

    def _brand_performance_summary(self, brand_name: str, report_data: ReportData):
        """Brand-specific performance summary."""
        items = _section_title(f"Performance Summary - {brand_name}")
        
        # Add brand identification
        brand_info = Table([
            [Paragraph(f"Brand: {brand_name}", STYLES["body_bold"])],
            [Paragraph(f"Creators: {len(report_data.deal_rows)} deal, {len(report_data.non_deal_rows)} non-deal", STYLES["small"])],
        ], colWidths=[CONTENT_W])
        brand_info.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), C_LIGHT),
            ("TOPPADDING",   (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
            ("LEFTPADDING",  (0, 0), (-1, -1), 15),
            ("RIGHTPADDING", (0, 0), (-1, -1), 15),
            ("BOX",          (0, 0), (-1, -1), 1, C_BORDER),
        ]))
        items.append(brand_info)
        items.append(Spacer(1, 4 * mm))
        
        # Regular performance summary
        items += self._performance_summary(report_data)[1:]  # Skip the title
        return items

    def _brand_gmv_highlight(self, brand_name: str, report_data: ReportData):
        """Brand-specific GMV highlight."""
        items = _section_title(f"GMV Highlight - {brand_name}")
        items += self._gmv_highlight(report_data)[1:]  # Skip the title
        return items

    def _brand_top_performers(self, brand_name: str, report_data: ReportData):
        """Brand-specific top performers."""
        items = _section_title(f"Top Performers - {brand_name}")
        items += self._top_performers(report_data)[1:]  # Skip the title
        return items

    def _multi_brand_insights(self, brand_reports: dict, consolidated_config: dict):
        """Consolidated insights and next plans."""
        items = _section_title("Multi-Brand Insights")
        
        # Generate automatic insights based on brand comparison
        insights = []
        
        # Find best performing brand by GMV
        best_brand = max(brand_reports.items(), key=lambda x: x[1].metrics.total_gmv)
        insights.append(f"Brand dengan performa terbaik: {best_brand[0]} dengan total GMV {format_rupiah(best_brand[1].metrics.total_gmv)}")
        
        # Find brand with highest conversion rate
        conversion_rates = {}
        for brand_name, report_data in brand_reports.items():
            if report_data.metrics.total_approached > 0:
                conversion_rates[brand_name] = report_data.metrics.total_deal / report_data.metrics.total_approached
        
        if conversion_rates:
            best_conversion_brand = max(conversion_rates.items(), key=lambda x: x[1])
            insights.append(f"Brand dengan konversi terbaik: {best_conversion_brand[0]} ({best_conversion_brand[1]*100:.1f}%)")
        
        # Total summary
        total_gmv = sum(rd.metrics.total_gmv for rd in brand_reports.values())
        total_creators = sum(len(rd.deal_rows) for rd in brand_reports.values())
        insights.append(f"Total {len(brand_reports)} brand dengan {total_creators} creators menghasilkan GMV {format_rupiah(total_gmv)}")
        
        insight_text = "\n\n".join(insights)
        items.append(_text_block(insight_text))
        
        items.append(Spacer(1, 8 * mm))
        items += _section_title("Next Plan")
        
        next_plan = consolidated_config.get('next_plan', 'Fokus pada optimasi brand dengan performa terbaik dan perbaikan strategi untuk brand dengan konversi rendah.')
        items.append(_text_block(next_plan))
        
        return items
