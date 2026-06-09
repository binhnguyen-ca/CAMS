"""Lõi dùng chung cho mọi cách lấy dữ liệu (browser hoặc token).

Tách riêng để sau này đổi từ Cách 2 (chạy PC, dùng trình duyệt) sang Cách 1
(chạy mây, dùng token) chỉ cần thay "đầu lấy data", phần này giữ nguyên.
"""
import os
import sys
import csv
import json
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---- Cấu hình Grafana (lấy từ request thật của dashboard) ------------------
GRAFANA_BASE = "https://grafana.selless.com"
QUERY_URL = f"{GRAFANA_BASE}/api/ds/query?ds_type=grafana-postgresql-datasource"
DASHBOARD_URL = (
    f"{GRAFANA_BASE}/d/zvSN7-x4z/facebook-ads-manager-v2-5"
    "?orgId=1"
)
DATASOURCE_UID = "0YhUzD17k"
DATASOURCE_ID = 41
DASHBOARD_UID = "zvSN7-x4z"
ORG_ID = "1"

VN_TZ = timezone(timedelta(hours=7))  # chỉ dùng để in log cho dễ đọc

# Múi giờ của DỮ LIỆU (ads chạy giờ US) — mốc "một ngày" cắt theo giờ này.
# Dashboard Grafana đang đặt America/Anchorage. zoneinfo tự xử lý hè/đông.
# Có thể đổi bằng biến môi trường DATA_TZ nếu sau này dashboard đổi múi giờ.
DATA_TZ = ZoneInfo(os.environ.get("DATA_TZ", "America/Anchorage"))

HERE = os.path.dirname(os.path.abspath(__file__))
SQL_PATH = os.path.join(HERE, "query.sql")
DATA_DIR = os.path.join(HERE, "..", "data")
INTRADAY_DIR = os.path.join(DATA_DIR, "intraday")
HISTORY_DIR = os.path.join(DATA_DIR, "history")

# Các cột BỎ ĐI cho nhẹ file (sửa danh sách này nếu sau cần thêm/bớt).
DROP_COLUMNS = {
    "str_time_report", "updated", "daily_budget",
    "ad_status", "adset_status", "campaign_status",
    "str_link_clicks", "str_content_view", "str_add_to_cart",
    "str_initial_checkout", "str_purchase", "str_impressions",
    "fb_content_view", "str_fb_content_view",
    "fb_add_to_cart", "str_fb_add_to_cart",
    "fb_initial_checkout", "str_fb_initial_checkout",
    "fb_checkout", "str_fb_checkout",
    "fb_purchase", "str_fb_purchase",
    "access", "str_access", "access_error",
    "initcheckout_error", "checkout_error", "abandon_error",
    "cp_days", "adset_days", "ad_days",
    "ad_id", "adset_id", "campaign_id",
    "quality_ranking", "engagement_rate_ranking", "conversion_rate_ranking",
    "fb_page_id",
}


def drop_columns(header, rows):
    """Bỏ các cột trong DROP_COLUMNS, giữ nguyên thứ tự các cột còn lại."""
    keep_idx = [i for i, name in enumerate(header) if name not in DROP_COLUMNS]
    new_header = [header[i] for i in keep_idx]
    new_rows = [[r[i] for i in keep_idx] for r in rows]
    return new_header, new_rows


def run_type() -> str:
    return os.environ.get("RUN_TYPE", "intraday").strip().lower()  # intraday | final


def query_headers() -> dict:
    """Header chung cho request /api/ds/query (KHÔNG gồm cookie/token)."""
    return {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "x-datasource-uid": DATASOURCE_UID,
        "x-dashboard-uid": DASHBOARD_UID,
        "x-grafana-org-id": ORG_ID,
        "x-plugin-id": "grafana-postgresql-datasource",
    }


def remote_auth() -> str:
    """Che do lay data KHONG dung browser, doc tu env.

    -> 'token'  neu co GRAFANA_TOKEN (Cach 1 — Service Account).
    -> 'cookie' neu co GRAFANA_COOKIE (browser-less — chuoi cookie phien dang nhap).
    -> ''       neu khong co gi (=> PC dung trinh duyet da dang nhap).
    """
    if os.environ.get("GRAFANA_TOKEN", "").strip():
        return "token"
    if os.environ.get("GRAFANA_COOKIE", "").strip():
        return "cookie"
    return ""


def mode_label(kind: str) -> str:
    """Nhãn chế độ để in log, theo kết quả remote_auth()."""
    return {"token": "TOKEN (mây)", "cookie": "COOKIE (browser-less)"}.get(kind, "BROWSER (PC)")


