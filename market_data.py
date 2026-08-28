import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta

@st.cache_data(ttl=120)
def get_stock_price(ticker: str):
    """Busca cotação nominal atual na B3 via Yahoo Finance (sem ajuste retroativo)."""
    if not ticker:
        return None
    formatted_ticker = ticker.strip().upper()
    if not formatted_ticker.endswith(".SA"):
        formatted_ticker += ".SA"
    try:
        data = yf.Ticker(formatted_ticker)
        history = data.history(period="1d", auto_adjust=False)
        if not history.empty:
            return float(history["Close"].iloc[-1])
        return None
    except Exception:
        return None

@st.cache_data(ttl=600)
def get_historical_data(ticker: str, period="6mo"):
    """Busca histórico de preços nominais para gerar gráfico de velas."""
    if not ticker:
        return pd.DataFrame()
    formatted_ticker = ticker.strip().upper()
    if not formatted_ticker.endswith(".SA"):
        formatted_ticker += ".SA"
    try:
        data = yf.Ticker(formatted_ticker)
        return data.history(period=period, auto_adjust=False)
    except Exception:
        return pd.DataFrame()

def get_recent_dividends(ticker: str, days: int = 30):
    """Busca proventos recentes na B3."""
    if not ticker:
        return []
    formatted_ticker = ticker.strip().upper()
    if not formatted_ticker.endswith(".SA"):
        formatted_ticker += ".SA"
    try:
        data = yf.Ticker(formatted_ticker)
        divs = data.dividends
        if divs.empty:
            return []
        
        divs.index = divs.index.tz_localize(None) if divs.index.tz is not None else divs.index
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        recent = divs[divs.index >= cutoff_date]
        
        events = []
        for date, amount in recent.items():
            events.append({"date": date, "amount": float(amount)})
        return events
    except Exception:
        return []

def generate_synthetic_book(ticker: str, current_price: float):
    """Gera Book de Ofertas simplificado em torno do preço de mercado."""
    if not current_price:
        return pd.DataFrame(), pd.DataFrame()
    
    bids = [{"Preço Compra (R$)": round(current_price * (1 - 0.002 * i), 2), "Qtd": i * 200} for i in range(1, 6)]
    asks = [{"Preço Venda (R$)": round(current_price * (1 + 0.002 * i), 2), "Qtd": i * 200} for i in range(1, 6)]
        
    return pd.DataFrame(bids), pd.DataFrame(asks)