"""
Database Migration: Add Multi-Brand Features

This migration adds the necessary database tables and indexes for
multi-brand detection and processing functionality.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def get_database_path():
    """Get the path to the SQLite database."""
    # Try to find the database in common locations
    possible_paths = [
        'instance/tiktok_affiliate.db',
        'tiktok_affiliate.db',
        '../instance/tiktok_affiliate.db'
    ]
    
    for path in possible_paths:
        if Path(path).exists():
            return path
    
    # Default to instance directory
    instance_dir = Path('instance')
    instance_dir.mkdir(exist_ok=True)
    return 'instance/tiktok_affiliate.db'


def create_brand_aliases_table(cursor):
    """Create the brand_aliases table for storing brand alias mappings."""
    
    # Check if table already exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='brand_aliases'
    """)
    
    if cursor.fetchone():
        logger.info("brand_aliases table already exists, skipping creation")
        return
    
    # Create brand_aliases table
    cursor.execute("""
        CREATE TABLE brand_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name VARCHAR(255) NOT NULL,
            alias_name VARCHAR(255) NOT NULL,
            similarity_score FLOAT DEFAULT 1.0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(canonical_name, alias_name)
        )
    """)
    
    logger.info("Created brand_aliases table")


def create_indexes(cursor):
    """Create indexes for efficient brand alias lookups."""
    
    indexes = [
        ("idx_brand_aliases_canonical", "brand_aliases", "canonical_name"),
        ("idx_brand_aliases_alias", "brand_aliases", "alias_name"),
        ("idx_brand_aliases_similarity", "brand_aliases", "similarity_score"),
        ("idx_brand_aliases_created", "brand_aliases", "created_at")
    ]
    
    for index_name, table_name, column_name in indexes:
        try:
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS {index_name} 
                ON {table_name}({column_name})
            """)
            logger.info(f"Created index {index_name}")
        except sqlite3.Error as e:
            logger.warning(f"Failed to create index {index_name}: {e}")


def add_multi_brand_columns_to_reports(cursor):
    """Add multi-brand support columns to existing report tables if they exist."""
    
    # Check if report_records table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='report_records'
    """)
    
    if not cursor.fetchone():
        logger.info("report_records table does not exist, skipping column additions")
        return
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(report_records)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    
    # Add multi-brand support columns if they don't exist
    new_columns = [
        ("is_multi_brand", "BOOLEAN DEFAULT FALSE"),
        ("brand_count", "INTEGER DEFAULT 1"),
        ("selected_brands", "TEXT"),  # JSON array of selected brand names
        ("report_mode", "VARCHAR(50) DEFAULT 'single'"),  # 'single', 'separate', 'consolidated'
    ]
    
    for column_name, column_def in new_columns:
        if column_name not in existing_columns:
            try:
                cursor.execute(f"""
                    ALTER TABLE report_records 
                    ADD COLUMN {column_name} {column_def}
                """)
                logger.info(f"Added column {column_name} to report_records")
            except sqlite3.Error as e:
                logger.warning(f"Failed to add column {column_name}: {e}")


def create_multi_brand_report_metadata_table(cursor):
    """Create table for storing multi-brand report metadata."""
    
    # Check if table already exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='multi_brand_report_metadata'
    """)
    
    if cursor.fetchone():
        logger.info("multi_brand_report_metadata table already exists, skipping creation")
        return
    
    # Create multi_brand_report_metadata table
    cursor.execute("""
        CREATE TABLE multi_brand_report_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER,
            brand_name VARCHAR(255) NOT NULL,
            creator_count INTEGER DEFAULT 0,
            total_gmv FLOAT DEFAULT 0.0,
            avg_gmv FLOAT DEFAULT 0.0,
            report_file_path VARCHAR(500),
            generation_status VARCHAR(50) DEFAULT 'pending',
            error_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (report_id) REFERENCES report_records (id) ON DELETE CASCADE
        )
    """)
    
    # Create indexes for the metadata table
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_multi_brand_metadata_report_id 
        ON multi_brand_report_metadata(report_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_multi_brand_metadata_brand_name 
        ON multi_brand_report_metadata(brand_name)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_multi_brand_metadata_status 
        ON multi_brand_report_metadata(generation_status)
    """)
    
    logger.info("Created multi_brand_report_metadata table with indexes")


