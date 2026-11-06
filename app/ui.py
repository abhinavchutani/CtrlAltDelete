"""Shared UI bits: synthetic-data banner, status badges, the drafts toggle, the copilot panel."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app import data

BADGE = {"published": "🟢 published", "approved": "🔵 approved", "draft": "🟠 draft · pending expert approval"}


def banner() -> None:
    if data.is_mock():
        st.warning("**MOCK DATA**: placeholder rows from `app/mock.py`, not results. Run the pipelines to replace them.")
    st.caption("All figures come from the organisers' synthetic twin and are **not Apetit's real data**.")


def show_drafts() -> bool:
    return st.session_state.get("show_drafts", True)


def badges(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "status" in df:
        df["status"] = df["status"].map(lambda s: BADGE.get(s, s))
    return df


def copilot_panel() -> None:
    with st.sidebar:
        st.divider()
        st.subheader("Copilot")
        st.caption("Answers only from tool results, with evidence.")
        hist = st.session_state.setdefault("chat", [])
        for role, text in hist[-6:]:
            st.chat_message(role).markdown(text)
        if prompt := st.chat_input("Ask about the inventory or climate risk"):
            hist.append(("user", prompt))
            hist.append(("assistant", _answer(prompt)))
            st.rerun()


def _answer(question: str) -> str:
    try:
        from src.e_agent import answer  # built in #22
    except ImportError:
        return "_The copilot is not connected yet (#22)._"
    res = answer(question)
    return getattr(res, "markdown", str(res))
