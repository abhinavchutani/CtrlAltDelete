"""Climate & Nature Navigator: Streamlit entry point.  Run: make app"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app import data, ui  # noqa: E402

st.set_page_config(page_title="Climate & Nature Navigator", page_icon="🌱", layout="wide")

pages = [
    st.Page("views/data_quality.py", title="Data quality", icon="🔎", default=True),
    st.Page("views/inventory.py", title="Inventory 2025", icon="📊"),
    st.Page("views/farm_peat.py", title="Farm & peat", icon="🌾"),
    st.Page("views/climate_risk.py", title="Climate risk", icon="🌦️"),
]
nav = st.navigation(pages)

with st.sidebar:
    st.markdown("### 🌱 Navigator")
    path, label = data.source()
    st.caption(f"Data: **{label}** · `{Path(path).name}`")
    st.toggle("Show drafts", value=True, key="show_drafts",
              help="Only published results are final. Drafts carry a 'pending expert approval' badge.")

ui.banner()
nav.run()
ui.copilot_panel()
