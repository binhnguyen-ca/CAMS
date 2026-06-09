"""In CHUOI COOKIE (da XAC THUC con han) de dan vao GitHub secret GRAFANA_COOKIE.

QUAN TRONG: ban nay KHONG mo dashboard (khong page.goto) nen KHONG lam Grafana
"xoay" (rotate) token -> cookie lay ra GIU NGUYEN gia tri va dung duoc lau. Sau khi
dan vao secret, chi runner goi /api/ds/query (endpoint nay KHONG xoay) -> cookie ben.

- stdout: CHI 1 dong = chuoi cookie (chi in khi da xac thuc 200).
- stderr: trang thai + huong dan.
Chay TREN PC (da login):  python scripts/print_cookie.py

Neu bao COOKIE KHONG HOP LE -> chay  python scripts/refresh_session.py  roi thu lai.
LUU Y: chuoi cookie LA phien dang nhap song -> KHONG commit / KHONG chia se cong khai.
"""
import os
import sys
import json
from datetime import datetime

import core


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Chua cai Playwright. Chay: pip install playwright && playwright install chromium")
    profile_dir = os.environ.get(
        "BROWSER_PROFILE_DIR", os.path.expanduser("~/.ca-grafana-profile")
    )
    if not os.path.exists(profile_dir):
        sys.exit("Chua dang nhap. Chay: python scripts/login.py")

    # Doc cookie tu profile -> KHONG navigate (tranh lam Grafana xoay token).
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(profile_dir, headless=True)
        try:
            cookies = ctx.cookies()
        finally:
            ctx.close()

    jar = {c["name"]: c["value"] for c in cookies if "selless.com" in (c.get("domain") or "")}
    if "grafana_session" not in jar:
        sys.exit("Khong tim thay grafana_session. Chay: python scripts/login.py")
    cookie_str = "; ".join(f"{k}={v}" for k, v in jar.items())

    # Xac thuc cookie con han bang 1 query /api/ds/query (endpoint nay KHONG xoay token).
    import requests
    headers = core.query_headers()
    headers["cookie"] = cookie_str
    headers["referer"] = core.DASHBOARD_URL
    headers["origin"] = core.GRAFANA_BASE
    body = core.build_body(datetime.now(core.VN_TZ))
    try:
        r = requests.post(core.QUERY_URL, headers=headers, data=json.dumps(body), timeout=60)
    except Exception as e:
        sys.exit(f"Loi mang khi xac thuc cookie: {e}")

    if r.status_code != 200:
        print(f"COOKIE KHONG HOP LE (HTTP {r.status_code}) -> phien co the het han.", file=sys.stderr)
        print("Chay:  python scripts/refresh_session.py   roi chay lai print_cookie.py.", file=sys.stderr)
        sys.exit(1)

    print(f"Cookie DA XAC THUC con han (200, {len(cookie_str)} ky tu). "
          "Dan dong DUOI vao secret GRAFANA_COOKIE:", file=sys.stderr)
    print(cookie_str)   # stdout: CHI cookie


if __name__ == "__main__":
    main()
