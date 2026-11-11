import sqlite3
conn = sqlite3.connect('backend/ai_bizops.db')
c = conn.cursor()
c.execute('SELECT id, name, email, password_hash, password, is_active FROM users WHERE id IN (1,2,3,21,24)')
rows = c.fetchall()
for r in rows:
    phash = r[3] or ''
    ppw = r[4] or ''
    is_bcrypt_hash = phash.startswith(('$2b$', '$2a$', '$2y$'))
    is_bcrypt_pw = ppw.startswith(('$2b$', '$2a$', '$2y$'))
    print(f'id={r[0]} name={r[1]} email={r[2]} active={r[5]}')
    print(f'  password_hash[0:30]: {repr(phash[:30])} is_bcrypt={is_bcrypt_hash}')
    print(f'  password[0:30]:      {repr(ppw[:30])} is_bcrypt={is_bcrypt_pw}')
conn.close()

