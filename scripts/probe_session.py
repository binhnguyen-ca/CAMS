"""PROBE: thu lay du lieu Grafana CHI bang cookie + requests (KHONG dung browser).

Muc dich kiem chung y tuong "browser-less": co the snapshot ma khong can Playwright/PC,
bang cach (1) doc cookie tu profile da login, (2) goi /api/ds/query bang requests thuan,
(3) xem Grafana co tra ve cookie grafana_session MOI (xoay token) hay khong.

Neu HTTP 200 + co cookie moi -> co the chay hourly o BAT KY dau (GitHub Actions /
Cloudflare Workers / dien thoai cu), khong can browser, khong dinh loi "Google chan IP la".

Chay TREN PC (da login):  python scripts/probe_session.py
Script nay CHI DOC (query SELECT) — khong ghi file, khong push.
"""
import os
import sys
import json

import core
import snapshot as snap


def get_selless_cookies() -> dict:
    """Doc cookie cho *.selless.com tu profile Chromium da login."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Chua cai Playwright. Chay: pip install playwright && playwright install chromium")
    profile_dir = os.environ.get(
        "BROWSER_PROFILE_DIR", os.path.expanduser("~/.ca-grafana-profile")
    )
    if not os.path.exists(profile_dir):
        sys.exit("Chua dang nhap. Chay truoc: python scripts/login.py")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(profile_dir, headless=True)
        try:
            page = ctx.new_page()
            page.goto(core.DASHBOARD_URL, wait_until="domcontentloaded", timeout=60000)
            if "/login" in page.url or "accounts.google.com" in page.url:
                print("CANH BAO: phien co ve da het. Chay refresh_session.py truoc roi thu lai.")
            cookies = ctx.cookies()
        finally:
            ctx.close()
    return {c["name"]: c["value"] for c in cookies if "selless.com" in (c.get("domain") or "")}


def main():
    import requests

    jar = get_selless_cookies()
    gs = jar.get("grafana_session")
    print(f"Cookie selless: {len(jar)} cai | grafana_session truoc: "
          f"{(gs[:10] + '...') if gs else 'KHONG CO'}")
    if not gs:
        sys.exit("Khong tim thay grafana_session -> can login lai.")

    cfg = snap.load_config()
    products = cfg.get("products") or ["RosyLift 1.0"]
    body, now_vn = snap.build_body(products)

    headers = core.query_headers()
    headers["cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items())
    headers["referer"] = core.DASHBOARD_URL
    headers["origin"] = core.GRAFANA_BASE

    print(f"Goi {core.QUERY_URL}  (SP: {', '.join(products)})")
    resp = requests.post(core.QUERY_URL, headers=headers, data=json.dumps(body), timeout=60)
    print(f"--> HTTP {resp.status_code}")

    # Co cookie grafana_session MOI tra ve khong? (xoay token)
    new_gs = resp.cookies.get("grafana_session")
    set_cookie_raw = resp.headers.get("set-cookie", "")
    rotated = bool(new_gs) or ("grafana_session" in set_cookie_raw)
    print(f"--> Grafana tra cookie grafana_session MOI (xoay token): {'CO' if rotated else 'khong'}")
    if new_gs:
        print(f"    grafana_session moi: {new_gs[:10]}...  (khac cu: {new_gs != gs})")

    if resp.status_code == 200:
        try:
            header, rows = core.parse_frames(resp.json())
            print(f"--> OK: query tra ve {len(rows)} dong, {len(header)} cot.")
            print("==> KET LUAN: BROWSER-LESS CHAY DUOC. Co the snapshot bang requests + cookie o bat ky dau.")
            if not rotated:
                print("    (Luu y: lan nay khong thay cookie moi -> can theo doi tuoi phien qua nhieu gio.)")
        except SystemExit as e:
            print(f"--> Parse loi: {e}")
    elif resp.status_code in (401, 403):
        print(f"--> Bi tu choi ({resp.status_code}). Body: {resp.text[:300]}")
        print("    Co the Grafana doi CSRF/Origin khac, hoac phien het. Se xu ly tiep.")
    else:
        print(f"--> Body: {resp.text[:300]}")


if __name__ == "__main__":
    main()
