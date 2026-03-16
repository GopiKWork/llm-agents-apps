"""
Yahoo Finance Tool - Strands module-based tool for fetching financial data.
Uses yfinance library to get stock prices, company info, financials,
analyst recommendations, historical prices, and news.
"""

import json
from typing import Any

try:
    import yfinance as yf
except ImportError:
    raise ImportError("`yfinance` not installed. Please install using `pip install yfinance`.")


# ============================================================================
# Response helpers
# ============================================================================

def _ok(tid: str, text: str) -> dict:
    return {"toolUseId": tid, "status": "success", "content": [{"text": text}]}


def _error(tid: str, text: str) -> dict:
    return {"toolUseId": tid, "status": "error", "content": [{"text": text}]}


def _require(inp: dict, tid: str, *keys: str):
    """Return error dict if any required key is missing, else None."""
    for k in keys:
        if not inp.get(k):
            return _error(tid, f"Error: {k} is required")
    return None


# ============================================================================
# Action handlers
# ============================================================================

def _stock_price(inp: dict, tid: str) -> dict:
    symbol = inp["symbol"]
    stock = yf.Ticker(symbol)
    info = stock.info
    price = info.get("regularMarketPrice") or info.get("currentPrice")
    if price is None:
        return _error(tid, f"Could not fetch price for {symbol}")
    currency = info.get("currency", "USD")
    prev_close = info.get("regularMarketPreviousClose")
    lines = [f"{symbol}: {price:.4f} {currency}"]
    if prev_close:
        change = price - prev_close
        pct = (change / prev_close) * 100
        lines.append(f"Change: {change:+.4f} ({pct:+.2f}%)")
    return _ok(tid, "\n".join(lines))


def _company_info(inp: dict, tid: str) -> dict:
    symbol = inp["symbol"]
    info = yf.Ticker(symbol).info
    if not info:
        return _error(tid, f"Could not fetch company info for {symbol}")
    cleaned = {
        "Name": info.get("shortName"),
        "Symbol": info.get("symbol"),
        "Price": f"{info.get('regularMarketPrice', info.get('currentPrice'))} {info.get('currency', 'USD')}",
        "Market Cap": info.get("marketCap"),
        "Sector": info.get("sector"),
        "Industry": info.get("industry"),
        "Country": info.get("country"),
        "Employees": info.get("fullTimeEmployees"),
        "Website": info.get("website"),
        "Summary": info.get("longBusinessSummary"),
        "EPS": info.get("trailingEps"),
        "P/E Ratio": info.get("trailingPE"),
        "52 Week High": info.get("fiftyTwoWeekHigh"),
        "52 Week Low": info.get("fiftyTwoWeekLow"),
        "50 Day Average": info.get("fiftyDayAverage"),
        "200 Day Average": info.get("twoHundredDayAverage"),
        "Dividend Yield": info.get("dividendYield"),
        "Analyst Recommendation": info.get("recommendationKey"),
    }
    return _ok(tid, json.dumps({k: v for k, v in cleaned.items() if v is not None}, indent=2))


def _stock_fundamentals(inp: dict, tid: str) -> dict:
    symbol = inp["symbol"]
    info = yf.Ticker(symbol).info
    fundamentals = {
        "symbol": symbol,
        "company_name": info.get("longName", ""),
        "sector": info.get("sector", ""),
        "industry": info.get("industry", ""),
        "market_cap": info.get("marketCap", "N/A"),
        "pe_ratio": info.get("forwardPE", "N/A"),
        "pb_ratio": info.get("priceToBook", "N/A"),
        "dividend_yield": info.get("dividendYield", "N/A"),
        "eps": info.get("trailingEps", "N/A"),
        "beta": info.get("beta", "N/A"),
        "52_week_high": info.get("fiftyTwoWeekHigh", "N/A"),
        "52_week_low": info.get("fiftyTwoWeekLow", "N/A"),
    }
    return _ok(tid, json.dumps(fundamentals, indent=2))


def _income_statements(inp: dict, tid: str) -> dict:
    symbol = inp["symbol"]
    stock = yf.Ticker(symbol)
    financials = stock.financials
    if financials is None or financials.empty:
        return _error(tid, f"No income statement data for {symbol}")
    return _ok(tid, financials.to_string())


def _analyst_recommendations(inp: dict, tid: str) -> dict:
    symbol = inp["symbol"]
    recs = yf.Ticker(symbol).recommendations
    if recs is None or recs.empty:
        return _error(tid, f"No analyst recommendations for {symbol}")
    return _ok(tid, recs.head(10).to_string())


