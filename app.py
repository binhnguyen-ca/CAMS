"""CAMS — All-Marketer Snapshot dashboard (Streamlit Cloud). 1 trang: Metrics by Hour.

Data do scripts/cams_snapshot.py snapshot moi gio (tat ca marketer Crossian) -> DIM+FACT
-> push GitHub. App chi doc DIM+FACT da commit; moi lan data moi push, Streamlit Cloud tu
reboot + cap nhat (cache loader tu xoa).

Uu tien chon: Marketer -> San pham -> Data Range.
"""
from datetime import timedelta

import pandas as pd
import streamlit as st

from utils.data_loader import load_dim, load_facts
from utils import transform as T
from utils import metrics as M

st.set_page_config(page_title="CAMS — Metrics by Hour", layout="wide")

# ---- Bo cuc cot --------------------------------------------------------------
HOUR_COL_ORDER = [
    "Giờ", "Total Budget", "REV", "ME", "PO", "CPP", "AOV", "ROAS",
    "CPM", "CTR", "CPC", "View/click", "CPV", "CR1", "Cost CO", "CR2", "CR",
]
HOUR_BOLD_COLS = {"Giờ", "ROAS", "CPP", "CPV", "CR1", "CR2"}
CAMP_HOUR_COL_ORDER = ["Giờ", "Status", "Budget"] + \
    [c for c in HOUR_COL_ORDER if c not in ("Giờ", "Total Budget")]
HOUR_SEP_AFTER = {"Giờ", "Total Budget", "ROAS", "CPV"}
CAMP_SEP_AFTER = {"Status", "Budget", "ROAS", "CPV"}

# ---- Map mau (R8/R9/R10) -----------------------------------------------------
# Cao=tot, XANH NHAT (clamp) tai: ROAS=3, CR=7% (CR luu dang phan so -> 0.07).
_HEAT_HI_CLAMP = {"ROAS": 3.0, "CR": 0.07}
# Thap=tot (data-relative min->max): CPP, CPV. CPM/CPC KHONG to mau nua.
_HEAT_LO = {"CPP", "CPV"}
_HEAT_COLS = set(_HEAT_HI_CLAMP) | _HEAT_LO

_RED = (244, 199, 195); _YEL = (252, 232, 178); _GRN = (183, 225, 205)


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _heat_bg(t):
    t = max(0.0, min(1.0, t))
    c = _lerp(_RED, _YEL, t * 2) if t <= 0.5 else _lerp(_YEL, _GRN, (t - 0.5) * 2)
    return f"background-color:rgb({c[0]},{c[1]},{c[2]});"


def _heat_for_col(rows, col) -> dict:
    """Tra {i: css-bg} cho cot `col`.
    - HI clamp (ROAS/CR): t = v / clamp (cap 1) -> tuyet doi, xanh nhat tai clamp.
    - LO (CPP/CPV): data-relative min->max, thap=xanh."""
    if col in _HEAT_HI_CLAMP:
        clamp = _HEAT_HI_CLAMP[col]
        out = {}
        for i, r in enumerate(rows):
            v = r.get(col)
            if v is None:
                continue
            out[i] = _heat_bg(v / clamp if clamp else 0.0)
        return out
    if col in _HEAT_LO:
        vals = [r.get(col) for r in rows if r.get(col) is not None]
        if len(vals) < 2 or max(vals) == min(vals):
            return {}
        lo, hi = min(vals), max(vals)
        out = {}
        for i, r in enumerate(rows):
            v = r.get(col)
            if v is None:
                continue
            out[i] = _heat_bg(1 - (v - lo) / (hi - lo))
        return out
    return {}


def _build_heat(rows) -> dict:
    return {c: _heat_for_col(rows, c) for c in _HEAT_COLS}


def _fmt_money0(v) -> str:
    return "" if v is None else (f"${v:,.0f}" if v else "$0")


_TABLE_CSS = """
<style>
.ca-hr-wrap{max-height:75vh;overflow:auto;border:1px solid #e6e6e6;border-radius:6px}
table.ca-hr{border-collapse:collapse;font-size:13px;line-height:1.15;width:100%;table-layout:auto}
table.ca-hr td,table.ca-hr th{border:1px solid #ececec;padding:2px 8px;white-space:nowrap}
table.ca-hr th{background:#f6f8fa;position:sticky;top:0;z-index:2}
</style>
"""


