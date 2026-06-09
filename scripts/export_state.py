"""Xuat phien dang nhap (storage_state) tu profile tren PC ra 1 file JSON
de mang sang may khac (Oracle VM).

Vi sao can: cookie trong profile Chromium tren Windows duoc ma hoa bang DPAPI
(gan voi tai khoan Windows) -> copy nguyen thu muc profile sang Linux thi Chromium
Linux GIAI MA KHONG DUOC -> mat dang nhap. storage_state chua cookie da GIAI MA
(plaintext) nen mang sang may khac duoc.

File xuat ra CHUA COOKIE GOOGLE -> TUYET DOI KHONG commit / khong gui qua kenh cong khai.
Da them ca_state.json vao .gitignore. Nap xong tren VM thi xoa file nay o ca 2 may.

Chay TREN PC (may da login):  python scripts/export_state.py
Mac dinh ghi ra:  ~/ca_state.json   (doi duong dan bang bien BROWSER_STATE_FILE)
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

    profile_dir = os.environ.get(
        "BROWSER_PROFILE_DIR", os.path.expanduser("~/.ca-grafana-profile")
    )
    if not os.path.exists(profile_dir):
        sys.exit("Chua dang nhap lan nao. Chay truoc:  python scripts/login.py")

    out = os.environ.get("BROWSER_STATE_FILE", os.path.expanduser("~/ca_state.json"))

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(profile_dir, headless=True)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(core.DASHBOARD_URL, wait_until="domcontentloaded", timeout=60000)
            if "/login" in page.url or "accounts.google.com" in page.url:
                print("CANH BAO: phien Grafana co ve da het han, NHUNG cookie Google van duoc xuat.")
                print("          VM se tu chay refresh_session.py de gia han lai bang cookie Google.")
            state = ctx.storage_state()
        finally:
            ctx.close()

    with open(out, "w", encoding="utf-8") as f:
        json.dump(state, f)

    cookies = state.get("cookies", [])
    has_google = any("google" in (c.get("domain") or "") for c in cookies)
    print(f"Da xuat {len(cookies)} cookie -> {out}")
    print(f"Co cookie Google: {'CO' if has_google else 'KHONG -> can login lai bang login.py!'}")
    print("Buoc tiep: scp file nay len VM, roi chay  python scripts/seed_profile.py  tren VM.")
    print("LUU Y: file chua phien dang nhap -> KHONG commit, nap xong thi xoa.")


if __name__ == "__main__":
    main()
