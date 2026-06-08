from __future__ import annotations

from decimal import Decimal

import altair as alt
import pandas as pd
import streamlit as st

from reconciliation import reconcile

st.set_page_config(page_title="Reconciliation Checker", layout="wide")
st.title("Account Reconciliation Checker")
st.caption("Upload transaction and bank-balance CSVs to verify day-by-day reconciliation.")

# ─── Sidebar: File Uploads & Filters ──────────────────────────────────────────
# The sidebar keeps the controls separate from the results area.
# Users upload their two CSV files here and optionally filter the table view.
with st.sidebar:
    st.header("Upload Files")
    transactions_file = st.file_uploader(
        "Transactions CSV (columns: date,amount)",
        type=["csv"],
        key="transactions",
    )
    bank_file = st.file_uploader(
        "Bank Balances CSV (columns: date,balance)",
        type=["csv"],
        key="bank",
    )
    # When checked, the results table will only show days where discrepancies
    # were found — useful when there are many days and the user only cares
    # about the problem rows.
    show_only_mismatches = st.checkbox("Show only mismatch rows", value=False)


# ─── Helper: Decimal to Float for Charting ────────────────────────────────────
def _to_float_for_chart(series: pd.Series) -> pd.Series:
    """
    Converts a pandas Series of Decimal values to floats before passing to
    Streamlit's line chart.

    Streamlit's charting library (Altair/Vega) does not understand Python's
    Decimal type — it expects standard Python floats or numpy numbers.
    We only convert here for display purposes; all actual calculations in
    reconciliation.py use Decimal to avoid rounding errors.
    """
    return series.map(lambda x: float(x) if isinstance(x, Decimal) else float(x))


# ─── Guard: Wait Until Both Files Are Uploaded ────────────────────────────────
# st.stop() halts execution of the rest of the script. The app shows a prompt
# and waits — nothing below this block runs until both files are provided.
if not transactions_file or not bank_file:
    st.info("Upload both CSV files to run reconciliation.")
    st.stop()


# ─── Load CSVs and Run Reconciliation ─────────────────────────────────────────
# Read both uploaded files into DataFrames and pass them to the reconcile()
# function from reconciliation.py. If anything goes wrong (bad columns,
# unparseable dates, non-numeric amounts), the error is caught and displayed
# to the user in a readable way — the app does not crash.
try:
    tx_df = pd.read_csv(transactions_file)
    bank_df = pd.read_csv(bank_file)
    result_df, summary = reconcile(tx_df, bank_df)
except Exception as exc:
    st.error(f"Failed to process files: {exc}")
    st.stop()


# ─── Summary Metric Cards ──────────────────────────────────────────────────────
# Display four headline numbers across the top of the page in a 4-column grid.
# These give the user an instant at-a-glance answer: how many days matched,
# how many didn't, and the exact date to start investigating.
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total days", summary.total_days)
col2.metric("Matched days", summary.matched_days)
col3.metric("Mismatched days", summary.mismatched_days)
col4.metric("First mismatch", summary.first_mismatch_date or "None")


# ─── Reconciliation Table ─────────────────────────────────────────────────────
# Show the full day-by-day breakdown. If the sidebar checkbox is ticked,
# filter down to only the mismatch rows so the accountant can focus on problems.
# use_container_width=True makes the table stretch to fill available space.
display_df = result_df.copy()
if show_only_mismatches:
    display_df = display_df.loc[~display_df["is_match"]]

st.subheader("Reconciliation Table")
st.dataframe(display_df, use_container_width=True)


# ─── Layered Altair Chart: Expected vs Bank Balance ───────────────────────────
# A creative layered chart with three visual layers:
# 1. A red shaded band between the two lines — the "gap".
#    When balances match perfectly the gap is 0 and the red disappears entirely.
#    When there is a mismatch the red area grows, making the discrepancy
#    impossible to miss even at a glance.
# 2. Two colored lines with dot markers at each date for precise reading.
# 3. Interactive tooltips on hover showing exact values per day.
st.subheader("Expected vs Bank Balance")

chart_df = result_df[["date", "expected_balance", "bank_balance"]].copy()
chart_df["expected_balance"] = _to_float_for_chart(chart_df["expected_balance"])
chart_df["bank_balance"] = _to_float_for_chart(chart_df["bank_balance"])

# Compute upper and lower bounds per day for the gap band.
# When both values are equal the band has zero height and renders invisible.
chart_df["upper"] = chart_df[["expected_balance", "bank_balance"]].max(axis=1)
chart_df["lower"] = chart_df[["expected_balance", "bank_balance"]].min(axis=1)

# Layer 1: red shaded gap area between the two lines
gap_band = (
    alt.Chart(chart_df)
    .mark_area(color="#FF4B4B", opacity=0.25)
    .encode(
        x=alt.X("date:O", axis=alt.Axis(labelAngle=-45, title="Date")),
        y=alt.Y("upper:Q", title="Balance ($)"),
        y2=alt.Y2("lower:Q"),
        tooltip=[
            alt.Tooltip("date:O", title="Date"),
            alt.Tooltip("upper:Q", title="Upper", format=",.2f"),
            alt.Tooltip("lower:Q", title="Lower", format=",.2f"),
        ],
    )
)

# Layer 2: two lines with dot markers, one per series
melted = chart_df.melt(
    "date",
    value_vars=["expected_balance", "bank_balance"],
    var_name="series",
    value_name="balance",
)
lines = (
    alt.Chart(melted)
    .mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=60))
    .encode(
        x=alt.X("date:O"),
        y=alt.Y("balance:Q"),
        color=alt.Color(
            "series:N",
            scale=alt.Scale(
                domain=["bank_balance", "expected_balance"],
                range=["#4C9BE8", "#F4A261"],
            ),
            legend=alt.Legend(title="Series"),
        ),
        tooltip=[
            alt.Tooltip("date:O", title="Date"),
            alt.Tooltip("series:N", title="Series"),
            alt.Tooltip("balance:Q", title="Balance", format=",.2f"),
        ],
    )
)

layered_chart = (gap_band + lines).properties(height=380)
st.altair_chart(layered_chart, use_container_width=True)

# Status message below the chart
if summary.mismatched_days == 0:
    st.success("No red shading visible - all days reconcile perfectly.")
else:
    st.warning(f"Red shading highlights {summary.mismatched_days} day(s) with discrepancies. First mismatch: {summary.first_mismatch_date}")


# ─── Download Button ──────────────────────────────────────────────────────────
# Allow the user to export the current table view (full or filtered) as a CSV.
# The data is encoded to UTF-8 bytes since st.download_button expects bytes.
# This is useful for saving results or sharing with a colleague.
csv_download = display_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download current table as CSV",
    data=csv_download,
    file_name="reconciliation_results.csv",
    mime="text/csv",
)