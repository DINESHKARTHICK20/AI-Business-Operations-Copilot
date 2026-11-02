import sqlite3
from pathlib import Path

db_path = Path("backend/ai_bizops.db")
print("DB exists:", db_path.exists())

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print("Tables in DB:", tables)

for t in tables:
    cursor.execute(f"PRAGMA table_info({t})")
    cols = cursor.fetchall()
    cursor.execute(f"SELECT COUNT(*) FROM {t}")
    cnt = cursor.fetchone()[0]
    print(f"Table '{t}' ({cnt} rows):")
    for c in cols:
        print(f"  - col {c[0]}: {c[1]} ({c[2]})")

conn.close()
