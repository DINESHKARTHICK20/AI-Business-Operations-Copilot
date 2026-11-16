import sqlite3
import os

db_path = 'backend/ai_bizops.db'
if not os.path.exists(db_path):
    print("Database file not found at", db_path)
else:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cur.fetchall()]
    print("Tables:", tables)
    for t in tables:
        cur.execute(f"PRAGMA table_info({t});")
        cols = cur.fetchall()
        print(f"Table {t} columns:", [(c[1], c[2]) for c in cols])
    conn.close()
