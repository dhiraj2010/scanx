"""ScanX scan engine: Chartink-style conditions evaluated on wide price tables (rows = bars, columns = symbols)."""
import ast
import re
import numpy as np
import pandas as pd

BARS_PER_YEAR = {"15 min": 6300, "1 hour": 1764, "Daily": 252, "Weekly": 52, "Monthly": 12}


def build_namespace(P: dict, tf: str) -> dict:
    o, h, l, c, v = P["open"], P["high"], P["low"], P["close"], P["volume"]
    yr = BARS_PER_YEAR.get(tf, 252)

    def _f(x):
        return x if isinstance(x, (pd.DataFrame, pd.Series)) else x

    def sma(x, n=20): return x.rolling(int(n), min_periods=int(n)).mean()
    def ema(x, n=20): return x.ewm(span=int(n), adjust=False, min_periods=int(n)).mean()
    def wma(x, n=20):
        w = np.arange(1, int(n) + 1)
        return x.rolling(int(n)).apply(lambda a: np.dot(a, w) / w.sum(), raw=True)
    def highest(x, n=20): return x.rolling(int(n), min_periods=1).max()
    def lowest(x, n=20): return x.rolling(int(n), min_periods=1).min()
    def ago(x, k=1): return x.shift(int(k))
    def change(n=1): return 100 * (c / c.shift(int(n)) - 1)
    def avg_volume(n=20): return sma(v, n)
    def _rma(x, n): return x.ewm(alpha=1 / n, adjust=False, min_periods=int(n)).mean()
    def rsi(n=14, x=None):
        x = c if x is None else x
        d = x.diff()
        up, dn = _rma(d.clip(lower=0), n), _rma(-d.clip(upper=0), n)
        return 100 - 100 / (1 + up / dn.replace(0, np.nan))
    def _tr():
        pc = c.shift()
        return np.maximum(np.maximum(h - l, (h - pc).abs()), (l - pc).abs())
    def atr(n=14): return _rma(_tr(), n)
    def crossed_above(a, b):
        bp = b.shift(1) if isinstance(b, (pd.DataFrame, pd.Series)) else b
        return (a > b) & (a.shift(1) <= bp)
    def crossed_below(a, b):
        bp = b.shift(1) if isinstance(b, (pd.DataFrame, pd.Series)) else b
        return (a < b) & (a.shift(1) >= bp)
    def macd(fast=12, slow=26): return ema(c, fast) - ema(c, slow)
    def macd_signal(fast=12, slow=26, sig=9): return ema(macd(fast, slow), sig)
    def macd_hist(fast=12, slow=26, sig=9): return macd(fast, slow) - macd_signal(fast, slow, sig)
    def bb_upper(n=20, k=2): return sma(c, n) + k * c.rolling(int(n)).std()
    def bb_lower(n=20, k=2): return sma(c, n) - k * c.rolling(int(n)).std()
    def stoch_k(n=14, smooth=3):
        lo, hi = lowest(l, n), highest(h, n)
        return sma(100 * (c - lo) / (hi - lo).replace(0, np.nan), smooth)
    def stoch_d(n=14, smooth=3, d=3): return sma(stoch_k(n, smooth), d)
    def willr(n=14):
        lo, hi = lowest(l, n), highest(h, n)
        return -100 * (hi - c) / (hi - lo).replace(0, np.nan)
    def cci(n=20):
        tp = (h + l + c) / 3
        md = tp.rolling(int(n)).apply(lambda a: np.mean(np.abs(a - a.mean())), raw=True)
        return (tp - sma(tp, n)) / (0.015 * md)
    def mfi(n=14):
        tp = (h + l + c) / 3; mf = tp * v; up = tp > tp.shift()
        pos = mf.where(up, 0).rolling(int(n)).sum(); neg = mf.where(~up, 0).rolling(int(n)).sum()
        return 100 - 100 / (1 + pos / neg.replace(0, np.nan))
    def obv(): return (np.sign(c.diff()).fillna(0) * v).cumsum()
    def adx(n=14):
        upm, dnm = h.diff(), -l.diff()
        pdm = upm.where((upm > dnm) & (upm > 0), 0.0); ndm = dnm.where((dnm > upm) & (dnm > 0), 0.0)
        tr = _rma(_tr(), n)
        pdi, ndi = 100 * _rma(pdm, n) / tr, 100 * _rma(ndm, n) / tr
        dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
        return _rma(dx, n)
    def plus_di(n=14):
        upm, dnm = h.diff(), -l.diff(); pdm = upm.where((upm > dnm) & (upm > 0), 0.0)
        return 100 * _rma(pdm, n) / _rma(_tr(), n)
    def minus_di(n=14):
        upm, dnm = h.diff(), -l.diff(); ndm = dnm.where((dnm > upm) & (dnm > 0), 0.0)
        return 100 * _rma(ndm, n) / _rma(_tr(), n)
    def supertrend(n=10, mult=3):
        a = atr(n); hl2 = (h + l) / 2
        ub, lb = (hl2 + mult * a).values, (hl2 - mult * a).values
        cl = c.values; rows, cols = cl.shape
        st_ = np.full((rows, cols), np.nan); fu = ub.copy(); fl = lb.copy(); up = np.ones(cols, bool)
        for i in range(1, rows):
            pfu, pfl = fu[i - 1], fl[i - 1]
            fu[i] = np.where(np.isnan(pfu) | (ub[i] < pfu) | (cl[i - 1] > pfu), ub[i], pfu)
            fl[i] = np.where(np.isnan(pfl) | (lb[i] > pfl) | (cl[i - 1] < pfl), lb[i], pfl)
            up = np.where(cl[i] > fu[i - 1], True, np.where(cl[i] < fl[i - 1], False, up))
            st_[i] = np.where(up, fl[i], fu[i])
        return pd.DataFrame(st_, index=c.index, columns=c.columns)

    q = max(1, yr // 4)
    wr = 0.4 * (c / c.shift(q) - 1) + 0.2 * (c / c.shift(2 * q) - 1) + 0.2 * (c / c.shift(3 * q) - 1) + 0.2 * (c / c.shift(4 * q) - 1)
    rs = wr.rank(axis=1, pct=True) * 99
    g_s = sum(ema(c, n) for n in (3, 5, 8, 10, 12, 15)) / 6
    g_l = sum(ema(c, n) for n in (30, 35, 40, 45, 50, 60)) / 6
    return dict(open=o, high=h, low=l, close=c, volume=v, sma=sma, ema=ema, wma=wma, highest=highest, lowest=lowest, ago=ago,
                change=change, roc=change, avg_volume=avg_volume, rsi=rsi, atr=atr, crossed_above=crossed_above, crossed_below=crossed_below,
                macd=macd, macd_signal=macd_signal, macd_hist=macd_hist, bb_upper=bb_upper, bb_lower=bb_lower, stoch_k=stoch_k,
                stoch_d=stoch_d, willr=willr, cci=cci, mfi=mfi, obv=obv, adx=adx, plus_di=plus_di, minus_di=minus_di,
                supertrend=supertrend, rs=rs, high52=highest(h, yr), low52=lowest(l, yr), gmma_short=g_s, gmma_long=g_l,
                abs=abs, min=np.minimum, max=np.maximum)


ALLOWED = (ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare, ast.Call, ast.Name, ast.Load, ast.Constant,
           ast.And, ast.Or, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.USub, ast.UAdd, ast.Not,
           ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.Eq, ast.NotEq, ast.BitAnd, ast.BitOr)


class _Bool(ast.NodeTransformer):
    def visit_BoolOp(self, node):
        self.generic_visit(node)
        op = ast.BitAnd() if isinstance(node.op, ast.And) else ast.BitOr()
        out = node.values[0]
        for v in node.values[1:]:
            out = ast.BinOp(left=out, op=op, right=v)
        return out

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        return ast.UnaryOp(op=ast.Invert(), operand=node.operand) if isinstance(node.op, ast.Not) else node

    def visit_Compare(self, node):
        self.generic_visit(node)
        if len(node.ops) == 1:
            return node
        parts, left = [], node.left
        for op, right in zip(node.ops, node.comparators):
            parts.append(ast.Compare(left=left, ops=[op], comparators=[right])); left = right
        out = parts[0]
        for p in parts[1:]:
            out = ast.BinOp(left=out, op=ast.BitAnd(), right=p)
        return out


def compile_condition(text: str):
    text = text.replace("≥", ">=").replace("≤", "<=")
    text = re.sub(r"(?<![<>!=])=(?!=)", "==", text)
    tree = ast.parse(text, mode="eval")
    for n in ast.walk(tree):
        if not isinstance(n, ALLOWED):
            raise ValueError(f"'{type(n).__name__}' is not allowed in a scan")
        if isinstance(n, ast.Call) and not isinstance(n.func, ast.Name):
            raise ValueError("Only plain functions like sma(close, 50) are allowed")
        if isinstance(n, ast.Name) and n.id.startswith("_"):
            raise ValueError("Names cannot start with _")
    tree = ast.fix_missing_locations(_Bool().visit(tree))
    return compile(tree, "<scan>", "eval")


def split_lines(text: str):
    return [ln.split("#")[0].strip() for ln in text.splitlines() if ln.split("#")[0].strip()]


def evaluate_frame(text: str, ns: dict, mode: str = "all"):
    """Returns (DataFrame of True/False for every bar and symbol, list of error messages)."""
    c = ns["close"]
    acc = None
    errs = []
    for cond in split_lines(text):
        try:
            r = eval(compile_condition(cond), {"__builtins__": {}}, {k.lower(): val for k, val in ns.items()})  # noqa: S307
            if isinstance(r, (bool, np.bool_)):
                r = pd.DataFrame(bool(r), index=c.index, columns=c.columns)
            if not isinstance(r, pd.DataFrame):
                errs.append(f"Not a true/false condition: {cond}"); continue
            r = r.reindex(index=c.index, columns=c.columns).fillna(False).astype(bool)
            acc = r if acc is None else (acc & r if mode == "all" else acc | r)
        except Exception as e:  # noqa: BLE001
            errs.append(f"{cond}  →  {e}")
    if acc is None or errs:
        acc = pd.DataFrame(False, index=c.index, columns=c.columns)
    return acc, errs


# ------------------------------------------------------------------ magic filters (plain-English → conditions)
_MA = r"(sma|ema|dma|ma|moving average)"


def magic(text: str):
    """Turn phrases like 'up 4% + high volume, above 200 dma, rsi below 30' into scan lines."""
    out, unknown = [], []
    parts = [p.strip() for p in re.split(r"\+|,|;|\band\b|\n", text.lower()) if p.strip()]
    for p in parts:
        m = None
        if m := re.search(r"(up|gain(?:ed)?|rise|rose)\s*(?:by\s*)?(\d+(?:\.\d+)?)\s*%(?:\s*in\s*(\d+)\s*(?:day|days|bar|bars|week|weeks|candles?))?", p):
            out.append(f"change({m.group(3) or 1}) > {m.group(2)}")
        elif m := re.search(r"(down|fall|fell|drop(?:ped)?|lose|lost)\s*(?:by\s*)?(\d+(?:\.\d+)?)\s*%(?:\s*in\s*(\d+)\s*(?:day|days|bar|bars|week|weeks|candles?))?", p):
            out.append(f"change({m.group(3) or 1}) < -{m.group(2)}")
        elif m := re.search(r"volume\s*(\d+(?:\.\d+)?)\s*(?:x|times)", p) or re.search(r"(\d+(?:\.\d+)?)\s*(?:x|times)\s*volume", p):
            out.append(f"volume > {m.group(1)} * avg_volume(20)")
        elif re.search(r"(high|big|huge|heavy)\s*volume|volume\s*(spike|surge|shocker|breakout)", p):
            out.append("volume > 2 * avg_volume(20)")
        elif m := re.search(r"(above|over|>)\s*(\d+)\s*" + _MA, p):
            fn = "ema" if m.group(3) == "ema" else "sma"; out.append(f"close > {fn}(close, {m.group(2)})")
        elif m := re.search(r"(below|under|<)\s*(\d+)\s*" + _MA, p):
            fn = "ema" if m.group(3) == "ema" else "sma"; out.append(f"close < {fn}(close, {m.group(2)})")
        elif m := re.search(r"(sma|ema)\s*(\d+)\s*(?:cross(?:es|ed)?\s*(?:above|over)?|x)\s*(?:sma|ema)?\s*(\d+)", p):
            out.append(f"crossed_above({m.group(1)}(close, {m.group(2)}), {m.group(1)}(close, {m.group(3)}))")
        elif m := re.search(r"rsi\s*(?:\(?\s*(\d+)\s*\)?)?\s*(above|over|>|greater than)\s*(\d+)", p):
            out.append(f"rsi({m.group(1) or 14}) > {m.group(3)}")
        elif m := re.search(r"rsi\s*(?:\(?\s*(\d+)\s*\)?)?\s*(below|under|<|less than)\s*(\d+)", p):
            out.append(f"rsi({m.group(1) or 14}) < {m.group(3)}")
        elif "oversold" in p:
            out.append("rsi(14) < 30")
        elif "overbought" in p:
            out.append("rsi(14) > 70")
        elif re.search(r"52\s*-?\s*w(ee)?k\s*high|new high|all.?time high|ath", p):
            out.append("close >= 0.98 * high52")
        elif re.search(r"52\s*-?\s*w(ee)?k\s*low|new low", p):
            out.append("close <= 1.02 * low52")
        elif "golden cross" in p:
            out.append("crossed_above(sma(close, 50), sma(close, 200))")
        elif "death cross" in p:
            out.append("crossed_below(sma(close, 50), sma(close, 200))")
        elif re.search(r"macd.*(cross|crossover)", p):
            out.append("crossed_above(macd(), macd_signal())")
        elif re.search(r"macd.*(negative|bearish|sell)", p):
            out.append("macd() < macd_signal()")
        elif "macd" in p:
            out.append("macd() > macd_signal()")
        elif re.search(r"supertrend.*(negative|sell|red|bearish|down)", p):
            out.append("close < supertrend(10, 3)")
        elif "supertrend" in p:
            out.append("close > supertrend(10, 3)")
        elif re.search(r"bollinger.*(lower|bottom)|below.*bollinger", p):
            out.append("close < bb_lower(20, 2)")
        elif "bollinger" in p:
            out.append("close > bb_upper(20, 2)")
        elif "gap up" in p:
            out.append("open > ago(high, 1)")
        elif "gap down" in p:
            out.append("open < ago(low, 1)")
        elif "inside bar" in p:
            out.append("high < ago(high, 1) and low > ago(low, 1)")
        elif "nr7" in p or "narrow range" in p:
            out.append("(high - low) <= lowest(high - low, 7)")
        elif re.search(r"strong trend|adx", p):
            n = re.search(r"(\d+)", p); out.append(f"adx(14) > {n.group(1) if n else 25}")
        elif re.search(r"\bdowntrend\b", p):
            out.append("close < sma(close, 50) and sma(close, 50) < sma(close, 200)")
        elif re.search(r"\buptrend\b|stage 2", p):
            out.append("close > sma(close, 50) and sma(close, 50) > sma(close, 200)")
        elif m := re.search(r"(?:rs|relative strength)\D*(\d+)", p):
            out.append(f"rs >= {m.group(1)}")
        elif re.search(r"strong rs|relative strength|leader", p):
            out.append("rs >= 80")
        elif m := re.search(r"(?:price|close)\s*(above|over|>|below|under|<)\s*(\d+(?:\.\d+)?)", p):
            out.append(f"close {'>' if m.group(1) in ('above', 'over', '>') else '<'} {m.group(2)}")
        elif re.search(r"green candle|bullish candle", p):
            out.append("close > open")
        elif re.search(r"red candle|bearish candle", p):
            out.append("close < open")
        else:
            unknown.append(p)
    return out, unknown


# ------------------------------------------------------------------ visual builder (table rows → conditions)
CATALOG = {
    "Close": ("close", ""), "Open": ("open", ""), "High": ("high", ""), "Low": ("low", ""), "Volume": ("volume", ""),
    "SMA": ("sma(close, {})", "50"), "EMA": ("ema(close, {})", "21"), "WMA": ("wma(close, {})", "20"),
    "Avg volume": ("avg_volume({})", "20"), "RSI": ("rsi({})", "14"), "MACD line": ("macd({})", "12, 26"),
    "MACD signal": ("macd_signal({})", "12, 26, 9"), "MACD histogram": ("macd_hist({})", "12, 26, 9"),
    "Supertrend": ("supertrend({})", "10, 3"), "ADX": ("adx({})", "14"), "+DI": ("plus_di({})", "14"), "-DI": ("minus_di({})", "14"),
    "Stochastic %K": ("stoch_k({})", "14, 3"), "Stochastic %D": ("stoch_d({})", "14, 3, 3"), "Williams %R": ("willr({})", "14"),
    "CCI": ("cci({})", "20"), "MFI": ("mfi({})", "14"), "Bollinger upper": ("bb_upper({})", "20, 2"),
    "Bollinger lower": ("bb_lower({})", "20, 2"), "ATR": ("atr({})", "14"), "% change": ("change({})", "1"),
    "Highest high": ("highest(high, {})", "20"), "Lowest low": ("lowest(low, {})", "20"), "52-week high": ("high52", ""),
    "52-week low": ("low52", ""), "RS rating (0-99)": ("rs", ""), "GMMA short": ("gmma_short", ""), "GMMA long": ("gmma_long", ""),
    "OBV": ("obv()", ""),
}
OPS = ["greater than", "greater or equal", "less than", "less or equal", "equals", "crossed above", "crossed below"]
_OPSYM = {"greater than": ">", "greater or equal": ">=", "less than": "<", "less or equal": "<=", "equals": "=="}


def _expr(name, params, offset):
    tmpl, default = CATALOG[name]
    params = str(params).strip() if params is not None and str(params).strip() not in ("", "nan", "None") else default
    e = tmpl.format(params) if "{}" in tmpl else tmpl
    try:
        k = int(float(offset or 0))
    except (TypeError, ValueError):
        k = 0
    return f"ago({e}, {k})" if k > 0 else e


def row_to_line(r: dict):
    """r: indicator, params, bars_ago, condition, compare_to, value, params2, bars_ago2"""
    if not r.get("indicator") or r["indicator"] not in CATALOG:
        return None
    left = _expr(r["indicator"], r.get("params"), r.get("bars_ago"))
    try:
        val = float(r.get("value")) if r.get("value") not in (None, "") else None
    except (TypeError, ValueError):
        val = None
    if val is not None and np.isnan(val):
        val = None
    cmp_to = r.get("compare_to") or "Number"
    if cmp_to == "Number":
        right = f"{val if val is not None else 0:g}"
    else:
        if cmp_to not in CATALOG:
            return None
        right = _expr(cmp_to, r.get("params2"), r.get("bars_ago2"))
        if val is not None and val != 1:
            right = f"{val:g} * {right}"
    op = r.get("condition") or "greater than"
    if op == "crossed above":
        return f"crossed_above({left}, {right})"
    if op == "crossed below":
        return f"crossed_below({left}, {right})"
    return f"{left} {_OPSYM.get(op, '>')} {right}"
