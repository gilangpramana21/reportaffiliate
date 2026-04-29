"""
Database migration to add multi-brand support to ReportRecord table.

This migration adds the following columns to support multi-brand reports:
- is_multi_brand: Boolean flag to indicate if this is a multi-brand report
- brand_count: Number of brands in multi-brand report
- brand_list: JSON array of brand names for multi-brand reports
- report_mode: "separate" or "consolidated" for multi-brand reports
- ppt_path: Path to PPT file if generated
"""

import sqlite3
import os
import sys

def run_migration(db_path: str = None):
    """Run the multi-brand support migration."""
    
    if db_path is None:
        # Default database path
        db_path = os.path.join(os.path.dirname(__file__), '..', 'instance', 'tiktok_affiliate.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(report_records)")
        columns = [row[1] for row in cursor.fetchall()]
        
        migrations_needed = []
        
        # Check which columns need to be added
        if 'is_multi_brand' not in columns:
            migrations_needed.append("ALTER TABLE report_records ADD COLUMN is_multi_brand BOOLEAN NOT NULL DEFAULT 0")
        
        if 'brand_count' not in columns:
            migrations_needed.append("ALTER TABLE report_records ADD COLUMN brand_count INTEGER")
        
        if 'brand_list' not in columns:
            migrations_needed.append("ALTER TABLE report_records ADD COLUMN brand_list TEXT")
        
        if 'report_mode' not in columns:
            migrations_needed.append("ALTER TABLE report_records ADD COLUMN report_mode TEXT")
        
        if 'ppt_path' not in columns:
            migrations_needed.append("ALTER TABLE report_records ADD COLUMN ppt_path TEXT")
        
        if not migrations_needed:
            print("Multi-brand support columns already exist. No migration needed.")
            return True
        
        # Execute migrations
        for migration in migrations_needed:
            print(f"Executing: {migration}")
            cursor.execute(migration)
        
        # Commit changes
        conn.commit()
        print(f"Successfully added {len(migrations_needed)} columns for multi-brand support")
        
        return True
        
    except Exception as e:
        print(f"Migration failed: {e}")
        return False
    
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    # Allow running migration directly
    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    success = run_migration(db_path)
    sys.exit(0 if success else 1)