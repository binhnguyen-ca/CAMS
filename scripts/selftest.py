"""Self-test logic transform (THUAN pandas, KHONG can Grafana/Streamlit).
Chay: python scripts/selftest.py
"""
import os
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import transform as T  # noqa: E402

ANCH = ZoneInfo("America/Anchorage")
NOW = datetime(2030, 1, 1, tzinfo=ANCH)   # tuong lai xa -> khong gio nao bi mask "future"
DAY = date(2026, 6, 1)

# DIM: marketer a@crossian.com (P), b@crossian.com (Q)
dim = pd.DataFrame([
    {"campaign_id": "c1", "marketer": "a@crossian.com", "product": "P", "campaign_name": "Camp One"},
    {"campaign_id": "c2", "marketer": "a@crossian.com", "product": "P", "campaign_name": "Camp Two"},
    {"campaign_id": "c3", "marketer": "b@crossian.com", "product": "Q", "campaign_name": "Camp Three"},
])

# FACT cumulative day-to-date. c1: ah0,1,2 (budget 100->120->120). c2: ah0,1 (PAUSE tu ah1).
def row(cid, hh, status, budget, spent, impr, clk, vw, co, po, rev):
    return {"hh": hh, "campaign_id": cid, "status": status, "budget": budget,
            "spent": spent, "impressions": impr, "clicks": clk, "views": vw,
            "checkout": co, "purchase": po, "rev": rev, "_day": DAY}

facts = pd.DataFrame([
    row("c1", 0, "ACTIVE", 100, 10, 1000, 50, 200, 8, 1, 30),
    row("c1", 1, "ACTIVE", 120, 25, 2200, 110, 420, 18, 3, 95),
    row("c1", 2, "ACTIVE", 120, 40, 3500, 170, 650, 30, 5, 160),
    row("c2", 0, "ACTIVE", 50, 5, 600, 20, 90, 3, 0, 0),
    row("c2", 1, "PAUSE", 50, 8, 900, 30, 140, 5, 1, 40),
    row("c3", 0, "ACTIVE", 200, 99, 5000, 250, 900, 40, 7, 250),
])

facts = T.dedup_facts(facts)
ok = True


def check(name, cond, got=None):
    global ok
    status = "OK " if cond else "FAIL"
    if not cond:
        ok = False
    print(f"  [{status}] {name}" + (f"  -> {got}" if got is not None else ""))


print("== marketers_with_flag ==")
mk = T.marketers_with_flag(facts, dim)
print("  ", mk)
check("2 marketer", len(mk) == 2, mk)
check("ca 2 marketer active (co spent last2)", all(a for _, a in mk))
check("label rut gon", T.marketer_label("a@crossian.com") == "a")

print("== products_with_flag (a@crossian.com) ==")
pf = T.products_with_flag(facts, dim, "a@crossian.com")
print("  ", pf)
check("1 san pham P, active", pf == [("P", True)], pf)

print("== hourly_delta_rows (c1) ==")
fc1 = facts[facts["campaign_id"] == "c1"]
d1 = T.hourly_delta_rows(fc1).sort_values("hh")
spent_seq = list(d1["spent"])
print("  per-hour spent:", spent_seq)
check("delta spent = 10,15,15", spent_seq == [10, 15, 15], spent_seq)
check("delta purchase = 1,2,2", list(d1["purchase"]) == [1, 2, 2], list(d1["purchase"]))

print("== aggregate_hours (c1+c2, range) ==")
fsub = facts[facts["campaign_id"].isin(["c1", "c2"])]
agg = T.aggregate_hours(T.hourly_delta_rows(fsub), DAY)
ah0 = next(r for r in agg if r["_ah"] == 0)
check("ah0 ME = 10+5 = 15", abs(ah0["ME"] - 15) < 1e-6, ah0["ME"])
check("ah0 ROAS = rev/me = (30+0)/15 = 2.0", abs(ah0["ROAS"] - 2.0) < 1e-6, ah0["ROAS"])

