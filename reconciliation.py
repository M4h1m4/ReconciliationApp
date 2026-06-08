from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Tuple 

import pandas as pd

@dataclass
class ReconciliationSummary:
    total_days: int # Number of days of bank statements are processed
    matched_days: int #Number of days where expected balance = actual balance
    mismatched_days: int #Days where expected balance != actual balance
    first_mismatch_date: str | None #Earliest discrepancy date, None if no mismatches

def _to_decimal(value: str) -> Decimal:
    #convert numeric inputs into decimals safely 
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f"Invalid decimal value: {value}")

def _validate_columns(df: pd.DataFrame, required: set[str], name: str) -> None:
    #Check if the dataframe has all the columns required for reconciliation, raise error if any are missing
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{name} is missing required columns: {sorted(missing)}")


def _normalize_transactions(transactions_dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and prepares transactions csv for reconcilition

    steps performed:
    1. validates if 'date' and 'amount' columns are present
    2. Parses dates into datetime objects
    3. Converts 'amount' values into decimals for accurate financial calculations
    4. groups all transactions by date and sums the amounts to get daily totals
    5. returns dates sorted by date, oldest first
    """
    _validate_columns(transactions_dataframe, {"date", "amount"}, "Transactions CSV")
    tx = transactions_dataframe.copy()
    tx["date"] = pd.to_datetime(tx["date"], errors="raise").dt.normalize()
    tx["amount"] = tx["amount"].map(_to_decimal)

    daily_tx = tx.groupby("date", as_index=False)["amount"].sum()
    return daily_tx.sort_values("date").reset_index(drop=True)


def _normalize_balances(bank_df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and prepares bank balances csv for reconciliation

    steps performed:
    1. validates if 'date' and 'balances' columns are present
    2. Parses dates into datetime objects
    3. Converts balance values into decimals for accurate financial calculations
    4. returns dates sorted by date, oldest first
    """
    _validate_columns(bank_df, {"date", "balance"}, "Bank Statements CSV")
    bank = bank_df.copy()
    bank["date"] = pd.to_datetime(bank["date"], errors="raise").dt.normalize()
    bank["balance"] = bank["balance"].map(_to_decimal)
    return bank.sort_values("date").reset_index(drop=True)

def reconcile(
    transactions_df: pd.DataFrame, bank_df: pd.DataFrame
) -> Tuple[pd.DataFrame, ReconciliationSummary]:
    """
    Core Reconciliation logic: 
    Take two raw dataframes (from CSVs) and returns a day-by-day reconciliation report along with a summary of the results.

    Logic: 

    The bank CSV tells what bank recorded as a balance on each date
    The transaction CSV tells us every transaction made (withdrawals and deposits) on each date
    We compute an 'expected balance' by doing a running cumulative sum of
    all daily transaction totals. Starting from Day 1, each day we add that
    day's net transactions to the previous day's running total.
    We then compare expected_balance vs bank_balance for every date.
    If they differ, that day is flagged as a mismatch.

    Returns:
    - result_df: one row per bank statement with columns: 
        date, bank balance, daily_transaction_total, expected_balance, difference, match (boolean: is_match)
    - summary: ReconciliationSummary with headline counts and first mismatch date 
    """

    daily_tx = _normalize_transactions(transactions_df)
    bank = _normalize_balances(bank_df)

    if bank.empty:
        raise ValueError("Bank statements is empty, cannot perform reconciliation.")


    #starting with bank statements date as source of truth. 
    #performing left join so days with no transactions still appear and the value is 0 
    result = bank[["date", "balance"]].rename(columns={"balance": "bank_balance"}).copy()
    result = result.merge(
        daily_tx.rename(columns={"amount": "daily_transaction_total"}),
        on="date",
        how="left",
    )


    #Days present in the df but no transactions are present hence we fill those with 0
    result["daily_transaction_total"] = result["daily_transaction_total"].fillna(Decimal("0"))



    # Build the expected balance column by walking through each day in order
    # and accumulating a running total. This mirrors how a real bank balance grows:
    # each day's balance = previous balance + today's net transactions.
    expected_values = []
    running_total = Decimal("0")
    for daily_amount in result["daily_transaction_total"]:
        running_total += daily_amount
        expected_values.append(running_total)
    result["expected_balance"] = expected_values


    # Compute the difference. A value of 0 means records agree, any non-zero value
    # means the bank reported a different balance than our transactions imply.
    result["difference"] = result["expected_balance"] - result["bank_balance"]
    result["is_match"] = result["difference"] == Decimal("0")

    # Format dates as "YYYY-MM-DD" strings for clean display in the UI table.
    result["date"] = result["date"].dt.strftime("%Y-%m-%d")

    # Find the earliest date where a mismatch exists — this is the most
    # actionable piece of information for an accountant investigating discrepancies.
    mismatches = result.loc[~result["is_match"]]
    first_mismatch_date = None if mismatches.empty else mismatches.iloc[0]["date"]

    summary = ReconciliationSummary(
        total_days=len(result),
        matched_days=int(result["is_match"].sum()),
        mismatched_days=int((~result["is_match"]).sum()),
        first_mismatch_date=first_mismatch_date,
    )
    return result, summary




