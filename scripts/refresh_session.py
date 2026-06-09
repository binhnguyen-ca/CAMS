"""Lam moi phien Grafana TRUOC moi lan chay (khong can nhap tay).

Vi sao can: grafana_session cua Selless rat ngan (~vai gio), nhung cookie Google
trong profile song toi 2027. Khi grafana_session het han, chi can "Sign in with
Google" lai -- thao tac nay KHONG can mat khau vi cookie Google con han. Script
nay tu lam dieu do bang Playwright headless.

Quy trinh:
  1. Mo dashboard bang profile da luu.
  2. Neu vao thang dashboard -> phien con tot, xong.
  3. Neu bi day ra trang login Grafana -> bam <a href="login/google">.
  4. Neu Google hien chon tai khoan -> bam dung email.
  5. Cho toi khi URL ve dashboard (/d/zvSN7-x4z) -> luu phien, thoat 0.
  6. Het gio ma khong vao duoc -> thoat khac 0 (can dang nhap tay: login.py).

Chay tay:  python scripts/refresh_session.py
"""
import os
import sys
import time

import core

# Email Google de chon dung tai khoan khi co man hinh chon account (multi-account profile).
# Doc tu env de KHONG hardcode email ca nhan trong repo. Profile chi 1 account -> de trong cung OK.
EMAIL = os.environ.get("GRAFANA_LOGIN_EMAIL", "")
DASH_MARK = "/d/zvSN7-x4z"          # URL co doan nay = da o dashboard
DEADLINE_S = 90                     # toi da cho 90 giay


def _is_dashboard(url: str) -> bool:
    return DASH_MARK in url and "accounts.google.com" not in url and "/login" not in url


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Chua cai Playwright. Chay: pip install playwright && playwright install chromium")

    profile_dir = os.environ.get(
        "BROWSER_PROFILE_DIR", os.path.expanduser("~/.ca-grafana-profile")
    )
    if not os.path.exists(profile_dir):
        print("Chua dang nhap lan nao. Chay:  python scripts/login.py")
        return 2

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(profile_dir, headless=True)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(core.DASHBOARD_URL, wait_until="domcontentloaded", timeout=60000)

            deadline = time.time() + DEADLINE_S
            clicked_google = False
            while time.time() < deadline:
                url = page.url
                if _is_dashboard(url):
                    page.wait_for_timeout(3000)   # cho cookie ghi xuong dia
                    print("Phien OK, da lam moi.")
                    return 0

                # Tren trang login Grafana -> bam nut Google (chi bam 1 lan)
                if "grafana.selless.com" in url and "/login" in url and not clicked_google:
                    link = page.query_selector('a[href="login/google"]') or page.query_selector('a[href$="/login/google"]')
                    if link:
                        link.click()
                        clicked_google = True
                        page.wait_for_timeout(2000)
                        continue

                # Man hinh dong y quyen (consent) -> bam Allow
                if "accounts.google.com" in url:
                    allow = page.query_selector("#submit_approve_access")
                    if allow:
                        try:
                            allow.click(timeout=4000)
                            page.wait_for_timeout(2500)
                            continue
                        except Exception:
                            pass

                # Tren trang chon tai khoan Google -> bam dung o tai khoan (chi khi co EMAIL)
                if "accounts.google.com" in url and EMAIL:
                    picked = False
                    # uu tien click ca o <li> (account tile), roi cac fallback
                    for loc in (page.locator(f'li:has-text("{EMAIL}")').first,
                                page.locator(f'[data-email="{EMAIL}"]').first,
                                page.locator(f'[data-identifier="{EMAIL}"]').first,
                                page.get_by_text(EMAIL, exact=False).first):
                        try:
                            if loc.count() > 0:
                                loc.click(timeout=4000)
                                picked = True
                                break
                        except Exception:
                            continue
                    page.wait_for_timeout(2500)
                    if picked:
                        continue

                page.wait_for_timeout(1500)

            print("Het gio cho. Co the can dang nhap tay:  python scripts/login.py")
            return 1
        finally:
            ctx.close()


if __name__ == "__main__":
    sys.exit(main())