def requests_post(body: dict, extra_headers: dict | None = None) -> dict:
    """Goi POST /api/ds/query bang requests (KHONG can browser).

    Auth tu env: GRAFANA_TOKEN -> Bearer; hoac GRAFANA_COOKIE -> Cookie header.
    extra_headers: them/ghi de header (vd {'x-panel-id': '57'} cho query theo gio).
    Tra ve payload JSON da parse. Thoat voi thong bao giong fetch_via_* cu khi loi.

    Dung chung cho CACH 1 (token, may) va che do COOKIE (browser-less: GitHub Actions,
    Cloudflare, dien thoai cu...). PC khong set 2 bien nay -> van di duong trinh duyet.
    """
    import time
    import requests
    token = os.environ.get("GRAFANA_TOKEN", "").strip()
    cookie = os.environ.get("GRAFANA_COOKIE", "").strip()
    headers = query_headers()
    if extra_headers:
        headers.update(extra_headers)
    if token:
        headers["authorization"] = f"Bearer {token}"
    elif cookie:
        headers["cookie"] = cookie
        headers["referer"] = DASHBOARD_URL
        headers["origin"] = GRAFANA_BASE
    else:
        sys.exit("Khong co GRAFANA_TOKEN/GRAFANA_COOKIE (va khong o che do browser).")

    # Retry loi TAM THOI: read-replica Postgres huy query ("canceling statement due to
    # conflict with recovery", thuong HTTP 400/500) hoac loi mang. 401/403 = auth ->
    # thoat ngay (retry vo ich). Backoff 3s/6s/9s.
    TRANSIENT = ("conflict with recovery", "canceling statement")
    last = ""
    for attempt in range(4):
        try:
            resp = requests.post(QUERY_URL, headers=headers, data=json.dumps(body), timeout=60)
        except requests.RequestException as e:
            last = f"loi mang: {e}"
        else:
            if resp.status_code in (401, 403):
                sys.exit(f"LOI {resp.status_code}: token/cookie khong hop le hoac het han.")
            transient = any(t in resp.text for t in TRANSIENT)
            if resp.status_code == 200 and not transient:
                return resp.json()
            last = f"HTTP {resp.status_code}: {resp.text[:200]}"
        if attempt < 3:
            time.sleep(3 * (attempt + 1))
    sys.exit(f"LOI sau 4 lan thu (loi tam thoi DB/mang): {last}")


def time_window(now: datetime) -> dict:
    """Tính khoảng thời gian + nhãn ngày, CẮT THEO MÚI GIỜ DỮ LIỆU (DATA_TZ).

    Mốc "một ngày" theo giờ US (Anchorage), khớp với link now-1d/d của dashboard:
      - final (16h)   : TRỌN NGÀY HÔM QUA (giờ US). Nhãn file = ngày hôm qua (giờ US).
      - intraday (11h): từ 00:00 HÔM NAY (giờ US) tới bây giờ. Nhãn file = hôm nay (giờ US).
    timestamp() luôn ra epoch chuẩn nên from/to gửi Grafana là tuyệt đối, đúng thời điểm.
    """
    now_d = now.astimezone(DATA_TZ)
    today_start = now_d.replace(hour=0, minute=0, second=0, microsecond=0)
    if run_type() == "final":
        y_start = today_start - timedelta(days=1)            # hôm qua 00:00 (giờ US)
        y_end = today_start - timedelta(milliseconds=1)      # hôm qua 23:59:59.999 (giờ US)
        return {
            "from_ms": int(y_start.timestamp() * 1000),
            "to_ms": int(y_end.timestamp() * 1000),
            "label": f"{y_start:%Y-%m-%d}",
        }
    return {
        "from_ms": int(today_start.timestamp() * 1000),
        "to_ms": int(now_d.timestamp() * 1000),
        "label": f"{today_start:%Y-%m-%d}",
    }


def day_window(d) -> dict:
    """Khoảng + nhãn cho TRỌN MỘT NGÀY (giờ Anchorage) của date `d`. Dùng cho backfill."""
    start = datetime(d.year, d.month, d.day, tzinfo=DATA_TZ)
    end = start + timedelta(days=1) - timedelta(milliseconds=1)
    return {
        "from_ms": int(start.timestamp() * 1000),
        "to_ms": int(end.timestamp() * 1000),
        "label": f"{d:%Y-%m-%d}",
    }


def make_query_body(raw_sql: str, from_ms: int, to_ms: int,
                    interval_ms: int = 300000, max_data_points: int = 368) -> dict:
    """Khung body JSON chung cho MỌI query /api/ds/query (gộp 1 chỗ).

    Chỉ rawSql + khoảng thời gian thay đổi giữa các query; intervalMs/maxDataPoints
    là gợi ý cho datasource (raw SQL dùng from/to tuyệt đối nên không ảnh hưởng kết quả).
    Mọi core_*/snapshot gọi hàm này thay vì tự dựng dict -> sửa schema 1 nơi.
    """
    return {
        "queries": [{
            "refId": "A",
            "datasource": {"type": "grafana-postgresql-datasource", "uid": DATASOURCE_UID},
            "rawSql": raw_sql,
            "format": "table",
            "datasourceId": DATASOURCE_ID,
            "intervalMs": interval_ms,
            "maxDataPoints": max_data_points,
        }],
        "from": str(from_ms),
        "to": str(to_ms),
    }


