#!/usr/bin/env python3
"""
Create test duplicate data for testing the duplicate detector
"""
import sys
import os
import sqlite3
from pathlib import Path

# Get database path
db_path = Path(__file__).parent / "data" / "ddas.db"

if not db_path.exists():
    print(f"ERROR: Database not found at {db_path}")
    sys.exit(1)

print(f"Connecting to database at {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check current data
cursor.execute("SELECT COUNT(*) FROM datasets;")
count_before = cursor.fetchone()[0]
print(f"\n[INFO] datasets table has {count_before} records before")

# Now let's create some test duplicate data
print("\nInserting test duplicate data...")
try:
    # Insert first file
    cursor.execute("""
        INSERT INTO datasets 
        (id, file_name, file_path, file_size, file_type, file_hash, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        "dup_test_1",
        "report.pdf",
        "C:\\Users\\Kishor\\Documents\\report.pdf",
        512000,
        ".pdf",
        "abc123_duplicate_hash_001",
        "2024-01-15 10:00:00"
    ])
    
    # Insert duplicate file (same hash)
    cursor.execute("""
        INSERT INTO datasets 
        (id, file_name, file_path, file_size, file_type, file_hash, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        "dup_test_2",
        "report.pdf",
        "C:\\Users\\Kishor\\Downloads\\report.pdf",
        512000,
        ".pdf",
        "abc123_duplicate_hash_001",
        "2024-01-15 10:05:00"
    ])
    
    # Insert third file (another duplicate of same hash)
    cursor.execute("""
        INSERT INTO datasets 
        (id, file_name, file_path, file_size, file_type, file_hash, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        "dup_test_3",
        "report.pdf",
        "C:\\report_backup.pdf",
        512000,
        ".pdf",
        "abc123_duplicate_hash_001",
        "2024-01-15 10:10:00"
    ])
    
    # Insert another duplicate group (different hash)
    cursor.execute("""
        INSERT INTO datasets 
        (id, file_name, file_path, file_size, file_type, file_hash, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        "dup_test_4",
        "image.png",
        "C:\\Users\\Kishor\\Pictures\\image.png",
        2048000,
        ".png",
        "xyz789_duplicate_hash_002",
        "2024-01-15 11:00:00"
    ])
    
    # Insert duplicate image
    cursor.execute("""
        INSERT INTO datasets 
        (id, file_name, file_path, file_size, file_type, file_hash, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        "dup_test_5",
        "image.png",
        "C:\\Users\\Kishor\\Downloads\\image.png",
        2048000,
        ".png",
        "xyz789_duplicate_hash_002",
        "2024-01-15 11:05:00"
    ])
    
    conn.commit()
    print("✓ Test duplicate data inserted successfully")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()

# Query to verify duplicates
cursor.execute("SELECT COUNT(*) FROM datasets;")
count_after = cursor.fetchone()[0]
print(f"\nBefore: {count_before} records")
print(f"After: {count_after} records")
print(f"Inserted: {count_after - count_before} new records")

print("\nVerifying duplicate groups...")
cursor.execute("""
    SELECT file_hash, COUNT(*) as count FROM datasets 
    GROUP BY file_hash 
    HAVING count > 1
    ORDER BY count DESC
""")
duplicates = cursor.fetchall()
print(f"Found {len(duplicates)} duplicate groups:")

for file_hash, count in duplicates:
    print(f"\n  📋 Hash: {file_hash} [{count} copies]")
    cursor.execute("SELECT file_name, file_path, file_size FROM datasets WHERE file_hash = ? ORDER BY created_at", (file_hash,))
    files = cursor.fetchall()
    for filename, path, size in files:
        size_kb = size / 1024
        print(f"    • {filename} ({size_kb:.1f} KB)")
        print(f"      └─ {path}")

# Calculate total wasted space
cursor.execute("""
    SELECT 
        SUM((count - 1) * file_size) as wasted_bytes,
        SUM(count - 1) as wasted_files
    FROM (
        SELECT file_hash, COUNT(*) as count, MAX(file_size) as file_size
        FROM datasets
        GROUP BY file_hash
        HAVING count > 1
    )
""")
result = cursor.fetchone()
wasted_bytes, wasted_files = result if result[0] else (0, 0)
if wasted_bytes:
    wasted_mb = wasted_bytes / (1024 * 1024)
    print(f"\n💾 Wasted Space: {wasted_mb:.2f} MB ({wasted_files} duplicate files)")

conn.close()
print("\n✅ Done!")
