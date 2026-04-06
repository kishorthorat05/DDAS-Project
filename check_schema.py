import sqlite3

conn = sqlite3.connect('data/ddas.db')
cursor = conn.cursor()

# Check indexes
print("Indexes on datasets table:")
cursor.execute("PRAGMA index_list(datasets);")
for row in cursor.fetchall():
    print(f"  {row}")

# Check which columns have UNIQUE constraint
print("\nColumns in sqlite_autoindex_datasets_2 (UNIQUE):")
cursor.execute("PRAGMA index_info(sqlite_autoindex_datasets_2);")
for row in cursor.fetchall():
    print(f"  {row}")

# Check if there's a UNIQUE constraint
print("\nIndex definitions:")
cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='datasets';")
for row in cursor.fetchall():
    print(f"  {row}")

conn.close()
