# -*- coding: utf-8 -*-
"""
Created on Thu Apr 30 15:09:51 2026

@author: Aaron
"""

import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="DCF Valuation App", layout="wide")

# --------------------------------------------------
# TITLE + EDUCATIONAL OVERVIEW
# --------------------------------------------------
st.title("📊 Discounted Cash Flow (DCF) Valuation App")

st.write("""
### How This Model Works
This app estimates a company's intrinsic value using a **DCF model**:

1. Pull financial statements
2. Use assumptions to forecast cash flows
3. Compute WACC (cost of capital)
4. Discount future cash flows
5. Add terminal value
6. Compare to market price
""")

# --------------------------------------------------
# SIDEBAR INPUTS
# --------------------------------------------------
st.sidebar.header("📥 Inputs")

ticker = st.sidebar.text_input("Stock Ticker", "AAPL").upper()
stock = yf.Ticker(ticker)

# --------------------------------------------------
# FETCH DATA
# --------------------------------------------------
current_price = None
shares_outstanding = None
revenue = None
cash = None
debt = None

st.header("📡 Company Data")

try:
    info = stock.info
    current_price = info.get("currentPrice")
    shares_outstanding = info.get("sharesOutstanding")

    st.write(f"**Company:** {info.get('longName', ticker)}")
    st.write(f"**Price:** ${current_price:,.2f}" if current_price else "Price unavailable")
    st.write(f"**Shares Outstanding:** {shares_outstanding:,.0f}" if shares_outstanding else "Unavailable")

except:
    st.warning("Market data unavailable")

# Revenue
try:
    financials = stock.financials
    revenue = financials.loc["Total Revenue"][0]
    st.write(f"**Revenue:** ${revenue:,.0f}")
except:
    revenue = st.sidebar.number_input("Revenue ($)")

# Cash + Debt from balance sheet
try:
    bs = stock.balance_sheet

    cash = bs.loc["Cash And Cash Equivalents"][0] if "Cash And Cash Equivalents" in bs.index else None

    if "Total Debt" in bs.index:
        debt = bs.loc["Total Debt"][0]
    else:
        debt = bs.loc.get("Long Term Debt", [0])[0] + bs.loc.get("Short Long Term Debt", [0])[0]

    st.write(f"**Cash:** ${cash:,.0f}" if cash else "Cash unavailable")
    st.write(f"**Debt:** ${debt:,.0f}" if debt else "Debt unavailable")

except:
    st.warning("Balance sheet unavailable")

# Fallbacks
if cash is None:
    cash = st.sidebar.number_input("Cash ($)")
if debt is None:
    debt = st.sidebar.number_input("Debt ($)")
if shares_outstanding is None:
    shares_outstanding = st.sidebar.number_input("Shares Outstanding")

# --------------------------------------------------
# 5-YEAR HISTORICAL AVERAGES (GUIDANCE LAYER)
# --------------------------------------------------
st.subheader("📈 Historical Context (5-Year Averages)")

avg_growth = None
avg_margin = None
avg_return = None

try:
    hist = stock.history(period="5y")
    hist["Returns"] = hist["Close"].pct_change()
    avg_return = hist["Returns"].mean() * 252

    st.write(f"**Avg Annual Return:** {avg_return:.2%}")
    st.line_chart(hist["Close"])

except:
    pass

try:
    fin = stock.financials.T.head(5)
    if "Total Revenue" in fin.columns:
        avg_growth = fin["Total Revenue"].pct_change().mean()

    if "EBIT" in fin.columns:
        avg_margin = (fin["EBIT"] / fin["Total Revenue"]).mean()

except:
    pass

# --------------------------------------------------
# ASSUMPTIONS
# --------------------------------------------------
st.sidebar.subheader("Assumptions")

growth = st.sidebar.number_input("Growth Rate (%)", value=5.0) / 100
if avg_growth:
    st.sidebar.caption(f"📊 5Y Avg Growth: {avg_growth:.2%}")
else:
    st.sidebar.caption("📊 Typical range: 3% – 10%")

margin = st.sidebar.number_input("EBIT Margin (%)", value=20.0) / 100
if avg_margin:
    st.sidebar.caption(f"📊 5Y Avg Margin: {avg_margin:.2%}")
else:
    st.sidebar.caption("📊 Typical range: 10% – 30%")

reinvest = st.sidebar.number_input("Reinvestment Rate (%)", value=50.0) / 100
st.sidebar.caption("🔁 Ballpark: 30% – 70% depending on capital intensity")

terminal_growth = st.sidebar.number_input("Terminal Growth (%)", value=2.5) / 100
st.sidebar.caption("📉 Typical long-term: 2% – 3% (GDP-like growth)")

years = st.sidebar.slider("Projection Years", 3, 10, 5)

