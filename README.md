# CAMS — CA All-Marketer Snapshot

Snapshot metrics **tất cả marketer Crossian** mỗi giờ từ Grafana → lưu **DIM + FACT** (CSV theo
ngày) → đẩy GitHub → hiển thị bằng **Streamlit** (1 trang *Metrics by Hour*).

> Nền tái sử dụng từ dự án **CA**. Lý do tồn tại: budget/status campaign **không có lịch sử**
> trong DB Selless → cách duy nhất dựng timeline là tự snapshot mỗi giờ. CAMS mở rộng CA từ
> 1 marketer lên **toàn bộ marketer Crossian** (`publisher_email LIKE '%@crossian.com'`).

## Kiến trúc

```
PC nhà (Task Scheduler, 24x/ngày @ HH:55 giờ VN + chạy bù khi logon)
  ├─ git pull --rebase --autostash
  ├─ scripts/refresh_session.py     (gia hạn phiên Grafana qua cookie Google, headless)
  ├─ scripts/cams_snapshot.py       (crawl all-marketer Crossian, campaign-level)
  │     ├─ UPSERT  data/campaigns.csv          ← DIM  (campaign_id, marketer, product, name, first/last_seen)
  │     └─ APPEND  data/facts/<YYYY-MM-DD>.csv ← FACT (hh, campaign_id, status, budget, spent, ...rev)
  └─ git add data/ + commit + push
GitHub (private)  →  Streamlit Cloud đọc DIM+FACT  →  app.py (Metrics by Hour)
```

- **hh** = giờ Anchorage (00–23) lúc chụp; file FACT = ngày Anchorage (data ads chạy giờ US).
- Chụp tại phút **:55** → app hiển thị **khung = giờ kế tiếp** (chụp 14:55 VN → khung 15:00
  = chốt cả ngày, nằm cuối bảng; bảng chạy 16:00 → 15:00).
- FACT metrics = **cộng dồn day-to-date**; app tự `diff` 2 giờ liên tiếp ra số theo-giờ.
- budget/status = **point-in-time** (carry-forward, ô kế thừa có dấu `*`), KHÔNG diff.

## File chính
| File | Vai trò |
|---|---|
| `scripts/core.py` | Lõi Grafana (auth token/cookie/browser, query, parse) — copy từ CA |
| `scripts/cams_query_snapshot.sql` | Query snapshot all-marketer Crossian (1 dòng/campaign) |
| `scripts/cams_snapshot.py` | Crawler hằng giờ → ghi DIM + FACT |
| `scripts/run_snapshot.ps1` | Runner PC: pull → refresh → snapshot → commit/push |
| `scripts/setup_snapshot_schedule.ps1` | Đăng ký Task Scheduler "CAMS Snapshot" 24x @ HH:55 + WakeToRun + catch-up logon |
| `utils/transform.py` | Tái dựng per-hour, gộp giờ, Total Budget, hàng campaign (thuần pandas) |
| `utils/data_loader.py` | Loader DIM+FACT cho Streamlit (`@st.cache_data`) |
| `utils/metrics.py` | Công thức + format metrics — copy từ CA |
| `app.py` | Dashboard 1 trang: Marketer → Sản phẩm → Range |
| `scripts/selftest.py` | Unit-test logic transform (không cần Grafana) |
| `scripts/_gen_sample.py` | Sinh data giả để test UI (KHÔNG dùng production) |

## Trang Metrics by Hour
- Dropdown **Marketer** (ưu tiên 1) → **Sản phẩm** (lọc theo marketer) → **Data Range**.
- Marketer/Sản phẩm có ME (spent>0) trong 2 ngày gần nhất: 🟢 + đẩy lên đầu, còn lại alphabet.
- **Bảng gộp giờ**: thêm cột **Total Budget** = TB/ngày tổng daily_budget campaign ACTIVE tại giờ đó.
- **Màu**: ROAS xanh nhất tại **3**, CR xanh nhất tại **7%**, CPP/CPV thấp=xanh. CPM/CPC không tô.
- **Bảng campaign**: hàng **Σ Total** (chọn khung 16:00→15:00 + All; Status/Budget as-of khung, Metrics = cộng dồn tới khung đó) + 24 khung; ô **Budget đổi màu chữ** (xanh=tăng/đỏ=giảm vs giờ trước).

## Setup trên PC nhà (checklist)
> Profile Chromium `~/.ca-grafana-profile` (cookie đăng nhập) **không copy được giữa máy** (mã hóa
> DPAPI). PC phải login Grafana lại từ đầu.

```powershell
git clone <repo CAMS> ; cd CAMS
pip install -r scripts/requirements-downloader.txt   # requests, playwright, tzdata
python -m playwright install chromium
python scripts/login.py            # mở browser -> đăng nhập Google -> tự lưu khi thấy dashboard
python scripts/cams_snapshot.py    # chạy thử 1 nhịp -> data/campaigns.csv + data/facts/<hôm nay>.csv
powershell -ExecutionPolicy Bypass -File scripts\setup_snapshot_schedule.ps1   # 24x @ HH:55
```
Gỡ task: `Unregister-ScheduledTask -TaskName 'CAMS Snapshot' -Confirm:$false`

## Streamlit Cloud
[share.streamlit.io](https://share.streamlit.io) → New app → repo CAMS → main file `app.py`.
`requirements.txt` đã đủ (streamlit, pandas, altair, requests). Mỗi lần PC push data → Cloud tự reboot.

## Lưu ý vận hành
- **Phiên Grafana**: acc Viewer không tạo được token → dùng browser profile + `refresh_session.py`
  (cookie Google sống tới ~2027 tự mint lại `grafana_session`). Nếu hết hạn hẳn → chạy lại `login.py`.
- **Repo phình** (~3MB FACT/ngày, ~1GB/năm) → prune file FACT cũ >6–12 tháng định kỳ.
- Query all-marketer nặng hơn (~1.2K campaign/giờ) → `core.requests_post` đã retry lỗi DB tạm thời.
- Đừng đặt trùng tên task với CA ("CAMS Snapshot" ≠ "CA Snapshot").
