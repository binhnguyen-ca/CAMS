"""Nap phien (cookie + localStorage) tu ca_state.json vao profile Chromium TREN VM (Linux).

Chay 1 LAN tren VM, sau khi da scp ca_state.json (xuat tu PC bang export_state.py) len.

  python scripts/seed_profile.py

Sau buoc nay profile ~/.ca-grafana-profile tren VM da co cookie Google -> moi script
khac (snapshot.py, download_hourly.py...) dung profile binh thuong; refresh_session.py
tu gia han phien Grafana ngan han bang cookie Google (song toi 2027).
"""
import os
import sys
import json

import core


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Chua cai Playwright. Chay: pip install playwright && playwright install chromium")

    state_file = os.environ.get("BROWSER_STATE_FILE", os.path.expanduser("~/ca_state.json"))
    if not os.path.exists(state_file):
        sys.exit(f"Khong thay {state_file}. Hay scp ca_state.json (tu PC) len truoc.")

    with open(state_file, "r", encoding="utf-8") as f:
        state = json.load(f)
    cookies = state.get("cookies", [])
    origins = state.get("origins", [])

    profile_dir = os.environ.get(
        "BROWSER_PROFILE_DIR", os.path.expanduser("~/.ca-grafana-profile")
    )
    os.makedirs(profile_dir, exist_ok=True)

    url = ""
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(profile_dir, headless=True)
        try:
            if cookies:
                ctx.add_cookies(cookies)
            page = ctx.new_page()
            # Khoi phuc localStorage tung origin (best-effort; phien chu yeu nam o cookie).
            for o in origins:
                origin = o.get("origin")
                items = o.get("localStorage") or []
                if not origin or not items:
                    continue
                try:
                    page.goto(origin, wait_until="domcontentloaded", timeout=30000)
                    page.evaluate(
                        "items => { for (const it of items) localStorage.setItem(it.name, it.value); }",
                        items,
                    )
                except Exception as e:
                    print(f"  (bo qua localStorage {origin}: {e})")
            # Kiem tra phien
            page.goto(core.DASHBOARD_URL, wait_until="domcontentloaded", timeout=60000)
            url = page.url
        finally:
            ctx.close()

    print(f"Da nap {len(cookies)} cookie vao profile: {profile_dir}")
    if "/login" in url or "accounts.google.com" in url:
        print("Chua vao thang dashboard -> chay tiep:  python scripts/refresh_session.py")
        print("Neu refresh_session bao het gio (Google chan IP la) -> dung cach login VNC trong DEPLOY_ORACLE.md.")
    else:
        print("Vao thang dashboard -> phien OK. Co the xoa ca_state.json.")


if __name__ == "__main__":
    main()
