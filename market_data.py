import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta

@st.cache_data(ttl=120)
def get_stock_price(ticker: str):
    """Busca cotação atual na B3 via Yahoo Finance (com cache de 2 minutos)."""
    formatted_ticker = ticker.strip().upper()
    if not formatted_ticker.endswith(".SA"):
        formatted_ticker += ".SA"
    try:
        data = yf.Ticker(formatted_ticker)
        history = data.history(period="1d")
        if not history.empty:
            return float(history["Close"].iloc[-1])
        return None
    except Exception:
        return None

@st.cache_data(ttl=600)
def get_historical_data(ticker: str, period="6mo"):
    """Busca histórico de preços para gerar o gráfico de cotações."""
    formatted_ticker = ticker.strip().upper()
    if not formatted_ticker.endswith(".SA"):
        formatted_ticker += ".SA"
    try:
        data = yf.Ticker(formatted_ticker)
        return data.history(period=period)
    except Exception:
        return pd.DataFrame()

def get_recent_dividends(ticker: str, days: int = 30):
    """Busca proventos (dividendos e JCP) distribuídos recentemente pelo ativo."""
    formatted_ticker = ticker.strip().upper()
    if not formatted_ticker.endswith(".SA"):
        formatted_ticker += ".SA"
    try:
        data = yf.Ticker(formatted_ticker)
        divs = data.dividends
        if divs.empty:
            return []
        
        # Converte o fuso horário para UTC/ingênuo para comparação correta
        divs.index = divs.index.tz_localize(None) if divs.index.tz is not None else divs.index
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        recent = divs[divs.index >= cutoff_date]
        
        events = []
        for date, amount in recent.items():
            events.append({"date": date, "amount": float(amount)})
        return events
    except Exception:
        return []

def calculate_sharpe_ratio(returns_series: pd.Series, risk_free_rate: float = 0.1075) -> float:
    """Calcula o Índice de Sharpe anualizado considerando o CDI."""
    if len(returns_series) < 5 or returns_series.std() == 0:
        return 0.0
    daily_rf = (1 + risk_free_rate) ** (1 / 252) - 1
    excess_returns = returns_series - daily_rf
    sharpe = np.sqrt(252) * (excess_returns.mean() / returns_series.std())
    return round(float(sharpe), 2)

def generate_synthetic_book(ticker: str, current_price: float):
    """Gera o Book de Ofertas em torno da cotação de mercado."""
    if not current_price:
        return pd.DataFrame(), pd.DataFrame()
    
    bids = [{"Preço Compra (R$)": round(current_price * (1 - 0.002 * i), 2), "Qtd": i * 200} for i in range(1, 6)]
    asks = [{"Preço Venda (R$)": round(current_price * (1 + 0.002 * i), 2), "Qtd": i * 200} for i in range(1, 6)]
        
    return pd.DataFrame(bids), pd.DataFrame(asks)