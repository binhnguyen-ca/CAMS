"""CAMS — doc DIM + FACT cho dashboard.

  data/campaigns.csv          : DIM (1 dong/campaign) campaign_id,marketer,product,campaign_name,first_seen,last_seen
  data/facts/<YYYY-MM-DD>.csv  : FACT (1 dong/campaign/gio) hh,campaign_id,status,budget,spent,impressions,
                                 clicks,views,checkout,purchase,rev  (metrics = cong don day-to-date)

Loader nang duoc @st.cache_data(ttl=600): doc dia + concat 1 lan, moi rerun dung lai.
Data moi push len GitHub -> Streamlit Cloud reboot -> tu xoa cache. cache_data tra BAN COPY.
"""
import os
import glob

import pandas as pd
import streamlit as st

_TTL = 600

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
FACTS_DIR = os.path.join(BASE, "facts")
DIM_PATH = os.path.join(BASE, "campaigns.csv")


@st.cache_data(ttl=_TTL)
def load_dim():
    """DIM campaigns.csv -> DataFrame (campaign_id la str). None neu chua co."""
    if not os.path.exists(DIM_PATH):
        return None
    try:
        df = pd.read_csv(DIM_PATH, dtype={"campaign_id": str})
    except (pd.errors.EmptyDataError, FileNotFoundError):
        return None
    return df if not df.empty else None


def list_fact_days() -> list:
    """Cac ngay (str YYYY-MM-DD) co file FACT, moi nhat truoc."""
    files = sorted(glob.glob(os.path.join(FACTS_DIR, "*.csv")), reverse=True)
    return [os.path.basename(f)[:-4] for f in files]


@st.cache_data(ttl=_TTL)
def load_facts():
    """Gop TOAN BO data/facts/<ngay>.csv. Them cot _day (date tu ten file). None neu chua co.
    Chua dedup (de transform.dedup_facts xu ly) nhung da parse _day."""
    files = sorted(glob.glob(os.path.join(FACTS_DIR, "*.csv")))
    frames = []
    for f in files:
        try:
            df = pd.read_csv(f, dtype={"campaign_id": str})
        except (pd.errors.EmptyDataError, FileNotFoundError):
            continue
        if df.empty:
            continue
        df["_day"] = pd.to_datetime(os.path.basename(f)[:-4], errors="coerce").date()
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else None