def insert_sample_brand_aliases(cursor):
    """Insert some sample brand aliases for common variations."""
    
    sample_aliases = [
        ("FLORIST", "Florist", 1.0),
        ("FLORIST", "florist", 1.0),
        ("FLORIST", "FL", 0.8),
        ("BRAND_X", "Brand X", 1.0),
        ("BRAND_X", "BrandX", 1.0),
        ("COMPANY_A", "Company A", 1.0),
        ("COMPANY_A", "CompanyA", 1.0),
        ("COMPANY_A", "Co A", 0.9),
    ]
    
    for canonical, alias, similarity in sample_aliases:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO brand_aliases 
                (canonical_name, alias_name, similarity_score) 
                VALUES (?, ?, ?)
            """, (canonical, alias, similarity))
        except sqlite3.Error as e:
            logger.warning(f"Failed to insert sample alias {canonical} -> {alias}: {e}")
    
    logger.info(f"Inserted {len(sample_aliases)} sample brand aliases")


def create_migration_log_table(cursor):
    """Create table to track migration history."""
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS migration_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_name VARCHAR(255) NOT NULL UNIQUE,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN DEFAULT TRUE,
            error_message TEXT
        )
    """)
    
    logger.info("Created migration_log table")


def log_migration(cursor, migration_name, success=True, error_message=None):
    """Log migration execution."""
    
    cursor.execute("""
        INSERT OR REPLACE INTO migration_log 
        (migration_name, applied_at, success, error_message) 
        VALUES (?, ?, ?, ?)
    """, (migration_name, datetime.now(), success, error_message))


def run_migration():
    """Run the complete multi-brand migration."""
    
    db_path = get_database_path()
    logger.info(f"Running multi-brand migration on database: {db_path}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Create migration log table first
        create_migration_log_table(cursor)
        
        # Check if migration already applied
        cursor.execute("""
            SELECT success FROM migration_log 
            WHERE migration_name = 'add_multi_brand_features'
        """)
        
        result = cursor.fetchone()
        if result and result[0]:
            logger.info("Multi-brand migration already applied successfully")
            conn.close()
            return True
        
        # Run migration steps
        logger.info("Starting multi-brand database migration...")
        
        # Step 1: Create brand aliases table
        create_brand_aliases_table(cursor)
        
        # Step 2: Create indexes
        create_indexes(cursor)
        
        # Step 3: Add multi-brand columns to existing tables
        add_multi_brand_columns_to_reports(cursor)
        
        # Step 4: Create multi-brand report metadata table
        create_multi_brand_report_metadata_table(cursor)
        
        # Step 5: Insert sample data
        insert_sample_brand_aliases(cursor)
        
        # Commit all changes
        conn.commit()
        
        # Log successful migration
        log_migration(cursor, 'add_multi_brand_features', success=True)
        conn.commit()
        
        logger.info("Multi-brand migration completed successfully")
        
        # Verify tables were created
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('brand_aliases', 'multi_brand_report_metadata')
        """)
        
        created_tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"Verified created tables: {created_tables}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Multi-brand migration failed: {e}")
        
        try:
            # Log failed migration
            log_migration(cursor, 'add_multi_brand_features', success=False, error_message=str(e))
            conn.commit()
            conn.close()
        except:
            pass
        
        return False


def rollback_migration():
    """Rollback the multi-brand migration (for development/testing)."""
    
    db_path = get_database_path()
    logger.info(f"Rolling back multi-brand migration on database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Drop tables created by this migration
        tables_to_drop = [
            'multi_brand_report_metadata',
            'brand_aliases'
        ]
        
        for table in tables_to_drop:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"Dropped table {table}")
            except sqlite3.Error as e:
                logger.warning(f"Failed to drop table {table}: {e}")
        
        # Remove columns from existing tables (SQLite doesn't support DROP COLUMN easily)
        # This would require recreating tables, so we'll skip for now
        logger.warning("Column removal not implemented - manual cleanup may be required")
        
        # Remove migration log entry
        cursor.execute("""
            DELETE FROM migration_log 
            WHERE migration_name = 'add_multi_brand_features'
        """)
        
        conn.commit()
        conn.close()
        
        logger.info("Multi-brand migration rollback completed")
        return True
        
    except Exception as e:
        logger.error(f"Migration rollback failed: {e}")
        return False


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Run migration
    success = run_migration()
    
    if success:
        print("✅ Multi-brand migration completed successfully")
    else:
        print("❌ Multi-brand migration failed")
        exit(1)