def build_hour_table_html(rows) -> str:
    """Bang gop theo gio (range hoac 1 ngay). rows: dict co Giờ, _ah, Total Budget, metrics."""
    sep = "2px solid #b9b9b9"
    heat = _build_heat(rows)

    def cell_style(c, i, bold):
        s = "text-align:left;" if c == "Giờ" else "text-align:center;"
        if c in HOUR_SEP_AFTER:
            s += f"border-right:{sep};"
        if bold:
            s += "font-weight:bold;"
        if c in heat and i in heat[c]:
            s += heat[c][i]
        return s

    head = "".join(
        f"<th style='{'text-align:left;' if c == 'Giờ' else 'text-align:center;'}"
        f"{(f'border-right:{sep};' if c in HOUR_SEP_AFTER else '')}font-weight:bold;'>{c}</th>"
        for c in HOUR_COL_ORDER
    )
    body = ""
    for i, r in enumerate(rows):
        cells = ""
        for c in HOUR_COL_ORDER:
            if c == "Giờ":
                v = r.get("Giờ", "")
            elif c == "Total Budget":
                v = _fmt_money0(r.get("Total Budget"))
            else:
                v = M.fmt(c, r.get(c))
            cells += f"<td style='{cell_style(c, i, c in HOUR_BOLD_COLS)}'>{v}</td>"
        body += f"<tr>{cells}</tr>"
    return f'{_TABLE_CSS}<div class="ca-hr-wrap"><table class="ca-hr">' \
           f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def _status_style(s):
    if s == "ACTIVE":
        return "background-color:rgb(183,225,205);color:#13703f;font-weight:bold;"
    if s == "PAUSE":
        return "background-color:#efefef;color:#aaa;"
    return "color:#ccc;"


def build_campaign_status_table_html(rows) -> str:
    """Bang campaign theo gio: Status + Budget + metrics. rows[0] = hang Total (R13).
    R12: mau CHU o Budget (xanh=tang / do=giam vs gio truoc). Heat metrics nhu bang gio."""
    sep = "2px solid #b9b9b9"
    heat = _build_heat(rows)

    def cell_style(c, i, bold):
        s = "text-align:left;" if c == "Giờ" else "text-align:center;"
        if c in CAMP_SEP_AFTER:
            s += f"border-right:{sep};"
        if bold:
            s += "font-weight:bold;"
        if c in heat and i in heat[c]:
            s += heat[c][i]
        return s

    head = "".join(
        f"<th style='text-align:{'left' if c == 'Giờ' else 'center'};font-weight:bold;"
        f"{(f'border-right:{sep};') if c in CAMP_SEP_AFTER else ''}'>{c}</th>"
        for c in CAMP_HOUR_COL_ORDER
    )
    body = ""
    for i, r in enumerate(rows):
        is_total = (i == 0)
        tr_style = "background:#fbfbe7;font-weight:bold;" if is_total else ""
        cells = ""
        for c in CAMP_HOUR_COL_ORDER:
            if c == "Giờ":
                v = r.get("Giờ", "")
                cells += f"<td style='{cell_style(c, i, True)}'>{v}</td>"
            elif c == "Status":
                v = r.get("Status") or ""
                cells += f"<td style='text-align:center;{_status_style(v)}border-right:{sep};'>{v}</td>"
            elif c == "Budget":
                b = r.get("Budget")
                v = _fmt_money0(b)
                d = r.get("budget_dir", 0)
                col = "color:#137333;font-weight:bold;" if d > 0 else \
                      ("color:#c5221f;font-weight:bold;" if d < 0 else "")
                cells += f"<td style='text-align:center;border-right:{sep};{col}'>{v}</td>"
            else:
                v = M.fmt(c, r.get(c))
                cells += f"<td style='{cell_style(c, i, c in HOUR_BOLD_COLS)}'>{v}</td>"
        body += f"<tr style='{tr_style}'>{cells}</tr>"
    return f'{_TABLE_CSS}<div class="ca-hr-wrap"><table class="ca-hr">' \
           f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


# ===========================================================================
def _date_range_input(avail, key):
    """st.date_input range voi guard clamp-on-rerun. Tra (start, end) hoac None."""
    min_d, max_d = avail[0], avail[-1]
    default_start = max(min_d, max_d - timedelta(days=13))
    cur = st.session_state.get(key)
    if not (isinstance(cur, (tuple, list)) and len(cur) in (1, 2)):
        st.session_state[key] = (default_start, max_d)
    elif len(cur) == 2:
        s = min(max(cur[0], min_d), max_d)
        e = min(max(cur[1], min_d), max_d)
        if (s, e) != (cur[0], cur[1]):
            st.session_state[key] = (s, e)
    rng = st.date_input("Data Range", min_value=min_d, max_value=max_d,
                        key=key, format="DD/MM/YYYY")
    if isinstance(rng, (tuple, list)):
        if len(rng) != 2:
            st.info("Chọn đủ ngày bắt đầu và kết thúc.")
            return None
        return rng[0], rng[1]
    return rng, rng


