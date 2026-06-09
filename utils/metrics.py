"""Tính & định dạng các metrics FB cho 1 nhóm dòng (đã lọc sẵn theo SP/ngày).

Công thức (gộp SỐ THÔ rồi mới tính tỉ lệ — đúng trọng số):
  REV = total_re (từ TPN); nếu không có TPN → transaction_revenue (FB)
  ME  = Σspent
  ROAS= REV/ME
  PO fb = Σpurchase (FB)
  %PC = total_pc/total_re*100  (TPN)
  PO n/a = total_po(TPN) - PO fb
  AOV = REV / total_po(TPN)  (nếu có TPN, không thì REV/PO fb)
  CPM=ME/impr*1000  CTR=clicks/impr  CPC=ME/clicks
  View/click=views/clicks  CPV=ME/views  CR1=ico/views  Cost CO=ME/ico
  CR2=PO fb/ico  CR=PO fb/views  CPP=ME/PO fb
  CBH=(0.90-%PC)*REV-ME   %CBH=CBH/REV*100
"""
import math
import pandas as pd

# Thứ tự dòng hiển thị — bảng chính (có TPN)
METRIC_ORDER = [
    "REV", "ME", "ROAS",
    "PO fb", "PO n/a", "%PC", "AOV",
    "CPM", "CTR", "CPC", "View/click",
    "CPV", "CR1", "Cost CO", "CR2", "CR", "CPP",
    "CBH", "%CBH",
]

# Thứ tự dòng cho bảng Strategy/Ad (không có TPN, giữ nguyên như cũ)
METRIC_ORDER_STRAT = [
    "REV", "ME", "PO", "AOV", "ROAS",
    "CPM", "CTR", "CPC", "View/click",
    "CPV", "CR1", "Cost CO", "CR2", "CR", "CPP",
    "CBH", "%CBH",
]


def _num(df, col):
    if col not in df.columns:
        return 0.0
    return pd.to_numeric(df[col], errors="coerce").fillna(0).sum()


def _div(n, d):
    """Chia an toàn: mẫu = 0 -> None (hiển thị trống)."""
    return (n / d) if d else None


def compute(df: pd.DataFrame, pc_fraction: float,
            tpn_re=None, tpn_pc=None, tpn_po=None) -> dict:
    """
    df          : các dòng FB ad (đã lọc theo SP & ngày).
    pc_fraction : %PC dạng thập phân, tính từ TPN range-average.
    tpn_re/pc/po: giá trị TPN cho ngày/range tương ứng (None nếu chưa có data TPN).
    """
    # ---- Số thô từ FB ads ----
    me     = _num(df, "spent")
    po_fb  = _num(df, "purchase")
    clicks = _num(df, "link_clicks")
    views  = _num(df, "content_view")
    impr   = _num(df, "impressions")
    ico    = _num(df, "initial_checkout")

    # ---- Số từ TPN (ưu tiên TPN; fallback về FB nếu chưa có) ----
    rev    = tpn_re if tpn_re is not None else _num(df, "transaction_revenue")
    po_tot = tpn_po if tpn_po is not None else po_fb   # dùng cho AOV
    po_na  = (tpn_po - po_fb) if tpn_po is not None else None
    pct_pc = (tpn_pc / tpn_re * 100) if (tpn_pc is not None and tpn_re) else None

    # ---- CBH dùng REV từ TPN ----
    cbh = (0.90 - pc_fraction) * rev - me
    if rev:
        pct_cbh = cbh / rev * 100
    else:
        pct_cbh = math.inf if cbh > 0 else (-math.inf if cbh < 0 else None)

    return {
        "REV": rev, "ME": me,
        "ROAS": _div(rev, me),
        "PO": po_fb,        # alias dùng cho bảng Strategy/Ad
        "PO fb": po_fb,
        "%PC": pct_pc,
        "PO n/a": po_na,
        "AOV": _div(rev, po_tot),
        "CPM": (_div(me, impr) * 1000) if impr else None,
        "CTR": _div(clicks, impr),
        "CPC": _div(me, clicks),
        "View/click": _div(views, clicks),
        "CPV": _div(me, views),
        "CR1": _div(ico, views),
        "Cost CO": _div(me, ico),
        "CR2": _div(po_fb, ico),
        "CR": _div(po_fb, views),
        "CPP": _div(me, po_fb),
        "CBH": cbh, "%CBH": pct_cbh,
    }


