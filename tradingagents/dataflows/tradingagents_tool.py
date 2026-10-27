"""Optional LangChain adapter; copy technical.py alongside this file in dataflows."""
import json
from datetime import datetime, timedelta
from langchain_core.tools import tool
from tradingagents.dataflows.technical import analyze

@tool
def get_portfolio_technical_report(symbol: str, as_of: str) -> str:
    """Return a read-only technical report for symbol through inclusive as_of (YYYY-MM-DD). Uses daily Yahoo data; no orders."""
    import yfinance as yf
    day=datetime.strptime(as_of,'%Y-%m-%d')
    start=(day-timedelta(days=730)).strftime('%Y-%m-%d')
    end=(day+timedelta(days=1)).strftime('%Y-%m-%d')
    try:
        df=yf.Ticker(symbol).history(start=start,end=end,auto_adjust=False,actions=True,raise_errors=True)
        if df.empty: return f'No price data available for {symbol} through {as_of}.'
        result=analyze(df,as_of=as_of)
        result['ticker']=symbol.upper()
        result['price_basis']='Yahoo OHLC auto_adjust=False; usually split-adjusted and not dividend-adjusted; verify provider.'
        result['warnings'].append('Daily bars may be incomplete when called before the market close; verify timestamp and corporate actions.')
        return json.dumps(result,ensure_ascii=False,allow_nan=False)
    except Exception as exc:
        return f'Technical data unavailable for {symbol}: {type(exc).__name__}: {exc}'