_GUIDE = """
**CAMS** chụp metrics **mọi marketer Crossian mỗi giờ** (budget/status mà Grafana không lưu lịch sử).
Bạn chỉ cần chọn tên mình — không cần cài gì.

**Cách dùng (theo thứ tự):**
1. **Marketer** → chọn tên bạn (🟢 = có chi tiêu trong 2 ngày gần nhất, đẩy lên đầu).
2. **Sản phẩm** → chỉ hiện SP của bạn (🟢 = có chi 2 ngày gần nhất).
3. **Data Range** → khoảng ngày muốn xem.

**Giờ** hiển thị theo **giờ VN** (quy đổi từ giờ chạy ads của Mỹ) — chạy **15:00 → 14:00 hôm sau** = đúng 1 ngày làm việc.

**3 bảng:**
- **Gộp theo giờ (toàn range):** mỗi giờ trong ngày trung bình ra sao. Cột **Total Budget** = TB/ngày tổng budget các campaign đang ACTIVE ở giờ đó.
- **Soi 1 ngày:** đúng bảng trên nhưng cho 1 ngày bạn chọn.
- **Theo campaign:** từng campaign theo giờ. Hàng **Σ (Total)** ở trên: chọn "tính đến giờ" → Status/Budget tại giờ đó + metrics cộng dồn từ đầu ngày tới giờ đó. Ô **Budget đổi màu chữ**: 🟩 xanh = tăng, 🟥 đỏ = giảm so với giờ trước.

**Đọc màu (nền ô):** càng **xanh càng tốt**. ROAS xanh nhất khi ≥ **3**; CR xanh nhất khi ≥ **7%**; CPP/CPV thì **thấp = xanh**. (CPM/CPC không tô màu.)
"""


def _check_auth() -> bool:
    """Cong mat khau (cho phep deploy PUBLIC app ma data van kin).
    Dat secret `app_password` tren Streamlit Cloud. Neu KHONG dat (local/dev) -> cho qua."""
    try:
        secret = st.secrets.get("app_password")
    except Exception:
        secret = None
    if not secret:
        return True  # khong cau hinh mat khau -> mo (chay local)
    if st.session_state.get("_auth_ok"):
        return True
    st.title("🔒 CAMS")
    pw = st.text_input("Mật khẩu", type="password", key="_pw")
    if pw and pw == secret:
        st.session_state["_auth_ok"] = True
        st.rerun()
    elif pw:
        st.error("Sai mật khẩu.")
    return False


