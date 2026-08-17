"""Bundled NSE symbol -> company reference (offline, no external API)."""

COMPANY_MAP: dict[str, dict[str, str]] = {
    "RELIANCE.NS": {"name": "Reliance Industries", "sector": "Energy / Conglomerate"},
    "TCS.NS": {"name": "Tata Consultancy Services", "sector": "Information Technology"},
    "INFY.NS": {"name": "Infosys", "sector": "Information Technology"},
    "HDFCBANK.NS": {"name": "HDFC Bank", "sector": "Banking / Financials"},
    "SBIN.NS": {"name": "State Bank of India", "sector": "Banking / Financials"},
    "ICICIBANK.NS": {"name": "ICICI Bank", "sector": "Banking / Financials"},
    "AXISBANK.NS": {"name": "Axis Bank", "sector": "Banking / Financials"},
    "KOTAKBANK.NS": {"name": "Kotak Mahindra Bank", "sector": "Banking / Financials"},
    "HINDUNILVR.NS": {"name": "Hindustan Unilever", "sector": "FMCG"},
    "ITC.NS": {"name": "ITC", "sector": "FMCG"},
    "LT.NS": {"name": "Larsen & Toubro", "sector": "Infrastructure / Construction"},
    "HCLTECH.NS": {"name": "HCL Technologies", "sector": "Information Technology"},
    "WIPRO.NS": {"name": "Wipro", "sector": "Information Technology"},
    "BHARTIARTL.NS": {"name": "Bharti Airtel", "sector": "Telecom"},
    "ASIANPAINT.NS": {"name": "Asian Paints", "sector": "Consumer / Paints"},
    "MARUTI.NS": {"name": "Maruti Suzuki India", "sector": "Automobile"},
    "TATAMOTORS.NS": {"name": "Tata Motors", "sector": "Automobile"},
    "TATASTEEL.NS": {"name": "Tata Steel", "sector": "Metals / Steel"},
    "JSWSTEEL.NS": {"name": "JSW Steel", "sector": "Metals / Steel"},
    "SUNPHARMA.NS": {"name": "Sun Pharmaceutical", "sector": "Pharmaceuticals"},
    "DRREDDY.NS": {"name": "Dr. Reddy's Laboratories", "sector": "Pharmaceuticals"},
    "CIPLA.NS": {"name": "Cipla", "sector": "Pharmaceuticals"},
    "TITAN.NS": {"name": "Titan Company", "sector": "Consumer / Jewellery"},
    "BAJFINANCE.NS": {"name": "Bajaj Finance", "sector": "Financials / NBFC"},
    "ADANIENT.NS": {"name": "Adani Enterprises", "sector": "Conglomerate"},
    "NESTLEIND.NS": {"name": "Nestle India", "sector": "FMCG / Food"},
    "ULTRACEMCO.NS": {"name": "UltraTech Cement", "sector": "Cement"},
    "HDFCLIFE.NS": {"name": "HDFC Life Insurance", "sector": "Insurance"},
    "DMART.NS": {"name": "Avenue Supermarts (DMart)", "sector": "Retail"},
    "ADANIPORTS.NS": {"name": "Adani Ports & SEZ", "sector": "Ports / Logistics"},
    "INDIGO.NS": {"name": "InterGlobe Aviation (IndiGo)", "sector": "Aviation"},
    "BANKNIFTY.NS": {"name": "Nifty Bank", "sector": "Index"},
    "NIFTY50.NS": {"name": "Nifty 50", "sector": "Index"},
}


def company_for(symbol: str) -> dict[str, str]:
    """Return company reference for a symbol, or a symbol-based fallback."""
    return COMPANY_MAP.get(symbol, {"name": symbol.replace(".NS", ""), "sector": "Unknown"})


def add_company(symbol: str, name: str, sector: str = "Unknown") -> None:
    COMPANY_MAP[symbol] = {"name": name, "sector": sector}