def _historical_prices(inp: dict, tid: str) -> dict:
    symbol = inp["symbol"]
    period = inp.get("period", "1mo")
    interval = inp.get("interval", "1d")
    hist = yf.Ticker(symbol).history(period=period, interval=interval)
    if hist.empty:
        return _error(tid, f"No historical data for {symbol} (period={period}, interval={interval})")
    return _ok(tid, hist.to_string())


def _company_news(inp: dict, tid: str) -> dict:
    symbol = inp["symbol"]
    num = inp.get("num_stories", 5)
    news = yf.Ticker(symbol).news
    if not news:
        return _error(tid, f"No news found for {symbol}")
    stories = news[:num]
    lines = []
    for item in stories:
        title = item.get("title", item.get("content", {}).get("title", "N/A"))
        link = item.get("link", item.get("content", {}).get("canonicalUrl", {}).get("url", ""))
        publisher = item.get("publisher", item.get("content", {}).get("provider", {}).get("displayName", ""))
        lines.append(f"- {title}")
        if publisher:
            lines.append(f"  Source: {publisher}")
        if link:
            lines.append(f"  Link: {link}")
    return _ok(tid, "\n".join(lines) if lines else "No news available")


def _technical_indicators(inp: dict, tid: str) -> dict:
    symbol = inp["symbol"]
    period = inp.get("period", "3mo")
    hist = yf.Ticker(symbol).history(period=period)
    if hist.empty:
        return _error(tid, f"No data for {symbol}")
    sma_20 = hist["Close"].rolling(window=20).mean()
    sma_50 = hist["Close"].rolling(window=50).mean()
    rsi = _compute_rsi(hist["Close"])
    latest = hist.iloc[-1]
    lines = [
        f"Technical Indicators for {symbol} ({period})",
        f"Latest Close: {latest['Close']:.4f}",
        f"Volume: {int(latest['Volume'])}",
        f"SMA 20: {sma_20.iloc[-1]:.4f}" if len(sma_20.dropna()) > 0 else "SMA 20: N/A",
        f"SMA 50: {sma_50.iloc[-1]:.4f}" if len(sma_50.dropna()) > 0 else "SMA 50: N/A",
        f"RSI 14: {rsi.iloc[-1]:.2f}" if len(rsi.dropna()) > 0 else "RSI 14: N/A",
    ]
    return _ok(tid, "\n".join(lines))


def _compute_rsi(series, window: int = 14):
    """Compute RSI from a price series."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


# ============================================================================
# TOOL_SPEC and entry point
# ============================================================================

TOOL_SPEC = {
    "name": "yfinance_tool",
    "description": (
        "Yahoo Finance tool for fetching financial data.\n\n"
        "Actions:\n"
        "- stock_price: Get current stock price\n"
        "- company_info: Get company profile and overview\n"
        "- stock_fundamentals: Get fundamental data (PE, EPS, market cap, etc.)\n"
        "- income_statements: Get income statement data\n"
        "- analyst_recommendations: Get analyst recommendations\n"
        "- historical_prices: Get historical OHLCV data\n"
        "- company_news: Get recent company news\n"
        "- technical_indicators: Get technical indicators (SMA, RSI)\n"
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform",
                    "enum": [
                        "stock_price", "company_info", "stock_fundamentals",
                        "income_statements", "analyst_recommendations",
                        "historical_prices", "company_news", "technical_indicators",
                    ],
                },
                "symbol": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL, MSFT)"},
                "period": {
                    "type": "string",
                    "description": "Time period: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max (default: 1mo for historical, 3mo for technical)",
                },
                "interval": {
                    "type": "string",
                    "description": "Data interval: 1d,5d,1wk,1mo,3mo (default: 1d)",
                },
                "num_stories": {
                    "type": "integer",
                    "description": "Number of news stories to return (default: 5)",
                },
            },
            "required": ["action", "symbol"],
        }
    },
}

_ACTIONS = {
    "stock_price": _stock_price,
    "company_info": _company_info,
    "stock_fundamentals": _stock_fundamentals,
    "income_statements": _income_statements,
    "analyst_recommendations": _analyst_recommendations,
    "historical_prices": _historical_prices,
    "company_news": _company_news,
    "technical_indicators": _technical_indicators,
}


def yfinance_tool(tool: dict, **kwargs: Any) -> dict:
    """Yahoo Finance tool: fetch stock data, financials, news, and indicators."""
    try:
        tid = tool.get("toolUseId", "default-id")
        inp = tool.get("input", {})
        action = inp.get("action")
        if not action:
            return _error(tid, "Error: action is required")

        err = _require(inp, tid, "symbol")
        if err:
            return err

        handler = _ACTIONS.get(action)
        if not handler:
            return _error(tid, f"Error: Unknown action '{action}'")

        return handler(inp, tid)

    except Exception as e:
        return _error(tool.get("toolUseId", "default-id"), f"Error: {str(e)}")
