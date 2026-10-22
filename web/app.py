"""
ScanX Web: a personal, Chartink-style screener for any market (India, US, crypto, forex, commodities, world indices, or any Yahoo tickers).
Run locally:  streamlit run web/app.py      Hosted: Streamlit Community Cloud (free), deployed from GitHub.
Prices: Yahoo Finance via yfinance (end-of-day / delayed). Educational use only.
"""
import base64
import io
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import streamlit as st

import engine as E

st.set_page_config(page_title="ScanX Screener", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")
MOCK = os.environ.get("SCANX_MOCK") == "1"
ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}

st.markdown("""
<style>
.block-container{padding-top:1rem;padding-bottom:3rem;max-width:1200px}
h1{font-size:1.7rem!important;margin:0!important}
.sub{color:#6b7a8c;font-size:.85rem;margin:-.1rem 0 .6rem}
.regime{padding:.5rem .8rem;border-radius:.6rem;font-weight:600;font-size:.9rem;margin:.2rem 0 .6rem}
.on{background:rgba(11,122,85,.12);color:#0b7a55}.off{background:rgba(192,57,43,.12);color:#c0392b}
.clause{font-family:ui-monospace,Menlo,monospace;font-size:.82rem;background:rgba(31,79,209,.07);border-radius:.5rem;padding:.5rem .7rem;white-space:pre-wrap}
.card{border:1px solid rgba(128,128,128,.25);border-radius:.7rem;padding:.55rem .8rem;margin-bottom:.45rem}
.card .t{font-weight:700;font-size:1.02rem}.card .n{color:#6b7a8c;font-size:.78rem}
.card .r{display:flex;gap:.9rem;flex-wrap:wrap;font-size:.85rem;margin-top:.2rem;font-variant-numeric:tabular-nums}
.pos{color:#0b7a55}.neg{color:#c0392b}
.badge{display:inline-block;padding:0 .45rem;border-radius:.4rem;background:rgba(31,79,209,.12);color:#1f4fd1;font-weight:700;font-size:.8rem}
div[data-testid="stTextArea"] textarea{font-family:ui-monospace,Menlo,monospace;font-size:.85rem}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ markets and lists
DOW30 = "AAPL AMGN AMZN AXP BA CAT CRM CSCO CVX DIS GS HD HON IBM JNJ JPM KO MCD MMM MRK MSFT NKE NVDA PG SHW TRV UNH V VZ WMT".split()
NDX_FALLBACK = ("AAPL MSFT NVDA AMZN META AVGO GOOGL GOOG TSLA COST NFLX AMD PEP ADBE CSCO TMUS LIN INTU QCOM TXN AMGN ISRG CMCSA "
                "BKNG HON AMAT VRTX ADP PANW GILD SBUX MU ADI LRCX MELI KLAC INTC MDLZ CTAS REGN SNPS PDD CDNS PYPL MAR ABNB CRWD "
                "ORLY CSX FTNT MRVL ASML CEG DASH ROP ADSK WDAY NXPI PCAR TTD CPRT ROST MNST AEP PAYX CHTR KDP FAST ODFL DDOG "
                "KHC EXC VRSK CTSH EA FANG BKR GEHC XEL LULU CCEP TEAM IDXX CSGP AZN ZS ON DXCM ANSS TTWO BIIB WBD CDW GFS MDB ARM PLTR APP").split()
CRYPTO = ("BTC ETH BNB SOL XRP DOGE ADA TRX AVAX SHIB TON DOT LINK BCH LTC NEAR MATIC UNI ICP XLM ETC APT FIL ATOM HBAR ARB OP "
          "INJ VET MKR AAVE GRT ALGO SAND MANA AXS XTZ EOS THETA FTM").split()
FOREX = {"EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD", "USDJPY=X": "USD/JPY", "AUDUSD=X": "AUD/USD", "USDCAD=X": "USD/CAD",
         "USDCHF=X": "USD/CHF", "NZDUSD=X": "NZD/USD", "EURGBP=X": "EUR/GBP", "EURJPY=X": "EUR/JPY", "GBPJPY=X": "GBP/JPY",
         "AUDJPY=X": "AUD/JPY", "EURCHF=X": "EUR/CHF", "EURAUD=X": "EUR/AUD", "USDINR=X": "USD/INR", "EURINR=X": "EUR/INR",
         "GBPINR=X": "GBP/INR", "JPYINR=X": "JPY/INR", "USDCNY=X": "USD/CNY", "USDSGD=X": "USD/SGD", "USDHKD=X": "USD/HKD",
         "USDAED=X": "USD/AED", "USDZAR=X": "USD/ZAR", "USDMXN=X": "USD/MXN", "USDTRY=X": "USD/TRY"}
COMMOD = {"GC=F": "Gold", "SI=F": "Silver", "PL=F": "Platinum", "PA=F": "Palladium", "HG=F": "Copper", "ALI=F": "Aluminium",
          "CL=F": "Crude oil WTI", "BZ=F": "Brent crude", "NG=F": "Natural gas", "RB=F": "Gasoline", "HO=F": "Heating oil",
          "ZC=F": "Corn", "ZW=F": "Wheat", "ZS=F": "Soybeans", "ZM=F": "Soybean meal", "KC=F": "Coffee", "SB=F": "Sugar",
          "CT=F": "Cotton", "CC=F": "Cocoa", "OJ=F": "Orange juice", "LE=F": "Live cattle", "HE=F": "Lean hogs"}
WORLD = {"^NSEI": "Nifty 50", "^BSESN": "Sensex", "^NSEBANK": "Nifty Bank", "^CNXIT": "Nifty IT", "^GSPC": "S&P 500", "^DJI": "Dow Jones",
         "^IXIC": "Nasdaq", "^RUT": "Russell 2000", "^VIX": "VIX", "^FTSE": "FTSE 100", "^GDAXI": "DAX", "^FCHI": "CAC 40",
         "^STOXX50E": "Euro Stoxx 50", "^N225": "Nikkei 225", "^HSI": "Hang Seng", "000001.SS": "Shanghai", "^KS11": "KOSPI",
         "^TWII": "Taiwan", "^AXJO": "ASX 200", "^STI": "Singapore STI", "^JKSE": "Jakarta", "^BVSP": "Brazil Bovespa",
         "^GSPTSE": "Canada TSX", "^MXX": "Mexico IPC"}
NSE_CODES = {"Nifty 50": "a", "Nifty Next 50": "b", "Nifty 100": "c", "Nifty 200": "d", "Nifty 500": "e", "Nifty Midcap 150": "m",
             "Nifty Smallcap 250": "s", "Nifty Bank": "k", "Nifty IT": "i", "All NSE (Nifty Total Market)": "*"}
MARKETS = {
    "🇮🇳 India (NSE)": dict(lists=list(NSE_CODES), index="^NSEI", tv="NSE:", cur="₹", index_name="Nifty 50"),
    "🇺🇸 United States": dict(lists=["S&P 500", "Nasdaq 100", "Dow Jones 30"], index="^GSPC", tv="", cur="$", index_name="S&P 500"),
    "🪙 Crypto": dict(lists=["Top 40 coins (USD)"], index="BTC-USD", tv="CRYPTO:", cur="$", index_name="Bitcoin"),
    "💱 Forex": dict(lists=["Major and INR pairs"], index=None, tv="FX:", cur="", index_name=None),
    "🛢️ Commodities": dict(lists=["Futures (metals, energy, agri)"], index=None, tv="", cur="$", index_name=None),
    "🌍 World indices": dict(lists=["Major indices"], index=None, tv="", cur="", index_name=None),
    "🔧 Any tickers (custom)": dict(lists=["My list"], index=None, tv="", cur="", index_name=None),
}
TIMEFRAMES = {"15 min": ("15m", "60d"), "1 hour": ("60m", "360d"), "Daily": ("1d", "2y"), "Weekly": ("1wk", "8y"), "Monthly": ("1mo", "25y")}


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def nse_table():
    p = ROOT / "data" / "nse.csv"
    if p.exists():
        return pd.read_csv(p, dtype=str).fillna("")
    return pd.DataFrame(columns=["symbol", "name", "industry", "lists"])


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def universe(market: str, lst: str, custom: str = "") -> pd.DataFrame:
    """DataFrame[symbol, name, sector, yahoo]."""
    if MOCK:
        return pd.DataFrame({"symbol": [f"STK{i}" for i in range(80)], "name": [f"Demo Company {i}" for i in range(80)],
                             "sector": [["IT", "Banks", "Pharma", "Auto"][i % 4] for i in range(80)], "yahoo": [f"STK{i}" for i in range(80)]})
    if market.startswith("🇮🇳"):
        t = nse_table(); code = NSE_CODES[lst]
        if code != "*":
            t = t[t["lists"].str.contains(code, regex=False)]
        return pd.DataFrame({"symbol": t["symbol"], "name": t["name"], "sector": t["industry"], "yahoo": t["symbol"] + ".NS"})
    if market.startswith("🇺🇸"):
        if lst == "S&P 500":
            df = pd.read_csv("https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv")
            return pd.DataFrame({"symbol": df["Symbol"], "name": df["Security"], "sector": df["GICS Sector"], "yahoo": df["Symbol"].str.replace(".", "-", regex=False)})
        if lst == "Nasdaq 100":
            try:
                html = requests.get("https://en.wikipedia.org/wiki/Nasdaq-100", headers=UA, timeout=15).text
                for tb in pd.read_html(io.StringIO(html)):
                    cols = {c.lower(): c for c in tb.columns.astype(str)}
                    tk = cols.get("ticker") or cols.get("symbol")
                    if tk and len(tb) > 90:
                        nm = cols.get("company") or cols.get("security") or tk
                        sec = cols.get("gics sector") or cols.get("icb industry[14]") or cols.get("icb industry") or nm
                        return pd.DataFrame({"symbol": tb[tk], "name": tb[nm], "sector": tb[sec] if sec in tb else "", "yahoo": tb[tk].str.replace(".", "-", regex=False)})
            except Exception:
                pass
            return pd.DataFrame({"symbol": NDX_FALLBACK, "name": NDX_FALLBACK, "sector": "", "yahoo": NDX_FALLBACK})
        return pd.DataFrame({"symbol": DOW30, "name": DOW30, "sector": "", "yahoo": DOW30})
    if market.startswith("🪙"):
        return pd.DataFrame({"symbol": CRYPTO, "name": CRYPTO, "sector": "Crypto", "yahoo": [c + "-USD" for c in CRYPTO]})
    if market.startswith("💱"):
        return pd.DataFrame({"symbol": [v.replace("/", "") for v in FOREX.values()], "name": list(FOREX.values()), "sector": "Forex", "yahoo": list(FOREX)})
    if market.startswith("🛢️"):
        return pd.DataFrame({"symbol": list(COMMOD), "name": list(COMMOD.values()), "sector": "Commodity", "yahoo": list(COMMOD)})
    if market.startswith("🌍"):
        return pd.DataFrame({"symbol": list(WORLD), "name": list(WORLD.values()), "sector": "Index", "yahoo": list(WORLD)})
    ticks = [t.strip().upper() for t in custom.replace(",", " ").replace("\n", " ").split() if t.strip()]
    return pd.DataFrame({"symbol": ticks, "name": ticks, "sector": "", "yahoo": ticks})


def _mock(tickers, interval):
    n = {"15m": 900, "60m": 900, "1d": 500, "1wk": 400, "1mo": 240}[interval]
    freq = {"15m": "15min", "60m": "h", "1d": "B", "1wk": "W-MON", "1mo": "MS"}[interval]
    idx = pd.date_range(end=pd.Timestamp("2026-10-21"), periods=n, freq=freq)
    rng = np.random.default_rng(7); out = {}
    for t in tickers:
        c = 100 * np.exp(np.cumsum(rng.uniform(-0.001, 0.003) + 0.02 * rng.standard_normal(n)))
        o = c * (1 + 0.005 * rng.standard_normal(n)); h = np.maximum(o, c) * 1.01; l = np.minimum(o, c) * 0.99
        out[t] = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c, "Volume": rng.integers(1e5, 5e6, n).astype(float)}, index=idx)
    return {k.lower(): pd.DataFrame({t: out[t][k] for t in tickers}) for k in ["Open", "High", "Low", "Close", "Volume"]}


@st.cache_data(ttl=3600, show_spinner=False)
def prices(tickers: tuple, tf: str) -> dict:
    interval, period = TIMEFRAMES[tf]
    if MOCK:
        return _mock(tickers, interval)
    import yfinance as yf
    frames = []
    for k in range(0, len(tickers), 200):  # chunks keep Yahoo happy
        d = yf.download(list(tickers[k:k + 200]), period=period, interval=interval, auto_adjust=True, group_by="column", threads=True, progress=False)
        if d is None or d.empty:
            continue
        if not isinstance(d.columns, pd.MultiIndex):
            d.columns = pd.MultiIndex.from_product([d.columns, [tickers[k]]])
        frames.append(d)
    if not frames:
        return {}
    data = pd.concat(frames, axis=1)
    out = {f.lower(): data[f].copy() for f in ["Open", "High", "Low", "Close", "Volume"] if f in data.columns.get_level_values(0)}
    good = out["close"].columns[out["close"].notna().sum() > 25]
    return {k: v.reindex(columns=good).ffill(limit=3) for k, v in out.items()}


# ------------------------------------------------------------------ saved scans
TT_W = "close > sma(close, 30)\nclose > sma(close, 40)\nsma(close, 30) > sma(close, 40)\nsma(close, 40) > ago(sma(close, 40), 4)\nsma(close, 10) > sma(close, 30)\nclose >= 1.3 * low52\nclose >= 0.75 * high52\nrs >= 70"
PRESETS = {
    "— pick a ready-made scan —": None,
    "Leaders Pullback (our 1-week system)": dict(tf="Weekly", sort="Change %", asc=True, top=20, text="close > sma(close, 40)\nrs >= 80\nclose >= 0.75 * high52\nchange(1) < 0"),
    "SEPA Trend Template (weekly)": dict(tf="Weekly", sort="RS", asc=False, top=0, text=TT_W),
    "SEPA Breakout (weekly)": dict(tf="Weekly", sort="RS", asc=False, top=0, text=TT_W + "\nclose > ago(highest(high, 10), 1)\nclose <= 1.08 * ago(highest(high, 10), 1)"),
    "GMMA Bull Cross (weekly)": dict(tf="Weekly", sort="RS", asc=False, top=0, text="crossed_above(gmma_short, gmma_long)\nrs >= 70"),
    "Trend Template (daily 50/150/200)": dict(tf="Daily", sort="RS", asc=False, top=0, text="close > sma(close, 150)\nclose > sma(close, 200)\nsma(close, 150) > sma(close, 200)\nsma(close, 200) > ago(sma(close, 200), 21)\nsma(close, 50) > sma(close, 150)\nclose > sma(close, 50)\nclose >= 1.3 * low52\nclose >= 0.75 * high52\nrs >= 70"),
    "52-week high breakout + volume": dict(tf="Daily", sort="Volume ×", asc=False, top=0, text="close >= 0.98 * high52\nvolume > 1.5 * avg_volume(50)"),
    "Supertrend buy + MACD positive": dict(tf="Daily", sort="RS", asc=False, top=0, text="crossed_above(close, supertrend(10, 3))\nmacd() > macd_signal()"),
    "Golden cross (50/200)": dict(tf="Daily", sort="RS", asc=False, top=0, text="crossed_above(sma(close, 50), sma(close, 200))"),
    "RSI oversold in uptrend": dict(tf="Daily", sort="RSI", asc=True, top=0, text="close > sma(close, 200)\nrsi(14) < 35"),
    "Volume shocker": dict(tf="Daily", sort="Volume ×", asc=False, top=0, text="volume > 3 * avg_volume(20)\nchange(1) > 3"),
    "EMA 9/21 bull cross": dict(tf="Daily", sort="RS", asc=False, top=0, text="crossed_above(ema(close, 9), ema(close, 21))\nclose > sma(close, 50)"),
    "NR7 inside bar (squeeze)": dict(tf="Daily", sort="RS", asc=False, top=0, text="(high - low) <= lowest(high - low, 7)\nhigh < ago(high, 1)\nlow > ago(low, 1)\nclose > sma(close, 50)"),
    "Bollinger breakout": dict(tf="Daily", sort="Change %", asc=False, top=0, text="crossed_above(close, bb_upper(20, 2))\nvolume > 1.5 * avg_volume(20)"),
    "Strong trend (ADX > 25, +DI > -DI)": dict(tf="Daily", sort="RS", asc=False, top=0, text="adx(14) > 25\nplus_di(14) > minus_di(14)\nclose > ema(close, 21)"),
    "15-min opening breakout": dict(tf="15 min", sort="Change %", asc=False, top=0, text="close > highest(high, 20)\nvolume > 2 * avg_volume(20)\nclose > ema(close, 50)"),
}
SORTS = ["RS", "Change %", "Volume ×", "RSI", "Off 52-wk high %", "Symbol"]


def enc(d): return base64.urlsafe_b64encode(json.dumps(d).encode()).decode()
def dec(s):
    try:
        return json.loads(base64.urlsafe_b64decode(s.encode()).decode())
    except Exception:
        return None


ss = st.session_state
if "init" not in ss:
    ss.init = True
    ss.market = list(MARKETS)[0]; ss.lst = MARKETS[ss.market]["lists"][4]; ss.tf = "Weekly"; ss.mode = "all"
    ss.text = PRESETS["Leaders Pullback (our 1-week system)"]["text"]; ss.sort = "Change %"; ss.asc = True; ss.top = 20; ss.custom = "RELIANCE.NS TCS.NS AAPL MSFT BTC-USD GC=F 7203.T VOD.L"
    ss.mine = {}
    q = st.query_params.get("s")
    if q and (d := dec(q)):
        for k in ("market", "lst", "tf", "mode", "text", "sort", "asc", "top", "custom"):
            if k in d:
                ss[k] = d[k]
    ss.builder = pd.DataFrame([dict(indicator="Close", params="", bars_ago=0, condition="greater than", compare_to="SMA", value=1.0, params2="200", bars_ago2=0)])


def on_market():
    ss.lst = MARKETS[ss.market]["lists"][0 if not ss.market.startswith("🇮🇳") else 4]


def on_preset():
    p = PRESETS.get(ss.preset_pick)
    if p:
        ss.text = p["text"]; ss.tf = p["tf"]; ss.sort = p["sort"]; ss.asc = p["asc"]; ss.top = p["top"]


# ------------------------------------------------------------------ header + market picker
st.markdown("# 📈 ScanX")
st.markdown('<div class="sub">Personal Chartink-style screener for any market · India · US · crypto · forex · commodities · world indices · any Yahoo ticker</div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns([2, 2, 1])
c1.selectbox("Market", list(MARKETS), key="market", on_change=on_market)
if ss.lst not in MARKETS[ss.market]["lists"]:
    ss.lst = MARKETS[ss.market]["lists"][0]
c2.selectbox("List", MARKETS[ss.market]["lists"], key="lst")
c3.selectbox("Timeframe", list(TIMEFRAMES), key="tf")
if ss.market.startswith("🔧"):
    st.text_area("Yahoo Finance tickers (any exchange), separated by spaces or commas", key="custom", height=70,
                 help="Examples: RELIANCE.NS (NSE), 500325.BO (BSE), AAPL (US), VOD.L (London), 7203.T (Tokyo), BTC-USD, EURUSD=X, GC=F")

tab_scan, tab_bt, tab_chart, tab_saved, tab_help = st.tabs(["🔎 Screener", "🧪 Backtest", "📊 Chart", "⭐ My scans", "📚 Help"])

# ------------------------------------------------------------------ screener tab
with tab_scan:
    st.selectbox("Ready-made scans", list(PRESETS), key="preset_pick", on_change=on_preset)

    with st.expander("✨ Magic filter: type in plain English", expanded=False):
        mg = st.text_input("Example: up 4% + high volume, above 200 dma, rsi below 70", key="magic_text", label_visibility="visible")
        if st.button("Add to scan", key="magic_go"):
            lines, unknown = E.magic(mg)
            if lines:
                ss.text = (ss.text.rstrip() + "\n" if ss.text.strip() else "") + "\n".join(lines)
            if unknown:
                st.warning("Could not understand: " + ", ".join(unknown) + ". Use the filter builder or write it in the scan box.")
            st.rerun() if lines and not unknown else None

    with st.expander("🧱 Filter builder: pick indicators like Chartink", expanded=False):
        st.caption("Each row is one filter. For 'Number', Value is the number. For an indicator, Value is a multiplier (e.g. 0.95 × 52-week high). "
                   "'Bars ago' shifts the indicator back (1 = previous candle).")
        names = list(E.CATALOG)
        edited = st.data_editor(ss.builder, num_rows="dynamic", use_container_width=True, key="builder_editor", hide_index=True,
                                column_config={
                                    "indicator": st.column_config.SelectboxColumn("Indicator", options=names, required=True, width="medium"),
                                    "params": st.column_config.TextColumn("Params", help="e.g. 50 or 20, 2. Blank = default", width="small"),
                                    "bars_ago": st.column_config.NumberColumn("Bars ago", min_value=0, max_value=500, step=1, width="small"),
                                    "condition": st.column_config.SelectboxColumn("Condition", options=E.OPS, required=True, width="medium"),
                                    "compare_to": st.column_config.SelectboxColumn("Compare with", options=["Number"] + names, required=True, width="medium"),
                                    "value": st.column_config.NumberColumn("Value / ×", width="small"),
                                    "params2": st.column_config.TextColumn("Params", width="small"),
                                    "bars_ago2": st.column_config.NumberColumn("Bars ago", min_value=0, max_value=500, step=1, width="small"),
                                })
        preview = [ln for ln in (E.row_to_line(r) for r in edited.to_dict("records")) if ln]
        if preview:
            st.markdown('<div class="clause">' + "\n".join(preview) + "</div>", unsafe_allow_html=True)
        if st.button("Add these filters to scan", key="builder_go", disabled=not preview):
            ss.text = (ss.text.rstrip() + "\n" if ss.text.strip() else "") + "\n".join(preview)
            st.rerun()

    st.text_area("Scan conditions (one per line)", key="text", height=170,
                 help="Write like: close > sma(close, 200). See the Help tab for every indicator.")
    r1, r2, r3, r4 = st.columns([2, 2, 1.4, 1.2])
    r1.radio("Stock passes", ["all", "any"], key="mode", horizontal=True, format_func=lambda m: f"{m} of the filters")
    r2.selectbox("Sort by", SORTS, key="sort")
    r3.selectbox("Order", [False, True], key="asc", format_func=lambda a: "Low → high" if a else "High → low")
    r4.selectbox("Show", [0, 10, 20, 50, 100], key="top", format_func=lambda n: "All" if n == 0 else f"Top {n}")
    run = st.button("▶ Run scan", type="primary", use_container_width=True)


def load_all():
    m = MARKETS[ss.market]
    uni = universe(ss.market, ss.lst, ss.custom if ss.market.startswith("🔧") else "")
    tick = tuple(dict.fromkeys(uni["yahoo"].tolist() + ([m["index"]] if m["index"] and not MOCK else [])))
    with st.spinner(f"Downloading {len(tick)} symbols ({ss.tf})… first load of a big list takes about a minute"):
        P = prices(tick, ss.tf)
    if not P:
        return None
    P = {k: v.copy() for k, v in P.items()}
    idx = None
    if m["index"] and m["index"] in P["close"].columns:
        idx = P["close"][m["index"]].dropna()
        if m["index"] not in set(uni["yahoo"]):
            P = {k: v.drop(columns=m["index"], errors="ignore") for k, v in P.items()}
    return uni, P, idx


if run:
    st.query_params["s"] = enc({k: ss[k] for k in ("market", "lst", "tf", "mode", "text", "sort", "asc", "top", "custom")})
    ss.ran = True

if ss.get("ran"):
    res = load_all()
    with tab_scan:
        if res is None:
            st.error("No price data came back. Check the tickers or try again in a minute (Yahoo may be busy).")
        else:
            uni, P, idx = res
            ns = E.build_namespace(P, ss.tf)
            sig, errs = E.evaluate_frame(ss.text, ns, ss.mode)
            for e in errs:
                st.error("Fix this line: " + e)
            m = MARKETS[ss.market]
            if idx is not None and len(idx) > 50:
                n_ma = {"Weekly": 40, "Monthly": 10}.get(ss.tf, 200)
                ma = idx.rolling(n_ma).mean().iloc[-1]
                if not np.isnan(ma):
                    on = idx.iloc[-1] > ma
                    st.markdown(f'<div class="regime {"on" if on else "off"}">{"🟢" if on else "🔴"} {m["index_name"]} {idx.iloc[-1]:,.0f} is {"above" if on else "below"} its {n_ma}-bar average {ma:,.0f}</div>', unsafe_allow_html=True)
            c = ns["close"]; last = c.iloc[-1]
            hits = sig.iloc[-1]; hits = hits[hits].index
            meta = uni.drop_duplicates("yahoo").set_index("yahoo")
            g = lambda col, t: meta.loc[t, col] if t in meta.index else ""
            vol_x = (ns["volume"].iloc[-1] / ns["avg_volume"](50).iloc[-1].replace(0, np.nan))
            df = pd.DataFrame({
                "Symbol": [g("symbol", t) or t for t in hits], "Name": [g("name", t) for t in hits], "Sector": [g("sector", t) for t in hits],
                "Close": last[hits].values, "Change %": ns["change"](1).iloc[-1][hits].values, "RS": ns["rs"].iloc[-1][hits].values,
                "RSI": ns["rsi"](14).iloc[-1][hits].values, "Volume ×": vol_x[hits].values,
                "Off 52-wk high %": (100 * (1 - last / ns["high52"].iloc[-1]))[hits].values, "yahoo": list(hits)})
            df = df.sort_values(ss.sort, ascending=ss.asc, na_position="last")
            if ss.top:
                df = df.head(ss.top)
            ss.hits = df
            ss.last_scan = dict(text=ss.text, mode=ss.mode, tf=ss.tf, market=ss.market, lst=ss.lst)
            bar = c.index[-1]
            st.markdown(f"### {len(df)} match · {ss.lst} · {ss.tf} · last bar {bar:%d %b %Y %H:%M}" if ss.tf in ("15 min", "1 hour") else f"### {len(df)} match · {ss.lst} · {ss.tf} · last bar {bar:%d %b %Y}")
            st.caption(f"{c.shape[1]} symbols scanned. The latest bar can still be in progress during market hours.")
            tvp = m["tv"]
            def tv(row):
                s = str(row["Symbol"])
                if ss.market.startswith("🪙"): s = s + "USD"
                return "https://www.tradingview.com/chart/?symbol=" + tvp + s.replace("-", ".")
            if len(df):
                view = st.radio("View", ["Table", "Cards"], horizontal=True, label_visibility="collapsed", key="view")
                show = df.copy(); show.insert(1, "Chart", [tv(r) for _, r in df.iterrows()])
                show["Yahoo"] = ["https://finance.yahoo.com/quote/" + y for y in df["yahoo"]]
                if view == "Table":
                    st.dataframe(show.drop(columns=["yahoo"]), hide_index=True, use_container_width=True, column_config={
                        "Chart": st.column_config.LinkColumn("TradingView", display_text="open"),
                        "Yahoo": st.column_config.LinkColumn("Yahoo", display_text="open"),
                        "Close": st.column_config.NumberColumn(format="%.2f"), "Change %": st.column_config.NumberColumn(format="%.2f"),
                        "RS": st.column_config.NumberColumn(format="%.0f"), "RSI": st.column_config.NumberColumn(format="%.0f"),
                        "Volume ×": st.column_config.NumberColumn(format="%.1f"), "Off 52-wk high %": st.column_config.NumberColumn(format="%.1f")})
                else:
                    for _, r in show.head(150).iterrows():
                        ch = r["Change %"]; cls = "pos" if ch >= 0 else "neg"
                        st.markdown(f"""<div class="card"><div class="t"><a href="{r['Chart']}" target="_blank" style="text-decoration:none">{r['Symbol']}</a>
                        &nbsp;<span class="badge">RS {r['RS']:.0f}</span></div><div class="n">{r['Name']} · {r['Sector']}</div>
                        <div class="r"><span>{m['cur']}{r['Close']:,.2f}</span><span class="{cls}">{ch:+.2f}%</span><span>RSI {r['RSI']:.0f}</span>
                        <span>Vol {r['Volume ×']:.1f}×</span><span>{r['Off 52-wk high %']:.1f}% off high</span></div></div>""", unsafe_allow_html=True)
                st.download_button("⬇ Download results (CSV)", show.drop(columns=["yahoo"]).to_csv(index=False).encode(), "scanx_results.csv", "text/csv")
                st.code(",".join(tvp + (str(s) + ("USD" if ss.market.startswith("🪙") else "")).replace("-", ".") for s in df["Symbol"]), language=None)
                st.caption("Ticker list for a TradingView watchlist (Import list).")
            else:
                st.info("No symbols match right now. Loosen a filter, switch to 'any', or try another list.")

    # ------------------------------------------------------------------ backtest tab
    with tab_bt:
        if res is not None:
            uni, P, idx = res
            ns = E.build_namespace(P, ss.tf)
            sig, errs = E.evaluate_frame(ss.text, ns, ss.mode)
            b1, b2, b3 = st.columns(3)
            look = b1.selectbox("Look back", [60, 120, 250, 500, 1000], index=2, format_func=lambda n: f"last {n} bars")
            hold = b2.multiselect("Exit after (bars)", [1, 3, 5, 10, 20, 50], default=[5, 10, 20])
            fresh = b3.checkbox("Only first signal (no repeat within 10 bars)", value=True)
            c = ns["close"]
            s = sig.iloc[-look:].copy()
            if fresh:
                prev = sig.shift(1).rolling(10, min_periods=1).max().fillna(0).astype(bool).iloc[-look:]
                s = s & ~prev
            cnt = s.sum(axis=1)
            st.markdown(f"**{int(cnt.sum())} signals** in the last {look} bars · {ss.lst} · {ss.tf}")
            st.bar_chart(cnt.rename("Signals per bar"), height=180)
            rows = []
            for k in sorted(hold):
                fwd = (c.shift(-k) / c - 1) * 100
                vals = fwd.iloc[-look:][s].stack().dropna()
                if len(vals):
                    rows.append({"Exit after": f"{k} bars", "Trades": len(vals), "Avg return %": vals.mean(), "Median %": vals.median(),
                                 "Win rate %": 100 * (vals > 0).mean(), "Best %": vals.max(), "Worst %": vals.min()})
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, column_config={
                    k: st.column_config.NumberColumn(format="%.1f") for k in ["Avg return %", "Median %", "Win rate %", "Best %", "Worst %"]})
            ev = s.stack(); ev = ev[ev].reset_index().iloc[:, :2]; ev.columns = ["Date", "yahoo"]
            if len(ev):
                ev = ev.sort_values("Date", ascending=False).head(300)
                meta = uni.drop_duplicates("yahoo").set_index("yahoo")
                ev["Symbol"] = [meta.loc[t, "symbol"] if t in meta.index else t for t in ev["yahoo"]]
                ev["Price"] = [c.at[d, t] for d, t in zip(ev["Date"], ev["yahoo"])]
                for k in sorted(hold):
                    fk = (c.shift(-k) / c - 1) * 100
                    ev[f"{k}-bar %"] = [fk.at[d, t] for d, t in zip(ev["Date"], ev["yahoo"])]
                ev["Date"] = pd.to_datetime(ev["Date"]).dt.strftime("%d %b %Y %H:%M" if ss.tf in ("15 min", "1 hour") else "%d %b %Y")
                st.dataframe(ev.drop(columns=["yahoo"]), hide_index=True, use_container_width=True,
                             column_config={col: st.column_config.NumberColumn(format="%.2f") for col in ev.columns if col.endswith("%") or col == "Price"})
            st.caption("Each signal is bought at that bar's close and sold after the chosen number of bars. No costs, no stop-loss. "
                       "Uses today's index members, so results look better than reality (survivorship bias).")
        else:
            st.info("Run a scan first.")

    # ------------------------------------------------------------------ chart tab
    with tab_chart:
        hits = ss.get("hits")
        if res is None or hits is None or not len(hits):
            st.info("Run a scan, then pick a result here.")
        else:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            uni, P, idx = res
            sym = st.selectbox("Symbol", hits["Symbol"].tolist())
            yt = hits.loc[hits["Symbol"] == sym, "yahoo"].iloc[0]
            d = pd.DataFrame({k: P[k][yt] for k in ["open", "high", "low", "close", "volume"]}).dropna()
            lens = {"Weekly": (10, 30, 40), "Monthly": (6, 12, 24)}.get(ss.tf, (20, 50, 200))
            for L in lens:
                d[f"SMA {L}"] = d["close"].rolling(L).mean()
            n = {"15 min": 200, "1 hour": 200, "Daily": 180, "Weekly": 120, "Monthly": 120}[ss.tf]
            d = d.tail(n)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22], vertical_spacing=0.03)
            fig.add_trace(go.Candlestick(x=d.index, open=d["open"], high=d["high"], low=d["low"], close=d["close"], name=sym,
                                         increasing_line_color="#0b9e6f", decreasing_line_color="#d0453a", showlegend=False), 1, 1)
            for L, col in zip(lens, ["#1f77ff", "#ff9f1c", "#b388ff"]):
                fig.add_scatter(x=d.index, y=d[f"SMA {L}"], mode="lines", line=dict(width=1.5, color=col), name=f"SMA {L}", row=1, col=1)
            fig.add_bar(x=d.index, y=d["volume"], marker_color="rgba(120,130,150,.5)", name="Volume", showlegend=False, row=2, col=1)
            fig.update_layout(height=520, margin=dict(l=4, r=4, t=30, b=4), xaxis_rangeslider_visible=False, legend=dict(orientation="h", y=1.06, x=0))
            if ss.tf in ("Daily",):
                fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

if not ss.get("ran"):
    for _t in (tab_bt, tab_chart):
        with _t:
            st.info("Run a scan first (Screener tab).")

# ------------------------------------------------------------------ my scans tab
with tab_saved:
    st.markdown("Save scans for this visit, keep them as bookmarks, or download them as a file and upload it next time.")
    nm = st.text_input("Name for the current scan", key="save_name", placeholder="e.g. My breakout scan")
    if st.button("⭐ Save current scan", disabled=not nm):
        ss.mine[nm] = {k: ss[k] for k in ("market", "lst", "tf", "mode", "text", "sort", "asc", "top", "custom")}
        st.success(f"Saved “{nm}”.")
    for name, d in list(ss.mine.items()):
        a, b, c_ = st.columns([4, 1, 1])
        a.markdown(f"**{name}** · {d['market']} · {d['lst']} · {d['tf']}")
        if b.button("Load", key="ld_" + name):
            for k, v in d.items():
                ss[k] = v
            st.rerun()
        if c_.button("Delete", key="del_" + name):
            ss.mine.pop(name); st.rerun()
    st.download_button("⬇ Download my scans (scans.json)", json.dumps(ss.mine, indent=1).encode(), "scans.json", "application/json", disabled=not ss.mine)
    up = st.file_uploader("Upload scans.json", type="json")
    if up is not None and st.button("Import scans"):
        try:
            ss.mine.update(json.load(up)); st.success("Imported."); st.rerun()
        except Exception:
            st.error("That file is not a ScanX scans file.")
    st.divider()
    st.markdown("**Bookmark link for the current scan.** After you run a scan, the address bar holds the whole scan; bookmark it or share it.")
    host = st.context.headers.get("host", "") if hasattr(st, "context") else ""
    if host:
        st.code(f"https://{host}/?s={enc({k: ss[k] for k in ('market', 'lst', 'tf', 'mode', 'text', 'sort', 'asc', 'top', 'custom')})}", language=None)

# ------------------------------------------------------------------ help tab
with tab_help:
    st.markdown("""
**Write one condition per line.** By default a symbol must pass *all* lines; switch to *any* above the Run button.
You can also join conditions inside a line with `and`, `or`, `not` and brackets, and use ranges like `40 < rsi(14) < 60`.

| What | Write |
|---|---|
| Prices | `open` `high` `low` `close` `volume` |
| Moving averages | `sma(close, 50)` `ema(close, 21)` `wma(close, 20)` `avg_volume(20)` |
| Earlier candles | `ago(close, 1)` previous bar · `ago(sma(close, 40), 4)` |
| Highs / lows | `highest(high, 20)` `lowest(low, 10)` `high52` `low52` |
| Momentum | `change(1)` % change · `rsi(14)` · `macd()` `macd_signal()` `macd_hist()` · `stoch_k(14, 3)` `stoch_d()` · `willr(14)` · `cci(20)` · `mfi(14)` |
| Trend | `supertrend(10, 3)` · `adx(14)` `plus_di(14)` `minus_di(14)` · `gmma_short` `gmma_long` |
| Volatility | `atr(14)` · `bb_upper(20, 2)` `bb_lower(20, 2)` |
| Volume | `volume` · `avg_volume(20)` · `obv()` |
| Strength | `rs` RS rating 0–99 against the chosen list |
| Crosses | `crossed_above(ema(close, 9), ema(close, 21))` · `crossed_below(close, supertrend(10, 3))` |

**Examples**
- `close > 1.05 * ago(close, 5)` up 5% in 5 bars
- `(high52 - close) / high52 < 0.05` within 5% of the 52-week high
- `volume > 2 * avg_volume(20) and change(1) > 2` volume breakout
- `close > supertrend(10, 3) and adx(14) > 25` strong uptrend

**Magic filter** understands phrases like: *up 4%*, *down 3% in 5 days*, *high volume*, *volume 3x*, *above 200 dma*, *below 50 ema*,
*rsi above 60*, *oversold*, *52 week high*, *golden cross*, *death cross*, *macd crossover*, *supertrend positive*, *bollinger breakout*,
*gap up*, *inside bar*, *nr7*, *uptrend*, *strong trend*, *rs above 80*, *price above 100*, *green candle*.

**Timeframes**: 15 min (last 60 days), 1 hour (last year), daily (2 years), weekly (8 years), monthly (25 years).
**Any market**: choose *Any tickers (custom)* and type Yahoo symbols, e.g. `RELIANCE.NS`, `500325.BO`, `AAPL`, `VOD.L`, `7203.T`, `0700.HK`, `BTC-USD`, `EURUSD=X`, `GC=F`.

Data comes from Yahoo Finance (end-of-day or delayed), not a live exchange feed. Educational tool, not investment advice or a SEBI-registered recommendation.
""")
