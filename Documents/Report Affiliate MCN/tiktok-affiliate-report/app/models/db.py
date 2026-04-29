from datetime import datetime
from sqlalchemy import (
    Column, Integer, Text, Date, DateTime, ForeignKey, Boolean, Float, UniqueConstraint, Index
)
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class BrandProfile(db.Model):
    __tablename__ = "brand_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, unique=True, nullable=False)
    sku_list = Column(Text, nullable=False, default="[]")
    sow = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    column_config = db.relationship(
        "ColumnConfig", backref="brand", uselist=False, cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<BrandProfile id={self.id} name={self.name!r}>"


class ColumnConfig(db.Model):
    __tablename__ = "column_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brand_id = Column(Integer, ForeignKey("brand_profiles.id", ondelete="CASCADE"), nullable=False)
    mappings = Column(Text, nullable=False, default="{}")
    custom_cols = Column(Text, nullable=False, default="[]")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ColumnConfig id={self.id} brand_id={self.brand_id}>"


class ReportRecord(db.Model):
    __tablename__ = "report_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brand_name = Column(Text, nullable=False)
    batch_number = Column(Text, nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)
    pdf_path = Column(Text, nullable=False)
    config_snapshot = Column(Text, nullable=False)
    # Batch job reference (nullable — single reports have no batch)
    batch_job_id = Column(Text, nullable=True)
    
    # Multi-brand support fields
    is_multi_brand = Column(Boolean, nullable=False, default=False)
    brand_count = Column(Integer, nullable=True)  # Number of brands in multi-brand report
    brand_list = Column(Text, nullable=True)  # JSON array of brand names for multi-brand reports
    report_mode = Column(Text, nullable=True)  # "separate" or "consolidated" for multi-brand
    ppt_path = Column(Text, nullable=True)  # Path to PPT file if generated

    def __repr__(self):
        return f"<ReportRecord id={self.id} brand={self.brand_name!r} batch={self.batch_number!r} multi_brand={self.is_multi_brand}>"

    @property
    def brands_list(self):
        """Get list of brands for multi-brand reports."""
        if not self.is_multi_brand or not self.brand_list:
            return [self.brand_name]
        try:
            import json
            return json.loads(self.brand_list)
        except:
            return [self.brand_name]

    @property
    def display_name(self):
        """Get display name for the report."""
        if self.is_multi_brand:
            brands = self.brands_list
            if len(brands) <= 3:
                return " + ".join(brands)
            else:
                return f"{' + '.join(brands[:2])} + {len(brands) - 2} more"
        return self.brand_name


class AppSettings(db.Model):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(Text, unique=True, nullable=False)
    value = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AppSettings key={self.key!r}>"


class BrandAlias(db.Model):
    """Brand alias configuration for multi-brand detection and normalization."""
    __tablename__ = "brand_aliases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_name = Column(Text, nullable=False)
    alias_name = Column(Text, nullable=False)
    similarity_score = Column(Float, nullable=False, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('canonical_name', 'alias_name', name='uq_brand_alias'),
        Index('idx_brand_aliases_canonical', 'canonical_name'),
        Index('idx_brand_aliases_alias', 'alias_name'),
    )

    def __repr__(self):
        return f"<BrandAlias id={self.id} canonical={self.canonical_name!r} alias={self.alias_name!r}>"


class WebhookConfig(db.Model):
    """Webhook URL yang dipanggil saat laporan selesai dibuat."""
    __tablename__ = "webhook_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(Text, nullable=False)
    secret = Column(Text, nullable=True)       # optional HMAC secret
    enabled = Column(Boolean, nullable=False, default=True)
    events = Column(Text, nullable=False, default='["report.created"]')  # JSON array
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<WebhookConfig id={self.id} url={self.url!r}>"