def make_body(from_ms: int, to_ms: int) -> dict:
    """Tạo body JSON gửi tới Grafana cho khoảng thời gian (epoch ms) cho trước."""
    with open(SQL_PATH, "r", encoding="utf-8") as f:
        raw_sql = f.read()
    return make_query_body(raw_sql, from_ms, to_ms)


def build_body(now_vn: datetime) -> dict:
    """Tạo body JSON theo RUN_TYPE (intraday/final)."""
    win = time_window(now_vn)
    return make_body(win["from_ms"], win["to_ms"])


def browser_profile_dir() -> str:
    """Thư mục profile Chromium đã đăng nhập (đổi được qua BROWSER_PROFILE_DIR)."""
    return os.environ.get("BROWSER_PROFILE_DIR", os.path.expanduser("~/.ca-grafana-profile"))


@contextmanager
def browser_session():
    """CÁCH 2 (chạy PC): mở trình duyệt đã đăng nhập Google, yield hàm post(body, headers).

    Mở context MỘT lần rồi gọi post nhiều lần (vd hourly lặp qua nhiều SP) — tránh
    khởi động lại Chromium mỗi query. Mở dashboard để làm tươi phiên (Google SSO cấp
    lại grafana_session nếu phiên Google còn hạn); gọi API trong context nên tự kèm cookie.

    ⚠️ page.goto dashboard sẽ làm Grafana XOAY grafana_session — chỉ dùng đường này trên
    PC (Cách 2). Production (GitHub Actions) đi core.requests_post (cookie/token, KHÔNG xoay).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Chưa cài Playwright. Chạy: pip install playwright && playwright install chromium")

    profile_dir = browser_profile_dir()
    if not os.path.exists(profile_dir):
        sys.exit("Chưa đăng nhập lần nào. Chạy trước:  python scripts/login.py")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(profile_dir, headless=True)
        try:
            page = ctx.new_page()
            page.goto(DASHBOARD_URL, wait_until="domcontentloaded", timeout=60000)
            if "/login" in page.url or "accounts.google.com" in page.url:
                sys.exit("Phiên đăng nhập đã hết hạn. Chạy lại:  python scripts/login.py")

            def post(body: dict, headers: dict | None = None) -> dict:
                resp = ctx.request.post(
                    QUERY_URL, data=json.dumps(body),
                    headers=headers or query_headers(), timeout=60000,
                )
                if resp.status in (401, 403):
                    sys.exit("Phiên hết hạn (401/403). Chạy lại:  python scripts/login.py")
                if resp.status != 200:
                    sys.exit(f"LỖI HTTP {resp.status}: {resp.text()[:400]}")
                return json.loads(resp.text())

            yield post
        finally:
            ctx.close()


def parse_frames(payload: dict):
    """Phản hồi Grafana (frames) -> (header: list, rows: list[list])."""
    try:
        frames = payload["results"]["A"]["frames"]
    except (KeyError, TypeError):
        sys.exit(f"LỖI: cấu trúc phản hồi lạ: {json.dumps(payload)[:400]}")
    if not frames:
        return [], []
    frame = frames[0]
    header = [fld["name"] for fld in frame["schema"]["fields"]]
    columns = frame["data"]["values"]  # cột: columns[i] = list giá trị cột i
    n = len(columns[0]) if columns else 0
    rows = [[columns[c][r] for c in range(len(columns))] for r in range(n)]
    return header, rows


def write_history_csv(day: str, header, rows):
    """Cắt cột rồi ghi data/history/<day>.csv. Dùng cho backfill."""
    header, rows = drop_columns(header, rows)
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = os.path.join(HISTORY_DIR, f"{day}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if header:
            writer.writerow(header)
        writer.writerows(rows)
    return len(rows)


def save_csv(header, rows, day: str):
    """Lưu CSV vào intraday/ hoặc history/ theo RUN_TYPE; final thì xóa intraday cùng ngày.

    `day` là nhãn ngày của DỮ LIỆU (lấy từ time_window): final = hôm qua, intraday = hôm nay.
    """
    header, rows = drop_columns(header, rows)  # co bớt cột cho nhẹ

    is_final = run_type() == "final"
    target_dir = HISTORY_DIR if is_final else INTRADAY_DIR
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, f"{day}.csv")

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if header:
            writer.writerow(header)
        writer.writerows(rows)

    label = "CHUẨN (history)" if is_final else "trong ngày (intraday)"
    print(f"Đã lưu bản {label}: data/{'history' if is_final else 'intraday'}/{day}.csv "
          f"— {len(rows)} dòng")

    if is_final:
        # Bản intraday của CÙNG NGÀY dữ liệu (ghi lúc 11h hôm qua) giờ không cần nữa
        intraday_path = os.path.join(INTRADAY_DIR, f"{day}.csv")
        if os.path.exists(intraday_path):
            os.remove(intraday_path)
            print(f"Đã xóa bản intraday: data/intraday/{day}.csv")
