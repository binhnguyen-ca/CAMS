"""Sinh DATA GIA (DIM + FACT) de test dashboard. KHONG dung cho production.
Chay: python scripts/_gen_sample.py   -> ghi data/campaigns.csv + data/facts/<ngay>.csv
Xoa truoc khi snapshot that:  Remove-Item data/campaigns.csv, data/facts/*.csv
"""
import os
import csv
import random
from datetime import date, timedelta

random.seed(7)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
FACTS = os.path.join(DATA, "facts")
os.makedirs(FACTS, exist_ok=True)

DIM_COLS = ["campaign_id", "marketer", "product", "campaign_name", "first_seen", "last_seen"]
FACT_COLS = ["hh", "campaign_id", "status", "budget",
             "spent", "impressions", "clicks", "views", "checkout", "purchase", "rev"]

# (marketer, product, campaign_id, name, daily_budget, base_spend/h, roas, ctr, cvr, pause_after, budget_bump_at)
CAMPS = [
    ("nguyen.bnguyen@example.com", "RosyLift 1.0", "1001", "RL_CBO_US_v1", 120, 6.0, 2.8, 0.018, 0.05, None, 10),
    ("nguyen.bnguyen@example.com", "RosyLift 1.0", "1002", "RL_ABO_broad", 80, 4.0, 1.4, 0.012, 0.03, 14, None),
    ("nguyen.bnguyen@example.com", "LynaShape 1.0", "1003", "LS_CBO_scale", 200, 11.0, 3.4, 0.022, 0.06, None, None),
    ("linh.tran@example.com", "GlowSerum 2.0", "2001", "GS_test_audience", 50, 2.5, 0.9, 0.009, 0.02, 12, None),
    ("linh.tran@example.com", "GlowSerum 2.0", "2002", "GS_winner_v3", 150, 8.0, 4.1, 0.025, 0.07, None, 8),
    # marketer cu: chi co data ngay dau -> KHONG active 2 ngay gan nhat (test co ▫️)
    ("old.user@example.com", "DeadProduct 1.0", "3001", "OLD_camp", 30, 1.0, 0.5, 0.005, 0.01, None, None),
]

DAYS = [date(2026, 6, 4), date(2026, 6, 5), date(2026, 6, 6)]  # qua khu (Anchorage) -> khong bi mask "future"
HOURS = list(range(0, 24))  # tron 24 gio

dim = {}
for d in DAYS:
    rows = []
    for (mk, prod, cid, name, dbud, rate, roas, ctr, cvr, pause_after, bump_at) in CAMPS:
        if cid == "3001" and d != DAYS[0]:
            continue  # marketer cu chi chay ngay dau
        dim[cid] = [cid, mk, prod, name,
                    dim.get(cid, [None, None, None, None, str(DAYS[0])])[4] if cid in dim else str(d),
                    str(d)]
        cum = dict(spent=0.0, impr=0.0, clk=0.0, vw=0.0, co=0.0, po=0.0, rev=0.0)
        for hh in HOURS:
            status = "ACTIVE"
            if pause_after is not None and hh > pause_after:
                status = "PAUSE"
            budget = dbud
            if bump_at is not None and hh >= bump_at:
                budget = round(dbud * 1.5)
            if status == "ACTIVE":
                sp = rate * (0.7 + 0.6 * random.random())
                cum["spent"] += sp
                imp = sp / max(ctr, 0.001) / 2.0
                cum["impr"] += imp
                cum["clk"] += imp * ctr
                cum["vw"] += imp * ctr * (0.8 + 0.4 * random.random())
                cum["co"] += imp * ctr * cvr * 1.5
                po = (cum["spent"] * roas) / 25.0  # gia tri don ~ $25
                cum["po"] = po
                cum["rev"] = cum["spent"] * roas
            rows.append([hh, cid, status, budget,
                         round(cum["spent"], 2), int(cum["impr"]), int(cum["clk"]),
                         int(cum["vw"]), int(cum["co"]), int(cum["po"]), round(cum["rev"], 2)])
    with open(os.path.join(FACTS, f"{d}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(FACT_COLS)
        w.writerows(rows)
    print(f"FACT {d}: {len(rows)} dong")

with open(os.path.join(DATA, "campaigns.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(DIM_COLS)
    for cid in sorted(dim):
        w.writerow(dim[cid])
print(f"DIM: {len(dim)} campaign")
