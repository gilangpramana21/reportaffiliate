#!/usr/bin/env python3
"""
Database migration: Add brand_aliases table for multi-brand detection feature.

This migration adds the brand_aliases table to support brand name normalization
and alias management in the multi-brand detection and grouping feature.
"""

import sqlite3
import os
from datetime import datetime


def get_db_path():
    """Get the database path from the application configuration."""
    # Default SQLite database path
    return "instance/tiktok_affiliate.db"


def migrate_up(db_path: str = None):
    """
    Apply the migration - create brand_aliases table.
    
    Args:
        db_path: Path to SQLite database file. If None, uses default path.
    """
    if db_path is None:
        db_path = get_db_path()
    
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        print("Please ensure the database is initialized first.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='brand_aliases'
        """)
        
        if cursor.fetchone():
            print("Table 'brand_aliases' already exists. Migration skipped.")
            conn.close()
            return True
        
        # Create brand_aliases table
        cursor.execute("""
            CREATE TABLE brand_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_name TEXT NOT NULL,
                alias_name TEXT NOT NULL,
                similarity_score REAL NOT NULL DEFAULT 1.0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(canonical_name, alias_name)
            )
        """)
        
        # Create indexes for efficient lookups
        cursor.execute("""
            CREATE INDEX idx_brand_aliases_canonical 
            ON brand_aliases(canonical_name)
        """)
        
        cursor.execute("""
            CREATE INDEX idx_brand_aliases_alias 
            ON brand_aliases(alias_name)
        """)
        
        conn.commit()
        conn.close()
        
        print("✅ Migration completed successfully!")
        print("   - Created 'brand_aliases' table")
        print("   - Created indexes for efficient lookups")
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Migration failed: {e}")
        return False


def migrate_down(db_path: str = None):
    """
    Rollback the migration - drop brand_aliases table.
    
    Args:
        db_path: Path to SQLite database file. If None, uses default path.
    """
    if db_path is None:
        db_path = get_db_path()
    
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='brand_aliases'
        """)
        
        if not cursor.fetchone():
            print("Table 'brand_aliases' does not exist. Rollback skipped.")
            conn.close()
            return True
        
        # Drop the table (indexes will be dropped automatically)
        cursor.execute("DROP TABLE brand_aliases")
        
        conn.commit()
        conn.close()
        
        print("✅ Rollback completed successfully!")
        print("   - Dropped 'brand_aliases' table")
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Rollback failed: {e}")
        return False


def check_migration_status(db_path: str = None):
    """
    Check if the migration has been applied.
    
    Args:
        db_path: Path to SQLite database file. If None, uses default path.
        
    Returns:
        bool: True if migration is applied, False otherwise.
    """
    if db_path is None:
        db_path = get_db_path()
    
    if not os.path.exists(db_path):
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='brand_aliases'
        """)
        
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
        
    except sqlite3.Error:
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python add_brand_aliases_table.py [up|down|status] [db_path]")
        print("Commands:")
        print("  up     - Apply the migration")
        print("  down   - Rollback the migration")
        print("  status - Check migration status")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    db_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    if command == "up":
        success = migrate_up(db_path)
        sys.exit(0 if success else 1)
    elif command == "down":
        success = migrate_down(db_path)
        sys.exit(0 if success else 1)
    elif command == "status":
        applied = check_migration_status(db_path)
        print(f"Migration status: {'Applied' if applied else 'Not applied'}")
        sys.exit(0)
    else:
        print(f"Unknown command: {command}")
        print("Valid commands: up, down, status")
        sys.exit(1)