# ---- Định dạng theo đúng bảng (đơn vị + số lẻ) ----------------------------
def _money(v, dp):
    if v is None:
        return ""
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 10_000:                       # từ $10.00K trở lên -> rút gọn dạng K
        return f"{sign}${a / 1000:,.2f}K"
    return f"{sign}${a:,.{dp}f}"


def _pct(frac, dp):
    """frac là tỉ lệ thập phân (0.032 -> 3.2%)."""
    if frac is None:
        return ""
    return f"{frac * 100:.{dp}f}%"


def fmt(metric: str, v) -> str:
    if metric in ("REV", "ME", "CBH"):
        return _money(v, 0)
    if metric in ("PO", "PO fb", "PO n/a"):
        return "" if v is None else f"{int(v):,}"
    if metric == "%PC":
        return "" if v is None else f"{v:.1f}%"
    if metric == "AOV":
        return _money(v, 1)
    if metric == "ROAS":
        return "" if v is None else f"{v:.2f}"
    if metric == "CPM":
        return _money(v, 1)
    if metric == "CTR":
        return _pct(v, 1)
    if metric == "CPC":
        return _money(v, 1)
    if metric == "View/click":
        return _pct(v, 0)
    if metric == "CPV":
        return _money(v, 2)
    if metric == "CR1":
        return _pct(v, 1)
    if metric == "Cost CO":
        return _money(v, 1)
    if metric == "CR2":
        return _pct(v, 1)
    if metric == "CR":
        return _pct(v, 1)
    if metric == "CPP":
        return _money(v, 1)
    if metric == "%CBH":
        if v is None:
            return ""
        if v == math.inf:
            return "oo%"
        if v == -math.inf:
            return "-oo%"
        return f"{v:.0f}%"
    return "" if v is None else str(v)


# ---- Tô đậm / mũi tên-delta cho cột ngày cuối -----------------------------
BOLD_ROWS = {"ROAS", "AOV", "CPV", "CR1", "CR2", "CPP", "CBH", "%CBH"}
LOWER_BETTER  = {"CPM", "CPC", "CPV", "CPP"}
HIGHER_BETTER = {"CTR", "View/click", "CR1", "CR2"}
DELTA_METRICS = LOWER_BETTER | HIGHER_BETTER | {"ME"}
DELTA_THRESHOLD = 0.10


def delta_decor(metric: str, last_v, prev_v):
    """Trang trí ô ngày cuối so với ngày liền trước (|Δ|>=10%)."""
    if metric not in DELTA_METRICS:
        return None
    if last_v is None or prev_v in (None, 0):
        return None
    delta = (last_v - prev_v) / abs(prev_v)
    if abs(delta) < DELTA_THRESHOLD:
        return None
    increased = last_v > prev_v
    arrow = "↑" if increased else "↓"
    if metric == "ME":
        return {"me": True, "arrow": arrow, "delta": delta}
    better = (increased and metric in HIGHER_BETTER) or \
             (not increased and metric in LOWER_BETTER)
    return {"me": False, "arrow": arrow, "better": better, "delta": delta}


def cbh_color(pct_cbh) -> str:
    """Màu nền cho 2 dòng CBH/%CBH theo %CBH: <0 đỏ, 0-<8 vàng, >=8 xanh."""
    if pct_cbh is None:
        return ""
    if pct_cbh == -math.inf or pct_cbh < 0:
        return "background-color: #f4c7c3"
    if pct_cbh == math.inf or pct_cbh >= 8:
        return "background-color: #b7e1cd"
    return "background-color: #fce8b2"
