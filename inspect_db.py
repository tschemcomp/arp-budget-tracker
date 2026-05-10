import sqlite3
import os

db_path = r"C:\Users\CHEMISTRY\Desktop\arp_budget.db"

if not os.path.exists(db_path):
    print("Database file not found at:", db_path)
    exit()

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cur.fetchall()]
print("TABLES FOUND:", tables)
print("=" * 50)

for t in tables:
    print(f"\n--- TABLE: {t} ---")
    cur.execute(f"PRAGMA table_info({t})")
    print("Columns:")
    for col in cur.fetchall():
        print(" ", col)
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    count = cur.fetchone()[0]
    print(f"Total rows: {count}")
    if count > 0:
        cur.execute(f"SELECT * FROM {t} LIMIT 5")
        print("Sample rows:")
        for row in cur.fetchall():
            print(" ", row)

conn.close()
