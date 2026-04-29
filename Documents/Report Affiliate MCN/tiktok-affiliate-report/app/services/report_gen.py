"""
ReportGenerator — orkestrasi kalkulasi metrik dan perakitan data laporan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from app.services.data_parser import CreatorRow
from app.services.brand_profile import BrandProfileData


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when report configuration fails validation."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class VideoEngagementItem:
    """Data engagement satu video."""
    url: str
    views: int = 0
    likes: int = 0
    comments: int = 0


@dataclass
class CreatorEngagementItem:
    """Data engagement satu creator — untuk ditampilkan di laporan."""
    username: str
    total_views: int = 0
    total_likes: int = 0
    total_comments: int = 0
    videos: list = field(default_factory=list)  # list[VideoEngagementItem]


@dataclass
class EngagementData:
    total_views: int
    total_likes: int
    total_comments: int
    # Top 5 creator berdasarkan views (opsional)
    top_creators: list = field(default_factory=list)  # list[CreatorEngagementItem]


@dataclass
class ReportConfig:
    brand_name: str
    batch_number: str
    period_start: date
    period_end: date
    prev_gmv: Optional[float] = None
    engagement: Optional[EngagementData] = None
    insight: Optional[str] = None
    next_plan: Optional[str] = None
    total_pesanan: Optional[int] = None
    total_produk_terjual: Optional[int] = None
    total_create_sale: Optional[int] = None
    overall_conclusion: Optional[str] = None
    next_planning: Optional[str] = None
    # Screenshot per section: {section_key: [image_path, ...]}
    section_images: dict = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    total_approached: int
    total_deal: int
    total_posting: int          # akun yang sudah upload VT
    total_belum_posting: int    # akun belum upload VT
    total_video: int            # total jumlah VT
    total_pesanan: int          # dari form manual
    total_produk_terjual: int   # dari form manual
    total_create_sale: int      # akun yang create sale
    total_gmv: float
    hero_sku: Optional[str]
    gmv_change: Optional[float]
    gmv_change_pct: Optional[float]


@dataclass
class ReportData:
    config: ReportConfig
    metrics: PerformanceMetrics
    top_performers: list   # list[CreatorRow]
    deal_rows: list        # list[CreatorRow]
    non_deal_rows: list    # list[CreatorRow]
    brand_profile: object  # BrandProfileData


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def format_rupiah(value: float) -> str:
    """Format float ke string Rupiah. Contoh: 1500000 → "Rp1.500.000" """
    int_value = int(value)
    formatted = f"{int_value:,}".replace(",", ".")
    return f"Rp{formatted}"


def format_number(value: int) -> str:
    """Format int dengan pemisah ribuan. Contoh: 52700 → "52.700" """
    return f"{value:,}".replace(",", ".")


# ---------------------------------------------------------------------------
# ReportGenerator
# ---------------------------------------------------------------------------

_POSTING_KEYWORDS = {"posting", "video", "done", "up vt", "upload"}
_SALE_KEYWORDS = {"sale", "create sale", "sold", "terjual"}


class ReportGenerator:

    def validate_config(self, config: ReportConfig) -> None:
        if config.period_end < config.period_start:
            raise ValidationError(
                f"Tanggal akhir periode ({config.period_end}) tidak boleh "
                f"lebih awal dari tanggal mulai periode ({config.period_start})."
            )

    def calculate_metrics(
        self,
        deal_rows: list[CreatorRow],
        non_deal_rows: list[CreatorRow],
        config: Optional[ReportConfig] = None,
    ) -> PerformanceMetrics:
        total_approached = len(deal_rows) + len(non_deal_rows)
        total_deal = len(deal_rows)

        total_posting = 0
        total_video = 0
        total_create_sale = 0

        for row in deal_rows:
            result_str = (row.result or "").lower()
            update_str = (row.update or "").lower()
            combined = result_str + " " + update_str

            # Cek apakah sudah posting
            has_keyword = any(kw in combined for kw in _POSTING_KEYWORDS)
            has_gmv = row.avg_gmv_month is not None and row.avg_gmv_month > 0
            if has_keyword or has_gmv:
                total_posting += 1

            # Hitung total VT dari field total_vt atau custom_fields
            vt_num = 0
            if row.total_vt is not None:
                vt_num = row.total_vt
            else:
                # Fallback ke custom_fields (data lama sebelum field total_vt ditambahkan)
                cf = row.custom_fields or {}
                vt_raw = cf.get('TOTAL VT') or cf.get('TOTAL\nVT') or cf.get('Total VT') or ''
                try:
                    vt_num = int(float(str(vt_raw).strip().replace(',', '')))
                except (ValueError, TypeError):
                    vt_num = 1 if (has_keyword or has_gmv) else 0
            total_video += vt_num

            # Cek create sale
            if has_gmv or any(kw in combined for kw in _SALE_KEYWORDS):
                total_create_sale += 1

        total_belum_posting = total_deal - total_posting

        total_gmv = sum(
            row.avg_gmv_month
            for row in deal_rows
            if row.avg_gmv_month is not None
        )

        # Ambil dari config jika ada (manual input)
        pesanan = (config.total_pesanan or 0) if config else 0
        produk = (config.total_produk_terjual or 0) if config else 0
        create_sale = (config.total_create_sale or total_create_sale) if config else total_create_sale

        return PerformanceMetrics(
            total_approached=total_approached,
            total_deal=total_deal,
            total_posting=total_posting,
            total_belum_posting=total_belum_posting,
            total_video=total_video,
            total_pesanan=pesanan,
            total_produk_terjual=produk,
            total_create_sale=create_sale,
            total_gmv=total_gmv,
            hero_sku=None,
            gmv_change=None,
            gmv_change_pct=None,
        )

    def calculate_gmv_change(
        self,
        current_gmv: float,
        prev_gmv: Optional[float],
    ) -> tuple[Optional[float], Optional[float]]:
        if prev_gmv is None or prev_gmv == 0:
            return (None, None)
        selisih = current_gmv - prev_gmv
        pct = (selisih / prev_gmv) * 100
        return (selisih, pct)

    def get_top_performers(
        self,
        deal_rows: list[CreatorRow],
        limit: int = 10,
    ) -> list[CreatorRow]:
        sorted_rows = sorted(
            deal_rows,
            key=lambda r: r.avg_gmv_month if r.avg_gmv_month is not None else 0,
            reverse=True,
        )
        # Hanya yang punya GMV > 0
        with_gmv = [r for r in sorted_rows if r.avg_gmv_month and r.avg_gmv_month > 0]
        return with_gmv[:limit]

    def assemble_report_data(
        self,
        config: ReportConfig,
        deal_rows: list[CreatorRow],
        non_deal_rows: list[CreatorRow],
        brand_profile: BrandProfileData,
    ) -> ReportData:
        self.validate_config(config)

        metrics = self.calculate_metrics(deal_rows, non_deal_rows, config)

        if config.prev_gmv is not None:
            gmv_change, gmv_change_pct = self.calculate_gmv_change(
                metrics.total_gmv, config.prev_gmv
            )
            metrics.gmv_change = gmv_change
            metrics.gmv_change_pct = gmv_change_pct

        if brand_profile.sku_list:
            metrics.hero_sku = brand_profile.sku_list[0]

        top_performers = self.get_top_performers(deal_rows)

        return ReportData(
            config=config,
            metrics=metrics,
            top_performers=top_performers,
            deal_rows=deal_rows,
            non_deal_rows=non_deal_rows,
            brand_profile=brand_profile,
        )