print("== total_budget_by_ah (c1+c2) ==")
bud = T.total_budget_by_ah(fsub, now_anch=NOW)
print("  ", bud)
# ah0: c1 ACTIVE 100 + c2 ACTIVE 50 = 150 ; /1 ngay = 150
check("ah0 budget = 150", abs(bud.get(0, 0) - 150) < 1e-6, bud.get(0))
# ah1: c1 ACTIVE 120 + c2 PAUSE(loai) = 120
check("ah1 budget = 120 (c2 PAUSE bi loai)", abs(bud.get(1, 0) - 120) < 1e-6, bud.get(1))
# ah2: c1 ACTIVE 120 ; c2 carry-forward PAUSE -> loai
check("ah2 budget = 120", abs(bud.get(2, 0) - 120) < 1e-6, bud.get(2))

print("== campaign_day_rows (c1) ==")
rows = T.campaign_day_rows(fc1, DAY, now_anch=NOW)
check("24 dong", len(rows) == 24, len(rows))
r0, r1, r2 = rows[0], rows[1], rows[2]
check("ah0 Status ACTIVE", r0["Status"] == "ACTIVE", r0["Status"])
check("ah0 budget_dir 0 (dau tien)", r0["budget_dir"] == 0, r0["budget_dir"])
check("ah1 budget_dir +1 (100->120)", r1["budget_dir"] == 1, r1["budget_dir"])
check("ah2 budget_dir 0 (120->120)", r2["budget_dir"] == 0, r2["budget_dir"])
check("ah3 future? khong (NOW=2030) -> carry-forward ACTIVE", rows[3]["Status"] == "ACTIVE", rows[3]["Status"])
check("ah0 ME theo-gio = 10", abs((r0.get("ME") or 0) - 10) < 1e-6, r0.get("ME"))

print("== vn_label (khung = gio KET THUC; chup ah:55) ==")
check("ah0 -> 16:00 (chup 15:55 VN)", T.vn_label(DAY, 0) == "16:00", T.vn_label(DAY, 0))
check("ah22 -> 14:00", T.vn_label(DAY, 22) == "14:00", T.vn_label(DAY, 22))
check("ah23 -> 15:00 cuoi ngay (chup 14:55 VN)", T.vn_label(DAY, 23) == "15:00", T.vn_label(DAY, 23))

print("== pending vs carried (gio chup = ah:55) ==")
# 02:30 Anch: ah2 DA co snapshot -> hien thi du chua toi 02:55; ah3 chua toi gio chup -> trong
NOW2 = datetime(2026, 6, 1, 2, 30, tzinfo=ANCH)
rows2 = T.campaign_day_rows(fc1, DAY, now_anch=NOW2)
check("ah2 co snapshot, truoc :55 -> van hien", rows2[2]["Status"] == "ACTIVE", rows2[2]["Status"])
check("ah2 khong danh dau *", rows2[2].get("_carried") is False, rows2[2].get("_carried"))
check("ah3 chua toi gio chup -> trong", rows2[3]["Status"] is None, rows2[3]["Status"])
# 04:30 Anch: ah3 qua gio chup (03:55) ma khong co snapshot -> ke thua + danh dau *
NOW3 = datetime(2026, 6, 1, 4, 30, tzinfo=ANCH)
rows3 = T.campaign_day_rows(fc1, DAY, now_anch=NOW3)
check("ah3 qua gio chup, miss -> carried + *",
      rows3[3]["Status"] == "ACTIVE" and rows3[3].get("_carried") is True,
      (rows3[3]["Status"], rows3[3].get("_carried")))
check("ah4 chua toi gio chup -> trong", rows3[4]["Status"] is None, rows3[4]["Status"])

print("== campaign_total_row (c1) ==")
tot_all = T.campaign_total_row(fc1, DAY, "ALL", now_anch=NOW)
check("Total ALL ME = cumulative cuoi = 40", abs(tot_all["ME"] - 40) < 1e-6, tot_all["ME"])
check("Total ALL budget = 120 (as-of gio cuoi)", abs((tot_all["Budget"] or 0) - 120) < 1e-6, tot_all["Budget"])
tot_h1 = T.campaign_total_row(fc1, DAY, 1, now_anch=NOW)
check("Total @ah1 ME = cumulative ah1 = 25", abs(tot_h1["ME"] - 25) < 1e-6, tot_h1["ME"])

print()
print("KET QUA:", "TAT CA PASS" if ok else "CO TEST FAIL")
sys.exit(0 if ok else 1)
