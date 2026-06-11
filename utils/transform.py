"""CAMS — bien doi DIM+FACT thanh cac bang cho dashboard (THUAN pandas, KHONG Streamlit).

Tach rieng de unit-test khong can chay Streamlit. FACT luu metrics CONG DON day-to-date
theo (campaign, ngay Anchorage, gio Anchorage hh). Cac ham o day:
  - dedup_facts        : ep kieu so + bo trung (_day,hh,campaign_id) giu ban moi nhat
  - marketers_with_flag: danh sach marketer (nhan rut gon) + co ME 2 ngay gan nhat
  - products_with_flag : san pham cua 1 marketer + co ME 2 ngay gan nhat
  - hourly_delta_rows  : tai dung so THEO-GIO = diff cumulative giua 2 gio lien tiep
  - aggregate_hours    : gop theo gio (toan range) -> list dict metrics + _ah
  - total_budget_by_ah : Total Budget moi gio = TB/ngay cua tong daily_budget camp ACTIVE
  - campaign_day_rows  : 1 campaign/1 ngay -> 24 dong gio (metrics + Status/Budget as-of + huong budget)
  - campaign_total_row : hang Total cua bang campaign (Status/Budget as-of gio chon; metrics = cumulative)
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from . import metrics as M

ANCH_TZ = ZoneInfo("America/Anchorage")
VN_TZ = timezone(timedelta(hours=7))

# Cot metrics CONG DON trong FACT (diff duoc de ra so theo-gio)
CUM_COLS = ["spent", "impressions", "clicks", "views", "checkout", "purchase", "rev"]
# Doi ten sang ten M.compute() mong doi
_RENAME = {"clicks": "link_clicks", "views": "content_view",
           "checkout": "initial_checkout", "rev": "transaction_revenue"}


def marketer_label(email) -> str:
    """publisher_email -> nhan rut gon (phan truoc @). Giu nguyen neu khong co @."""
    s = str(email or "")
    return s.split("@", 1)[0] if "@" in s else s


def to_vn_hour(day, ah) -> int:
    """Gio Anchorage HH24 -> gio VN HH24 (zoneinfo tu xu ly DST)."""
    dt = datetime(day.year, day.month, day.day, int(ah), tzinfo=ANCH_TZ)
    return dt.astimezone(VN_TZ).hour


def vn_label(day, ah) -> str:
    return f"{to_vn_hour(day, ah):02d}:00"


def dedup_facts(facts: pd.DataFrame) -> pd.DataFrame:
    """Ep kieu so cho CUM_COLS + budget; bo trung (_day,hh,campaign_id) giu dong cuoi (moi nhat)."""
    if facts is None or facts.empty:
        return facts
    df = facts.copy()
    df["hh"] = pd.to_numeric(df["hh"], errors="coerce").astype("Int64")
    df["campaign_id"] = df["campaign_id"].astype(str)
    for c in CUM_COLS + ["budget"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df = df.dropna(subset=["hh"])
    df["hh"] = df["hh"].astype(int)
    df = df.drop_duplicates(subset=["_day", "hh", "campaign_id"], keep="last")
    return df


def _recent_days(facts: pd.DataFrame, n: int = 2) -> set:
    days = sorted(facts["_day"].dropna().unique())
    return set(days[-n:])


def marketers_with_flag(facts: pd.DataFrame, dim: pd.DataFrame) -> list[tuple[str, bool]]:
    """List (marketer_email, active_last2) — active = co spent>0 trong 2 ngay gan nhat.
    Sap: active truoc, roi alphabet theo nhan rut gon."""
    if dim is None or dim.empty:
        return []
    marketers = sorted(dim["marketer"].dropna().astype(str).unique())
    active = set()
    if facts is not None and not facts.empty:
        last2 = _recent_days(facts, 2)
        rec = facts[facts["_day"].isin(last2)]
        spent_cid = set(rec.loc[rec["spent"] > 0, "campaign_id"].astype(str))
        d = dim[dim["campaign_id"].astype(str).isin(spent_cid)]
        active = set(d["marketer"].dropna().astype(str))
    return sorted(((m, m in active) for m in marketers),
                  key=lambda x: (not x[1], marketer_label(x[0]).lower()))


def products_with_flag(facts: pd.DataFrame, dim: pd.DataFrame, marketer: str) -> list[tuple[str, bool]]:
    """San pham cua 1 marketer + co ME 2 ngay gan nhat. Sap: active truoc, roi alphabet."""
    if dim is None or dim.empty:
        return []
    dm = dim[dim["marketer"].astype(str) == str(marketer)]
    products = sorted(p for p in dm["product"].dropna().astype(str).unique() if p)
    active = set()
    if facts is not None and not facts.empty:
        last2 = _recent_days(facts, 2)
        cids = set(dm["campaign_id"].astype(str))
        rec = facts[(facts["_day"].isin(last2)) & (facts["campaign_id"].isin(cids)) & (facts["spent"] > 0)]
        cid2prod = dict(zip(dm["campaign_id"].astype(str), dm["product"].astype(str)))
        active = {cid2prod.get(c) for c in rec["campaign_id"].astype(str)}
    return sorted(((p, p in active) for p in products),
                  key=lambda x: (not x[1], x[0].lower()))


def campaign_ids_for(dim: pd.DataFrame, marketer: str, product: str) -> set:
    d = dim[(dim["marketer"].astype(str) == str(marketer)) &
            (dim["product"].astype(str) == str(product))]
    return set(d["campaign_id"].astype(str))


def hourly_delta_rows(facts_subset: pd.DataFrame) -> pd.DataFrame:
    """Tai dung so THEO-GIO: per-hour[H] = cumulative[H] - cumulative[H_truoc] trong cung
    (campaign,_day). Gio dau tien co mat -> per-hour = cumulative. Am -> kep ve 0.
    Tra DataFrame cot: campaign_id,_day,hh + CUM_COLS (gio la GIA TRI THEO-GIO)."""
    if facts_subset is None or facts_subset.empty:
        return pd.DataFrame(columns=["campaign_id", "_day", "hh"] + CUM_COLS)
    g = facts_subset.sort_values(["campaign_id", "_day", "hh"]).copy()
    deltas = g.groupby(["campaign_id", "_day"])[CUM_COLS].diff()
    deltas = deltas.fillna(g[CUM_COLS])          # dong dau moi nhom = cumulative
    deltas = deltas.clip(lower=0)
    out = g[["campaign_id", "_day", "hh"]].copy()
    for c in CUM_COLS:
        out[c] = deltas[c].values
    return out


def _compute_row(df_rows: pd.DataFrame) -> dict:
    """Goi M.compute (khong TPN) tren 1 nhom dong (da la so theo-gio hoac cumulative)."""
    return M.compute(df_rows.rename(columns=_RENAME), 0.0)


def aggregate_hours(delta_rows: pd.DataFrame, ref_day) -> list[dict]:
    """Gop theo gio Anchorage (toan range) -> list dict metrics, kem 'Giờ' (nhan VN) + '_ah'.
    Thu tu = ngay lam viec Anchorage 0..23 -> nhan VN chay 15:00 -> 14:00."""
    if delta_rows is None or delta_rows.empty:
        return []
    rows = []
    for ah in range(24):
        g = delta_rows[delta_rows["hh"] == ah]
        if g.empty:
            continue
        m = _compute_row(g)
        m["_ah"] = ah
        m["Giờ"] = vn_label(ref_day, ah)
        rows.append(m)
    return rows


def _now_anch() -> datetime:
    return datetime.now(ANCH_TZ)


def _is_future(day, ah, now_anch) -> bool:
    return datetime(day.year, day.month, day.day, ah, tzinfo=ANCH_TZ) > now_anch


def _carry_forward_states(fc: pd.DataFrame):
    """fc = FACT cua 1 (campaign,_day), da sort theo hh. Tra (asof, cum_asof, present_hh):
       asof[ah]    = (status, budget) gan nhat <= ah (carry-forward), None neu chua co.
       cum_asof[ah]= dict cumulative metrics gan nhat <= ah.
       present_hh  = set cac hh thuc su co snapshot."""
    present = {int(r["hh"]): r for _, r in fc.iterrows()}
    asof, cum_asof = {}, {}
    last_state, last_cum = None, None
    for ah in range(24):
        if ah in present:
            r = present[ah]
            last_state = (r.get("status"), float(r["budget"]) if pd.notna(r.get("budget")) else None)
            last_cum = {c: float(r[c]) for c in CUM_COLS}
        asof[ah] = last_state
        cum_asof[ah] = last_cum
    return asof, cum_asof, set(present)


def campaign_day_rows(fc: pd.DataFrame, day, now_anch: datetime | None = None) -> list[dict]:
    """1 campaign, 1 ngay -> 24 dong gio (thu tu Anchorage 0..23, nhan VN).
    Moi dong: per-hour metrics (diff) + Status/Budget as-of gio + 'budget_dir' (R12: +1 tang/-1 giam/0)."""
    now_anch = now_anch or _now_anch()
    fc = fc.sort_values("hh")
    asof, _, present = _carry_forward_states(fc)
    deltas = hourly_delta_rows(fc)                 # per-hour cua chinh campaign nay
    by_ah = {int(r["hh"]): r for _, r in deltas.iterrows()}

    rows, prev_budget = [], None
    for ah in range(24):
        future = _is_future(day, ah, now_anch)
        if ah in by_ah:
            m = _compute_row(pd.DataFrame([by_ah[ah]]))
        else:
            m = {}
        m["Giờ"] = vn_label(day, ah)
        rs = None if future else asof[ah]
        if rs is not None:
            status, budget = rs
            m["Status"] = "ACTIVE" if status == "ACTIVE" else "PAUSE"
            m["Budget"] = budget
            # Gio bi MISS snapshot: Status/Budget la ke thua (carry-forward) tu gio
            # gan nhat truoc do, KHONG phai gia tri thuc ghi tai gio nay -> app danh dau *
            m["_carried"] = ah not in present
            # R12: huong thay doi budget so voi gio (co budget) truoc
            if budget is not None and prev_budget is not None:
                m["budget_dir"] = 1 if budget > prev_budget else (-1 if budget < prev_budget else 0)
            else:
                m["budget_dir"] = 0
            if budget is not None:
                prev_budget = budget
        else:
            m["Status"], m["Budget"], m["budget_dir"] = None, None, 0
            m["_carried"] = False
        rows.append(m)
    return rows


def campaign_total_row(fc: pd.DataFrame, day, choice, now_anch: datetime | None = None) -> dict:
    """Hang Total (R13). choice = gio Anchorage ah (0..23) hoac 'ALL'.
    Status/Budget = as-of gio chon ; Metrics = CUMULATIVE tai gio do (= tong 15:00 -> gio do).
    'ALL' = ca ngay (cumulative tai gio co mat cuoi cung)."""
    now_anch = now_anch or _now_anch()
    fc = fc.sort_values("hh")
    asof, cum_asof, present = _carry_forward_states(fc)
    if not present:
        return {"Giờ": "Total", "Status": None, "Budget": None}
    if choice == "ALL":
        ah = max(present)
    else:
        ah = int(choice)
    cum = cum_asof.get(ah)
    m = _compute_row(pd.DataFrame([cum])) if cum else {}
    m["Giờ"] = "Total"
    rs = None if (choice != "ALL" and _is_future(day, ah, now_anch)) else asof.get(ah)
    if rs is not None:
        status, budget = rs
        m["Status"] = "ACTIVE" if status == "ACTIVE" else "PAUSE"
        m["Budget"] = budget
        m["_carried"] = ah not in present
    else:
        m["Status"], m["Budget"] = None, None
        m["_carried"] = False
    m["budget_dir"] = 0
    return m


def total_budget_by_ah(facts_subset: pd.DataFrame, now_anch: datetime | None = None) -> dict:
    """Total Budget moi gio (R7) = TRUNG BINH/NGAY cua [tong daily_budget campaign ACTIVE as-of gio do].
    Tra {ah: budget_tb}. Active = status ACTIVE (carry-forward trong ngay)."""
    if facts_subset is None or facts_subset.empty:
        return {}
    now_anch = now_anch or _now_anch()
    sum_by_ah = {ah: 0.0 for ah in range(24)}
    nday_by_ah = {ah: 0 for ah in range(24)}
    for (_cid, day), fc in facts_subset.groupby(["campaign_id", "_day"]):
        asof, _, present = _carry_forward_states(fc.sort_values("hh"))
        if not present:
            continue
        first_present = min(present)
        for ah in range(24):
            if ah < first_present or _is_future(day, ah, now_anch):
                continue
            rs = asof[ah]
            if rs is None:
                continue
            status, budget = rs
            if status == "ACTIVE" and budget:
                sum_by_ah[ah] += budget
    # so ngay hop le moi gio = so (day) co du lieu tai gio do
    day_valid = {ah: set() for ah in range(24)}
    for (_cid, day), fc in facts_subset.groupby(["campaign_id", "_day"]):
        present = set(int(h) for h in fc["hh"].dropna())
        if not present:
            continue
        fp = min(present)
        for ah in range(24):
            if ah >= fp and not _is_future(day, ah, now_anch):
                day_valid[ah].add(day)
    out = {}
    for ah in range(24):
        n = len(day_valid[ah])
        if n > 0 and sum_by_ah[ah] > 0:
            out[ah] = sum_by_ah[ah] / n
    return out
