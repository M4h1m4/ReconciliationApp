# Account Reconciliation Checker

A Streamlit web app that reconciles daily bank balances against internal transaction records and flags any discrepancies.

## What it does

- Upload a transactions CSV and a bank balances CSV
- Computes the expected balance day by day using a running cumulative sum of transactions
- Compares expected balance vs bank-reported balance for each date
- Flags mismatched days and identifies the first date a discrepancy appears
- Displays a summary, a detailed table, and a line chart

## Tech Stack

- Python
- Streamlit
- Pandas

## Live Demo

The app is hosted on Streamlit Cloud and requires no installation.

**URL:** https://reconciliationapp-hcwvfav8houdw9tvbrwn4v.streamlit.app/

### How to use it

1. Open the link above in any browser
2. In the **left sidebar**, upload your two CSV files:
   - `transactions.csv` — must have `date` and `amount` columns
   - `bank_balances.csv` — must have `date` and `balance` columns
3. The results appear automatically once both files are uploaded:
   - **4 metric cards** at the top show total days, matched days, mismatched days, and the first mismatch date
   - **Reconciliation table** shows a row-by-row breakdown for every date
   - **Line chart** plots expected balance vs bank balance over time — divergence is immediately visible
4. Tick **"Show only mismatch rows"** in the sidebar to filter the table down to problem days only
5. Click **"Download current table as CSV"** to export the results

> If the app shows "This app has gone to sleep", just click **Wake up** — it starts in a few seconds.

---

## Run Locally

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/reconciliation-app.git
cd reconciliation-app

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
streamlit run app.py
```

## Input Format

**transactions.csv**
```
date,amount
2025-06-01,1000.00
2025-06-02,-50.00
```

**bank_balances.csv**
```
date,balance
2025-06-01,1000.00
2025-06-02,925.00
```

Sample files are available in the `data/` folder.

## Output

| Column | Description |
|---|---|
| `date` | Statement date |
| `bank_balance` | Balance reported by the bank |
| `daily_transaction_total` | Net transactions for that day |
| `expected_balance` | Cumulative sum of transactions |
| `difference` | Expected minus bank balance |
| `is_match` | True if records agree, False if not |