# --------------------------------------------------
# WACC COMPONENTS
# --------------------------------------------------
st.sidebar.subheader("WACC Components")

default_coe = avg_return * 100 if avg_return else 10.0

cost_of_equity = st.sidebar.number_input("Cost of Equity (%)", value=float(default_coe)) / 100
cost_of_debt = st.sidebar.number_input("Cost of Debt (%)", value=5.0) / 100
tax_rate = st.sidebar.number_input("Tax Rate (%)", value=25.0) / 100

# --------------------------------------------------
# WACC CALCULATION
# --------------------------------------------------
equity_value = shares_outstanding * current_price if current_price else 0
total_value = equity_value + debt if (equity_value + debt) > 0 else 1

equity_weight = equity_value / total_value
debt_weight = debt / total_value

wacc = (
    equity_weight * cost_of_equity
    + debt_weight * cost_of_debt * (1 - tax_rate)
)

# --------------------------------------------------
# WACC EXPLANATION
# --------------------------------------------------
st.subheader("🧮 WACC Breakdown (Fully Explained)")

st.write(f"""
WACC = (E/V × Re) + (D/V × Rd × (1 − T))

E = ${equity_value:,.2f}  
D = ${debt:,.2f}  
V = ${total_value:,.2f}  

Equity Weight = {equity_weight:.2%}  
Debt Weight = {debt_weight:.2%}  

Cost of Equity = {cost_of_equity:.2%}  
Cost of Debt = {cost_of_debt:.2%}  
Tax Rate = {tax_rate:.2%}  

### Final WACC = {wacc:.2%}
""")

# --------------------------------------------------
# PROJECTION
# --------------------------------------------------
revenues, fcfs, ebits, nopats = [], [], [], []

rev = revenue

for t in range(years):
    rev *= (1 + growth)
    ebit = rev * margin
    nopat = ebit * (1 - tax_rate)
    fcf = nopat * (1 - reinvest)

    revenues.append(rev)
    ebits.append(ebit)
    nopats.append(nopat)
    fcfs.append(fcf)

# --------------------------------------------------
# DISCOUNTING
# --------------------------------------------------
discount_factors = [(1 / (1 + wacc) ** (t + 1)) for t in range(years)]
pv_fcfs = [fcf * df for fcf, df in zip(fcfs, discount_factors)]

terminal_value = fcfs[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
pv_terminal = terminal_value / ((1 + wacc) ** years)

enterprise_value = sum(pv_fcfs) + pv_terminal
equity_value_final = enterprise_value - debt + cash
value_per_share = equity_value_final / shares_outstanding

# --------------------------------------------------
# RESULTS
# --------------------------------------------------
st.header("📈 Valuation Results")

c1, c2, c3 = st.columns(3)
c1.metric("Enterprise Value", f"${enterprise_value:,.2f}")
c2.metric("Equity Value", f"${equity_value_final:,.2f}")
c3.metric("Intrinsic Value", f"${value_per_share:,.2f}")

if current_price:
    upside = (value_per_share / current_price - 1) * 100
    st.metric("Market Price", f"${current_price:,.2f}")
    st.metric("Upside / Downside", f"{upside:.2f}%")

# --------------------------------------------------
# STEP-BY-STEP BREAKDOWN
# --------------------------------------------------
st.subheader("🔍 Step-by-Step DCF Breakdown")

for i in range(years):
    st.write(f"""
Year {i+1}  
Revenue: ${revenues[i]:,.2f}  
EBIT: ${ebits[i]:,.2f}  
NOPAT: ${nopats[i]:,.2f}  
FCF: ${fcfs[i]:,.2f}  
PV FCF: ${pv_fcfs[i]:,.2f}
""")

st.write(f"""
Terminal Value: ${terminal_value:,.2f}  
PV Terminal Value: ${pv_terminal:,.2f}
""")

# --------------------------------------------------
# TABLE
# --------------------------------------------------
df = pd.DataFrame({
    "Year": np.arange(1, years + 1),
    "Revenue": revenues,
    "FCF": fcfs,
    "PV FCF": pv_fcfs
})

st.subheader("📋 Projection Table")
st.dataframe(df)

# --------------------------------------------------
# VISUALS
# --------------------------------------------------
st.subheader("📊 Visual Analysis")

st.line_chart(df.set_index("Year")[["Revenue", "FCF"]])

st.bar_chart(pd.DataFrame({
    "FCF": fcfs,
    "Discounted FCF": pv_fcfs
}))

st.line_chart(pd.DataFrame({
    "Cumulative PV": np.cumsum(pv_fcfs)
}))

st.bar_chart(pd.DataFrame({
    "Value": [sum(pv_fcfs), pv_terminal]
}, index=["Explicit FCF", "Terminal Value"]))