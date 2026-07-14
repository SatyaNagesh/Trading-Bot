"""QuantLab AI Dashboard — Streamlit multi-page app."""

import asyncio
from datetime import date, timedelta

import streamlit as st
import httpx

BACKEND = "http://localhost:8000"

st.set_page_config(page_title="QuantLab AI", layout="wide")
st.title("QuantLab AI — Quantitative Research OS")

if "symbol" not in st.session_state:
    st.session_state.symbol = "RELIANCE.NS"
if "start" not in st.session_state:
    st.session_state.start = date.today() - timedelta(days=365)
if "end" not in st.session_state:
    st.session_state.end = date.today()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Market Data", "Backtest", "Strategies", "Hypotheses", "Research",
])

with tab1:
    st.subheader("Fetch Market Data")
    col1, col2, col3 = st.columns(3)
    with col1:
        symbol = st.text_input("Symbol", value=st.session_state.symbol, key="fetch_symbol")
    with col2:
        start = st.date_input("Start", value=st.session_state.start, key="fetch_start")
    with col3:
        end = st.date_input("End", value=st.session_state.end, key="fetch_end")
    if st.button("Fetch Data"):
        with st.spinner("Fetching..."):
            async def fetch():
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{BACKEND}/data/{symbol}",
                        params={"start": start.isoformat(), "end": end.isoformat()},
                    )
                    return resp.json()
            data = asyncio.run(fetch())
        st.success(f"Got {len(data.get('bars', []))} bars")
        st.dataframe(data.get("bars", []))

with tab2:
    st.subheader("Run Backtest")
    strategy_input = st.text_area("Strategy Code (Python)", value="# SMA Crossover\n")
    if st.button("Run Backtest"):
        with st.spinner("Running..."):
            async def run_bt():
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{BACKEND}/strategies/validate",
                        json={"name": "custom", "dsl": strategy_input},
                    )
                    return resp.json()
            result = asyncio.run(run_bt())
        st.json(result)

with tab3:
    st.subheader("Strategies")
    async def list_strategies():
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BACKEND}/strategies")
            return resp.json()
    strategies = asyncio.run(list_strategies())
    st.dataframe(strategies)

with tab4:
    st.subheader("Hypotheses")
    async def list_hypotheses():
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BACKEND}/hypotheses")
            return resp.json()
    hypotheses = asyncio.run(list_hypotheses())
    st.dataframe(hypotheses)

with tab5:
    st.subheader("Research Assistant")
    query = st.text_input("Research Question")
    if st.button("Submit") and query:
        st.info(f"Research query submitted: {query}")