def main():
    if not _check_auth():
        st.stop()
    st.title("🕐 CAMS — Metrics by Hour")
    with st.expander("ℹ️ Cách đọc dashboard (bấm để mở)"):
        st.markdown(_GUIDE)
    dim = load_dim()
    facts_raw = load_facts()
    if dim is None or facts_raw is None:
        st.warning("Chưa có dữ liệu snapshot. Chạy `python scripts/cams_snapshot.py` "
                   "để tạo `data/campaigns.csv` + `data/facts/`.")
        return
    facts = T.dedup_facts(facts_raw)

    # ---- R4/R5: Marketer (uu tien 1) ----
    mk = T.marketers_with_flag(facts, dim)
    if not mk:
        st.warning("DIM rỗng — chưa có marketer.")
        return
    mk_emails = [m for m, _ in mk]
    active_mk = {m for m, a in mk if a}
    if st.session_state.get("m_marketer") not in mk_emails:
        st.session_state["m_marketer"] = mk_emails[0]
    c1, c2 = st.columns(2)
    with c1:
        marketer = st.selectbox(
            "Marketer", mk_emails, key="m_marketer",
            format_func=lambda m: ("🟢 " if m in active_mk else "▫️ ") + T.marketer_label(m),
        )
    # ---- R6: San pham (loc theo marketer) ----
    pf = T.products_with_flag(facts, dim, marketer)
    if not pf:
        st.warning("Marketer này chưa có sản phẩm.")
        return
    prods = [p for p, _ in pf]
    active_pr = {p for p, a in pf if a}
    if st.session_state.get("m_product") not in prods:
        st.session_state["m_product"] = prods[0]
    with c2:
        product = st.selectbox(
            "Sản phẩm", prods, key="m_product",
            format_func=lambda p: ("🟢 " if p in active_pr else "▫️ ") + str(p),
        )

    cids = T.campaign_ids_for(dim, marketer, product)
    fsub_all = facts[facts["campaign_id"].isin(cids)]
    if fsub_all.empty:
        st.warning("Không có data cho marketer + sản phẩm này.")
        return

    # ---- Data Range (uu tien 3) ----
    avail = sorted(fsub_all["_day"].dropna().unique())
    rng = _date_range_input(avail, "m_range")
    if rng is None:
        return
    start_d, end_d = rng
    fsub = fsub_all[(fsub_all["_day"] >= start_d) & (fsub_all["_day"] <= end_d)]
    if fsub.empty:
        st.warning("Range này không có data.")
        return

    # ---- Bang gop theo gio (toan range) + Total Budget (R7) ----
    deltas = T.hourly_delta_rows(fsub)
    rows = T.aggregate_hours(deltas, end_d)
    budget_by_ah = T.total_budget_by_ah(fsub)
    for r in rows:
        r["Total Budget"] = budget_by_ah.get(r["_ah"])
    tot = T._compute_row(deltas) if not deltas.empty else {}
    st.caption(
        f"**{T.marketer_label(marketer)} · {product}** · {start_d:%d/%m/%Y} → {end_d:%d/%m/%Y} · "
        f"giờ VN (quy đổi Anchorage) · ME {M.fmt('ME', tot.get('ME'))} · "
        f"REV {M.fmt('REV', tot.get('REV'))} · ROAS {M.fmt('ROAS', tot.get('ROAS'))} · "
        f"PO {M.fmt('PO', tot.get('PO'))}"
    )
    st.markdown("##### Gộp theo giờ (toàn range)")
    if rows:
        st.markdown(build_hour_table_html(rows), unsafe_allow_html=True)
        st.caption("*Total Budget = TB/ngày tổng daily_budget của các campaign ACTIVE tại giờ đó.*")
    else:
        st.info("Range này không có giờ nào có data.")

    # ---- Soi 1 ngay ----
    st.markdown("---")
    day_opts = [f"{d:%Y-%m-%d}" for d in reversed(avail)]
    if st.session_state.get("m_day") not in day_opts:
        st.session_state["m_day"] = day_opts[0]
    chosen_day = st.selectbox("Soi 1 ngày / chọn ngày cho bảng campaign", day_opts, key="m_day")
    cmp_d = pd.to_datetime(chosen_day).date()
    fday = fsub_all[fsub_all["_day"] == cmp_d]

    dday = T.hourly_delta_rows(fday)
    drows = T.aggregate_hours(dday, cmp_d)
    dbud = T.total_budget_by_ah(fday)
    for r in drows:
        r["Total Budget"] = dbud.get(r["_ah"])
    st.markdown(f"##### Soi 1 ngày — {chosen_day}")
    if drows:
        st.markdown(build_hour_table_html(drows), unsafe_allow_html=True)
    else:
        st.info("Ngày này không có data.")

    # ---- Theo campaign (R12/R13) ----
    st.markdown("---")
    st.markdown(f"##### 🧭 Theo campaign — {chosen_day}")
    if fday.empty:
        st.info("Ngày này không có campaign nào chạy.")
        return
    me_by = fday.groupby("campaign_id")["spent"].max().sort_values(ascending=False)
    camps = [c for c in me_by.index if me_by[c] > 0]
    if not camps:
        st.info("Ngày này không campaign nào có ME.")
        return
    id2name = dict(zip(dim["campaign_id"].astype(str), dim["campaign_name"].astype(str)))
    if st.session_state.get("m_campaign") not in camps:
        st.session_state["m_campaign"] = camps[0]

    cc1, cc2 = st.columns([3, 1])
    with cc1:
        chosen_c = st.selectbox(
            f"Campaign ({len(camps)} có ME, sắp theo ME giảm dần)", camps, key="m_campaign",
            format_func=lambda c: (lambda n: (n[:70] + "…") if len(n) > 70 else n)(id2name.get(c, c)),
        )
    # R13: selector gio cho hang Total
    hour_pairs = [("All", "ALL")] + [(T.vn_label(cmp_d, ah), ah) for ah in range(24)]
    labels = [lbl for lbl, _ in hour_pairs]
    with cc2:
        if st.session_state.get("m_total_hour") not in labels:
            st.session_state["m_total_hour"] = "All"
        sel = st.selectbox("Hàng Total tính đến giờ", labels, key="m_total_hour")
    choice = dict(hour_pairs)[sel]

    fc = fday[fday["campaign_id"] == chosen_c]
    crows = T.campaign_day_rows(fc, cmp_d)
    total_row = T.campaign_total_row(fc, cmp_d, choice)
    total_row["Giờ"] = f"Σ {sel}"
    st.markdown(build_campaign_status_table_html([total_row] + crows), unsafe_allow_html=True)
    st.caption("*Hàng Σ (Total): Status & Budget = snapshot tại giờ đã chọn; Metrics = cộng dồn "
               "15:00 → giờ đó. Budget đổi màu chữ: xanh=tăng, đỏ=giảm so với giờ trước.*")


main()
