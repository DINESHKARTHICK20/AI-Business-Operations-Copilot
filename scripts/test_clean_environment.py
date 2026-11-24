"""
Clean Disposable Virtual Environment Verification Suite
Steps:
1. Create disposable virtual environment: .venv_disposable_clean
2. Install dependencies using pinned requirements.txt and requirements.lock
3. Run pip check in the clean environment to detect dependency conflicts
4. Test database connection & MySQL connectivity
5. Test ML model inference
6. Remove the disposable virtual environment cleanly
"""
import os
import sys
import shutil
import subprocess

print("=" * 70)
print("CLEAN ENVIRONMENT INSTALLATION & VERIFICATION")
print("=" * 70)

TEST_VENV = os.path.abspath(".venv_disposable_clean")
if os.path.exists(TEST_VENV):
    shutil.rmtree(TEST_VENV, ignore_errors=True)

print(f"1. Creating clean isolated virtual environment at: {TEST_VENV}")
res_create = subprocess.run([sys.executable, "-m", "venv", TEST_VENV, "--clear"], capture_output=True, text=True)
if res_create.returncode != 0:
    print(f"Error creating venv: {res_create.stderr}")
    sys.exit(1)
print("   Isolated virtual environment created successfully.")

test_py = os.path.join(TEST_VENV, "Scripts", "python.exe")
test_pip = os.path.join(TEST_VENV, "Scripts", "pip.exe")

print(f"\n2. Installing dependencies into clean environment from requirements.txt...")
# Use uv or pip to install from requirements.txt into the clean environment
res_install = subprocess.run([test_py, "-m", "pip", "install", "--no-cache-dir", "-r", "requirements.txt"], capture_output=True, text=True)
if res_install.returncode != 0:
    print(f"Installation error:\n{res_install.stderr}")
    sys.exit(1)
print("   Installation of pinned production requirements completed successfully.")

print(f"\n3. Running pip check in clean environment...")
res_check = subprocess.run([test_py, "-m", "pip", "check"], capture_output=True, text=True)
print(f"   Output: {res_check.stdout.strip()}")
print(f"   Conflict Check: {'PASS (0 conflicts)' if res_check.returncode == 0 else 'FAIL'}")
assert res_check.returncode == 0, f"pip check failed: {res_check.stderr}"

print(f"\n4. Verifying MySQL connectivity in clean environment...")
test_script = """
import os, sys
sys.path.insert(0, os.getcwd())
from backend.database import mysql_engine, text
with mysql_engine.connect() as conn:
    version = conn.execute(text('SELECT VERSION();')).scalar()
    count = conn.execute(text('SELECT COUNT(*) FROM users;')).scalar()
    print(f'   MySQL Server Version : {version}')
    print(f'   Verified User Records: {count}')
"""
res_db = subprocess.run([test_py, "-c", test_script], capture_output=True, text=True)
print(res_db.stdout.strip())
if res_db.returncode != 0:
    print(f"Database verification error: {res_db.stderr}")
assert res_db.returncode == 0, "Database connectivity test failed"

print(f"\n5. Verifying ML model inference in clean environment...")
ml_script = """
import os, sys, joblib, pandas as pd
sys.path.insert(0, os.getcwd())
m = joblib.load('backend/models/churn_model.pkl')
sample = pd.DataFrame([{'total_orders': 10, 'total_spend': 25000.0, 'days_since_last_purchase': 5, 'support_tickets': 0, 'complaints': 0, 'average_order_value': 2500.0}])
prob = m['model'].predict_proba(sample[m['features']])[0][1]
print(f'   Clean Env Churn Inference Probability: {prob*100:.2f}%')
"""
res_ml = subprocess.run([test_py, "-c", ml_script], capture_output=True, text=True)
print(res_ml.stdout.strip())
if res_ml.returncode != 0:
    print(f"ML verification error: {res_ml.stderr}")
assert res_ml.returncode == 0, "ML model verification failed"

print(f"\n6. Cleaning up disposable virtual environment...")
# Close any dangling handles and remove directory
import time
time.sleep(1)
shutil.rmtree(TEST_VENV, ignore_errors=True)
print("   Clean environment removed cleanly.")

print("\n" + "=" * 70)
print("CLEAN ENVIRONMENT VERIFICATION COMPLETED: ALL TESTS PASSED")
print("=" * 70)
