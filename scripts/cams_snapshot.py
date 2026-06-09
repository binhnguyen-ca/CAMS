"""CAMS — SNAPSHOT tat ca marketer Crossian, campaign-level, MOI GIO. Luu DIM + FACT.

Vi sao: budget/status cua campaign KHONG co lich su trong DB Selless (chi giu gia tri
hien tai, bi FB ghi de moi sync). Cach duy nhat dung timeline = tu snapshot moi gio.

Moi lan chay (1 query lay tat ca campaign Crossian cua ngay Anchorage hien tai):
  - UPSERT  data/campaigns.csv         (DIM, tinh)  : campaign_id, marketer, product,
                                                      campaign_name, first_seen, last_seen
  - APPEND  data/facts/<YYYY-MM-DD>.csv (FACT, dong): hh, campaign_id, status, budget,
                                        spent, impressions, clicks, views, checkout, purchase, rev
hh   = gio Anchorage (00-23) tai thoi diem chup ; file FACT = ngay Anchorage.
Metrics trong FACT = CONG DON day-to-date (00:00 Anchorage -> bay gio) -> app dung diff
giua 2 gio lien tiep de ra so theo-gio. budget/status la point-in-time (khong diff).

Dau lay data (core.remote_auth): GRAFANA_TOKEN -> token ; GRAFANA_COOKIE -> cookie ;
khong co -> trinh duyet da dang nhap (PC).

Chay:  python scripts/cams_snapshot.py
"""
import os
import csv
import json
from datetime import datetime

import core

HERE = os.path.dirname(os.path.abspath(__file__))
SQL_PATH = os.path.join(HERE, "cams_query_snapshot.sql")
DATA_DIR = os.path.join(HERE, "..", "data")
FACTS_DIR = os.path.join(DATA_DIR, "facts")
DIM_PATH = os.path.join(DATA_DIR, "campaigns.csv")
CONFIG_PATH = os.path.join(DATA_DIR, "snapshot_config.json")

# Cot tra ve tu cams_query_snapshot.sql (theo alias)
QUERY_COLS = [
    "campaign_id", "marketer", "campaign_name", "product", "effective_status",
    "budget", "me", "rev", "po", "impressions", "clicks", "views", "init_checkout",
]
# DIM: 1 dong/campaign (tinh) — upsert theo campaign_id
DIM_COLS = ["campaign_id", "marketer", "product", "campaign_name", "first_seen", "last_seen"]
# FACT: 1 dong/campaign/gio (dong) — append
FACT_COLS = ["hh", "campaign_id", "status", "budget",
             "spent", "impressions", "clicks", "views", "checkout", "purchase", "rev"]


def load_config() -> dict:
    """Doc data/snapshot_config.json. Mac dinh enabled=True."""
    cfg = {"enabled": True}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except FileNotFoundError:
        pass
    return cfg


def build_body(win: dict) -> dict:
    """Body query snapshot (all-marketer) cho cua so thoi gian cho truoc."""
    with open(SQL_PATH, "r", encoding="utf-8") as f:
        sql = f.read()
    return core.make_query_body(sql, win["from_ms"], win["to_ms"],
                                interval_ms=60000, max_data_points=1143)


def upsert_dim(recs: list, today_str: str) -> int:
    """Doc DIM hien co -> upsert theo campaign_id -> ghi lai. Tra so campaign trong DIM."""
    dim = {}
    if os.path.exists(DIM_PATH):
        with open(DIM_PATH, "r", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                dim[r["campaign_id"]] = r
    for rec in recs:
        cid = str(rec["campaign_id"])
        if cid in dim:
            d = dim[cid]
            d["marketer"] = rec["marketer"]
            d["product"] = rec["product"]
            d["campaign_name"] = rec["campaign_name"]
            d["last_seen"] = today_str
            if not d.get("first_seen"):
                d["first_seen"] = today_str
        else:
            dim[cid] = {
                "campaign_id": cid, "marketer": rec["marketer"],
                "product": rec["product"], "campaign_name": rec["campaign_name"],
                "first_seen": today_str, "last_seen": today_str,
            }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DIM_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DIM_COLS)
        w.writeheader()
        for cid in sorted(dim):
            w.writerow({k: dim[cid].get(k, "") for k in DIM_COLS})
    return len(dim)


def main():
    cfg = load_config()
    if not cfg.get("enabled", True):
        print("CAMS snapshot DANG TAT (enabled=false trong snapshot_config.json). Bo qua.")
        return

    kind = core.remote_auth()
    now_vn = datetime.now(core.VN_TZ)
    now_anch = now_vn.astimezone(core.DATA_TZ)
    win = core.time_window(now_vn)   # Anchorage 00:00 hom nay -> bay gio (intraday)
    print(f"[{now_vn:%Y-%m-%d %H:%M} VN] CAMS SNAPSHOT | che do={core.mode_label(kind)}")

    if kind:   # cookie/token: requests thuan — KHONG mo dashboard, KHONG xoay cookie
        payload = core.requests_post(build_body(win))
    else:      # PC: 1 context trinh duyet da dang nhap
        with core.browser_session() as post:
            payload = post(build_body(win))

    header, rows = core.parse_frames(payload)
    idx = {name: i for i, name in enumerate(header)}
    recs = [{c: (r[idx[c]] if c in idx else "") for c in QUERY_COLS} for r in rows]
    if not recs:
        print("Khong co campaign nao tra ve. Bo qua (khong ghi).")
        return

    today_str = f"{now_anch:%Y-%m-%d}"   # ngay Anchorage
    hh = f"{now_anch.hour:02d}"           # gio Anchorage 00-23

    n_dim = upsert_dim(recs, today_str)

    os.makedirs(FACTS_DIR, exist_ok=True)
    fact_path = os.path.join(FACTS_DIR, f"{today_str}.csv")
    is_new = not os.path.exists(fact_path)
    n = 0
    with open(fact_path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(FACT_COLS)
        for rec in recs:
            w.writerow([
                hh, rec["campaign_id"], rec["effective_status"], rec["budget"],
                rec["me"], rec["impressions"], rec["clicks"], rec["views"],
                rec["init_checkout"], rec["po"], rec["rev"],
            ])
            n += 1
    n_mkt = len({r["marketer"] for r in recs})
    print(f"FACT: ghi {n} campaign (hh={hh} Anchorage) -> data/facts/{today_str}.csv | "
          f"DIM: {n_dim} campaign | {n_mkt} marketer")


if __name__ == "__main__":
    main()
