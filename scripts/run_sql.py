"""Chạy 1 câu SQL tùy ý (READ-ONLY khuyến nghị) lên datasource Grafana qua phiên
trình duyệt đã đăng nhập. Dùng để introspect schema / kiểm tra dữ liệu.

    python scripts/run_sql.py < query.sql      # đọc SQL từ stdin
"""
import os
import sys
import json

import core

sql = sys.stdin.read()
if not sql.strip():
    sys.exit("Không có SQL (truyền qua stdin).")

body = {
    "queries": [{
        "refId": "A",
        "datasource": {"type": "grafana-postgresql-datasource", "uid": core.DATASOURCE_UID},
        "rawSql": sql,
        "format": "table",
        "datasourceId": core.DATASOURCE_ID,
        "intervalMs": 120000,
        "maxDataPoints": 942,
    }],
    "from": "1700000000000",
    "to": "1900000000000",
}

from playwright.sync_api import sync_playwright

profile_dir = os.environ.get("BROWSER_PROFILE_DIR", os.path.expanduser("~/.ca-grafana-profile"))
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(profile_dir, headless=True)
    try:
        page = ctx.new_page()
        page.goto(core.DASHBOARD_URL, wait_until="domcontentloaded", timeout=60000)
        if "/login" in page.url or "accounts.google.com" in page.url:
            sys.exit("Phiên hết hạn. Chạy lại: python scripts/login.py")
        resp = ctx.request.post(core.QUERY_URL, data=json.dumps(body),
                                headers=core.query_headers(), timeout=60000)
        status, text = resp.status, resp.text()
    finally:
        ctx.close()

if status != 200:
    sys.exit(f"LỖI HTTP {status}: {text[:500]}")

header, rows = core.parse_frames(json.loads(text))
print(" | ".join(map(str, header)))
print("-" * 60)
for r in rows:
    print(" | ".join("" if v is None else str(v) for v in r))
print(f"\n({len(rows)} rows)")
