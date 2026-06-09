"""
Đăng nhập Grafana 1 lần (Cách 2). Mở cửa sổ trình duyệt thật để bạn bấm
"Đăng nhập bằng Google". Phiên đăng nhập được lưu lại trong một thư mục hồ sơ
riêng (KHÔNG nằm trong project, không bị đẩy lên GitHub) để các lần tải sau dùng lại.

Chạy:  python scripts/login.py
Khi nào tải dữ liệu báo "Phiên đã hết hạn" thì chạy lại file này.
"""
import os
import sys

import core


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Chưa cài Playwright. Chạy: pip install playwright && playwright install chromium")

    profile_dir = os.environ.get(
        "BROWSER_PROFILE_DIR", os.path.expanduser("~/.ca-grafana-profile")
    )
    os.makedirs(profile_dir, exist_ok=True)
    print(f"Hồ sơ trình duyệt lưu tại: {profile_dir}")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(profile_dir, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(core.DASHBOARD_URL, wait_until="domcontentloaded")

        print("\n" + "=" * 60)
        print("  CỬA SỔ TRÌNH DUYỆT ĐÃ MỞ.")
        print("  → Bấm 'Đăng nhập bằng Google' và đăng nhập cho tới khi")
        print("    THẤY DASHBOARD hiện ra bình thường.")
        print("  → KHÔNG cần nhấn gì. Script tự nhận ra khi đăng nhập xong")
        print("    rồi tự lưu phiên và đóng cửa sổ.")
        print("=" * 60 + "\n")
        sys.stdout.flush()

        # Tu dong phat hien dang nhap xong: URL quay ve dashboard (/d/zvSN7-x4z)
        # va khong con o trang dang nhap Google. Poll toi da 6 phut.
        import time
        deadline = time.time() + 360
        logged_in = False
        while time.time() < deadline:
            url = page.url
            if "/d/zvSN7-x4z" in url and "accounts.google.com" not in url and "/login" not in url:
                logged_in = True
                break
            page.wait_for_timeout(2000)

        if logged_in:
            page.wait_for_timeout(4000)  # cho cookie ghi xuong dia
            print("Da nhan dien dang nhap thanh cong.")
        else:
            print("Het thoi gian cho (6 phut) ma chua thay dashboard. Luu tam phien hien co.")
        sys.stdout.flush()

        ctx.close()
    print("Đã lưu phiên đăng nhập. Giờ có thể chạy: python scripts/download_csv.py")


if __name__ == "__main__":
    main()
