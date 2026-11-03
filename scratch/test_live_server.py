import sys
import threading
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn
from backend.ai_backend import app

server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning"))
t = threading.Thread(target=server.run, daemon=True)
t.start()

time.sleep(1.5)

try:
    with urllib.request.urlopen("http://127.0.0.1:8000/", timeout=3) as resp:
        html = resp.read().decode("utf-8")
        print("Root response code:", resp.status)
        print("Root response has index.html title:", "AI Business Operations Copilot" in html)

    with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3) as resp:
        health_json = resp.read().decode("utf-8")
        print("Health response code:", resp.status)
        print("Health JSON:", health_json)

    with urllib.request.urlopen("http://127.0.0.1:8000/dashboard", timeout=3) as resp:
        spa_html = resp.read().decode("utf-8")
        print("SPA /dashboard response code:", resp.status)
        print("SPA /dashboard served index.html:", "AI Business Operations Copilot" in spa_html)

    # Check that static asset (js) is served by /assets mount
    from backend.ai_backend import DIST_ASSETS_DIR
    js_file = list(DIST_ASSETS_DIR.glob("*.js"))[0].name
    with urllib.request.urlopen(f"http://127.0.0.1:8000/assets/{js_file}", timeout=3) as resp:
        print("Static asset response code:", resp.status)
        print("Static asset content-type:", resp.headers.get("content-type"))

    print("ALL LIVE HTTP PROBES COMPLETED SUCCESSFULLY!")
except Exception as e:
    print("Error during HTTP probe:", type(e), e)
finally:
    server.should_exit = True

