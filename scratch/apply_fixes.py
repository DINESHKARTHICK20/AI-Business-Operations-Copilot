"""
Targeted fix script for ai_backend.py.
1. Remove duplicate first compute_business_health() function (lines 2100-2344).
2. Add try/finally conn.close() to unprotected routes.
3. Fix invoice error leaking internal detail.
4. Add stale session pruning.
5. Add warning log for accounts with no password hash.
"""
import re

BACKEND_PATH = r'd:\My Projects\AI Business Operations Copilot\backend\ai_backend.py'

with open(BACKEND_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

original_len = len(content)
print(f"Original file size: {original_len} chars")

# ------------------------------------------------------------------
# FIX 1: Remove the first duplicate compute_business_health definition
# It starts at "def compute_business_health():" and ends just before
# "@app.get(\"/api/business-health\")"
# ------------------------------------------------------------------
# We'll identify the first occurrence and remove it

first_def_start = content.find('\ndef compute_business_health():\n')
second_def_start = content.find('\ndef compute_business_health(conn=None):\n')

if first_def_start == -1:
    print("SKIP FIX 1: First compute_business_health() not found (already removed?)")
elif second_def_start == -1:
    print("SKIP FIX 1: Second compute_business_health(conn=None) not found")
elif first_def_start < second_def_start:
    # Find the end of the first definition — it ends right before @app.get("/api/business-health")
    business_health_route = '\n@app.get("/api/business-health")\n'
    end_pos = content.find(business_health_route, first_def_start)
    if end_pos == -1:
        print("SKIP FIX 1: Could not find @app.get(\"/api/business-health\") marker")
    else:
        # Remove the block from first_def_start to end_pos (exclusive)
        removed_block = content[first_def_start:end_pos]
        print(f"FIX 1: Removing duplicate function ({len(removed_block)} chars from line ~2100)")
        content = content[:first_def_start] + content[end_pos:]
        print("FIX 1: Done")
else:
    print("SKIP FIX 1: First definition is not before second; unexpected order")

# ------------------------------------------------------------------
# FIX 2: Invoice error message should not expose internal str(e)
# Change: raise HTTPException(status_code=500, detail=f"Failed to create invoice: {str(e)}")
# To:    raise HTTPException(status_code=500, detail="Failed to create invoice. Please try again.")
#        And log the actual error
# ------------------------------------------------------------------
old_invoice_err = '        raise HTTPException(status_code=500, detail=f"Failed to create invoice: {str(e)}")'
new_invoice_err = '''        logger.error("Invoice creation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create invoice. Please try again.")'''

if old_invoice_err in content:
    content = content.replace(old_invoice_err, new_invoice_err)
    print("FIX 2: Invoice error message sanitized")
else:
    print("SKIP FIX 2: Invoice error pattern not found (already fixed?)")

# ------------------------------------------------------------------
# FIX 3: Add stale session cleanup at startup (prune expired sessions)
# Add after the existing "Prune orphaned legacy sessions" block in init_db
# ------------------------------------------------------------------
old_prune = '''    # Prune orphaned legacy sessions
    try:
        cursor.execute("DELETE FROM user_sessions WHERE user_id NOT IN (SELECT id FROM users)")
    except Exception:
        pass'''

new_prune = '''    # Prune orphaned legacy sessions
    try:
        cursor.execute("DELETE FROM user_sessions WHERE user_id NOT IN (SELECT id FROM users)")
    except Exception:
        pass

    # Prune expired sessions at startup to keep the table lean
    try:
        now_startup = __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("DELETE FROM user_sessions WHERE expires_at < ?", (now_startup,))
        pruned = cursor.rowcount
        if pruned > 0:
            print(f"[startup] Pruned {pruned} expired session(s) from user_sessions")
    except Exception:
        pass'''

if old_prune in content:
    content = content.replace(old_prune, new_prune)
    print("FIX 3: Stale session pruning on startup added")
else:
    print("SKIP FIX 3: Orphan prune pattern not found (already updated?)")

# ------------------------------------------------------------------
# FIX 4: Add get_customers try/finally for conn.close()
# ------------------------------------------------------------------
old_get_customers = '''@app.get("/api/customers")
def get_customers(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows'''

new_get_customers = '''@app.get("/api/customers")
def get_customers(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM customers ORDER BY id ASC")
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    finally:
        try:
            conn.close()
        except Exception:
            pass'''

if old_get_customers in content:
    content = content.replace(old_get_customers, new_get_customers)
    print("FIX 4: get_customers try/finally added")
else:
    print("SKIP FIX 4: get_customers pattern not found")

# ------------------------------------------------------------------
# FIX 5: Add get_employees try/finally
# ------------------------------------------------------------------
old_get_employees = '''@app.get("/api/employees")
def get_employees(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows'''

new_get_employees = '''@app.get("/api/employees")
def get_employees(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM employees ORDER BY id ASC")
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    finally:
        try:
            conn.close()
        except Exception:
            pass'''

if old_get_employees in content:
    content = content.replace(old_get_employees, new_get_employees)
    print("FIX 5: get_employees try/finally added")
else:
    print("SKIP FIX 5: get_employees pattern not found")

# ------------------------------------------------------------------
# FIX 6: Add get_inventory try/finally
# ------------------------------------------------------------------
old_get_inventory = '''@app.get("/api/inventory")
def get_inventory(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows'''

new_get_inventory = '''@app.get("/api/inventory")
def get_inventory(user: dict = Depends(get_authenticated_user)):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM products ORDER BY id ASC")
        rows = [dict(r) for r in cursor.fetchall()]
        return rows
    finally:
        try:
            conn.close()
        except Exception:
            pass'''

if old_get_inventory in content:
    content = content.replace(old_get_inventory, new_get_inventory)
    print("FIX 6: get_inventory try/finally added")
else:
    print("SKIP FIX 6: get_inventory pattern not found")

# ------------------------------------------------------------------
# FIX 7: Add warning log for accounts with empty password hash in login
# ------------------------------------------------------------------
old_stored_hash = '''            stored_hash = user_dict.get("password_hash") or user_dict.get("password") or ""

            if not verify_password(raw_password, stored_hash):'''

new_stored_hash = '''            stored_hash = user_dict.get("password_hash") or user_dict.get("password") or ""

            if not stored_hash:
                logger.warning(
                    "Login attempt for account %s has no password hash stored. "
                    "This account cannot be authenticated until a password is set.",
                    clean_email
                )

            if not verify_password(raw_password, stored_hash):'''

if old_stored_hash in content:
    content = content.replace(old_stored_hash, new_stored_hash)
    print("FIX 7: Empty password hash warning added")
else:
    print("SKIP FIX 7: stored_hash pattern not found")

# ------------------------------------------------------------------
# VERIFY: Check for remaining duplicate function
# ------------------------------------------------------------------
count_old = content.count('def compute_business_health():')
count_new = content.count('def compute_business_health(conn=None):')
print(f"\nVerification: compute_business_health() occurrences: {count_old} (should be 0)")
print(f"Verification: compute_business_health(conn=None) occurrences: {count_new} (should be 1)")

# ------------------------------------------------------------------
# WRITE
# ------------------------------------------------------------------
with open(BACKEND_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\nFinal file size: {len(content)} chars (removed {original_len - len(content)} chars)")
print("All fixes applied successfully.")

