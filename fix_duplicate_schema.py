#!/usr/bin/env python3
"""
Fix database schema: Remove UNIQUE constraint from file_hash to enable duplicate detection.
The UNIQUE constraint prevents storing multiple files with the same hash (i.e., duplicates).
"""
import sqlite3
from pathlib import Path
import shutil

db_path = Path("data/ddas.db")

if not db_path.exists():
    print(f"ERROR: Database not found at {db_path}")
    exit(1)

print("=" * 60)
print("FIXING DATABASE SCHEMA FOR DUPLICATE DETECTION")
print("=" * 60)

# Backup the database
backup_path = db_path.with_stem(f"{db_path.stem}_backup")
shutil.copy(db_path, backup_path)
print(f"\n✓ Backup created at {backup_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print("\n[1] Checking current schema...")
    cursor.execute("PRAGMA index_info(sqlite_autoindex_datasets_2);")
    index_cols = cursor.fetchall()
    print(f"    UNIQUE index on: {[col[2] for col in index_cols]}")
    
    print("\n[2] Removing UNIQUE constraint by recreating table...")
    
    # Get the original table definition
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='datasets';")
    original_sql = cursor.fetchone()[0]
    print(f"    Original: {original_sql[:80]}...")
    
    # Create a new table without the UNIQUE constraint
    # The UNIQUE constraint was defined as part of the column definition
    # We need to create a new table with the same schema but without UNIQUE
    
    print("\n[3] Creating temporary table...")
    cursor.execute("""
        CREATE TABLE datasets_new AS
        SELECT * FROM datasets;
    """)
    
    print("\n[4] Dropping original table...")
    cursor.execute("DROP TABLE datasets;")
    
    print("\n[5] Creating new table without UNIQUE constraint...")
    cursor.execute("""
        CREATE TABLE datasets (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            organization_id TEXT,
            file_hash TEXT,  -- Removed UNIQUE constraint
            file_name TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            file_size_compressed INTEGER,
            file_path TEXT NOT NULL,
            file_type TEXT,
            user_id TEXT,
            user_name TEXT NOT NULL DEFAULT 'System',
            period TEXT,
            spatial_domain TEXT,
            attributes TEXT,
            description TEXT,
            tags TEXT,
            version INTEGER DEFAULT 1,
            is_latest_version INTEGER DEFAULT 1,
            source_location TEXT,
            cloud_uri TEXT,
            compression_method TEXT,
            reuse_count INTEGER DEFAULT 0,
            quality_score REAL DEFAULT 0.0,
            download_timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        );
    """)
    
    print("\n[6] Copying data back...")
    cursor.execute("""
        INSERT INTO datasets SELECT * FROM datasets_new;
    """)
    
    print("\n[7] Recreating indexes...")
    cursor.execute("DROP TABLE datasets_new;")
    cursor.execute("CREATE INDEX idx_datasets_hash      ON datasets(file_hash);")
    cursor.execute("CREATE INDEX idx_datasets_org       ON datasets(organization_id);")
    cursor.execute("CREATE INDEX idx_datasets_user      ON datasets(user_id);")
    cursor.execute("CREATE INDEX idx_datasets_file_type ON datasets(file_type);")
    cursor.execute("CREATE INDEX idx_datasets_tags      ON datasets(tags);")
    cursor.execute("CREATE INDEX idx_datasets_version   ON datasets(version);")
    cursor.execute("CREATE INDEX idx_datasets_created   ON datasets(created_at DESC);")
    
    conn.commit()
    print("\n✅ Schema fixed successfully!")
    
    print("\n[8] Verifying new schema...")
    cursor.execute("PRAGMA index_list(datasets);")
    indexes = cursor.fetchall()
    print(f"    Indexes: {len(indexes)} total")
    for idx in indexes:
        if 'autoindex' in idx[1]:
            print(f"      - {idx[1]} (unique={idx[2]}, type={idx[3]})")
    
    # Try inserting test duplicates
    print("\n[9] Testing duplicate insertion...")
    t_hash = "test_hash_001"
    
    cursor.execute("INSERT INTO datasets (file_name, file_path, file_hash) VALUES (?, ?, ?)", 
                   ("test1.txt", "C:\\test1.txt", t_hash))
    cursor.execute("INSERT INTO datasets (file_name, file_path, file_hash) VALUES (?, ?, ?)", 
                   ("test1.txt", "C:\\test_backup.txt", t_hash))
    
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM datasets WHERE file_hash = ?", (t_hash,))
    count = cursor.fetchone()[0]
    print(f"    ✓ Successfully inserted {count} files with same hash!")
    
    # Clean up test data
    cursor.execute("DELETE FROM datasets WHERE file_hash = ?", (t_hash,))
    conn.commit()
    
    print("\n" + "=" * 60)
    print("✅ DATABASE FIXED - Duplicate detection is now enabled!")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()
    print(f"\nReverting to backup: {backup_path}")
    shutil.copy(backup_path, db_path)
    
finally:
    conn.close()
