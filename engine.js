/* ScanX scan engine: Chartink-style condition language evaluated on aligned price arrays.
   Works in the browser (window.ScanEngine) and in Node (module.exports) for testing. */
(function (root) {
  'use strict';
  const isArr = (x) => x instanceof Float64Array || Array.isArray(x);

  // ---------- tokenizer
  function tokenize(src) {
    const t = []; let i = 0;
    while (i < src.length) {
      const ch = src[i];
      if (/\s/.test(ch)) { i++; continue; }
      if (/[0-9.]/.test(ch)) { let j = i; while (j < src.length && /[0-9.]/.test(src[j])) j++; t.push({ k: 'num', v: parseFloat(src.slice(i, j)) }); i = j; continue; }
      if (/[A-Za-z_]/.test(ch)) { let j = i; while (j < src.length && /[A-Za-z0-9_]/.test(src[j])) j++; const w = src.slice(i, j); const lw = w.toLowerCase();
        t.push(['and', 'or', 'not'].includes(lw) ? { k: 'kw', v: lw } : { k: 'id', v: lw }); i = j; continue; }
      const two = src.slice(i, i + 2);
      if (['>=', '<=', '==', '!='].includes(two)) { t.push({ k: 'op', v: two }); i += 2; continue; }
      if ('<>+-*/(),%'.includes(ch)) { t.push({ k: 'op', v: ch }); i++; continue; }
      if (ch === '=') { t.push({ k: 'op', v: '==' }); i++; continue; }
      throw new Error(`Unexpected character "${ch}"`);
    }
    return t;
  }

  // ---------- parser -> AST
  function parse(src) {
    const t = tokenize(src); let p = 0;
    const peek = () => t[p], next = () => t[p++];
    const isOp = (v) => peek() && peek().k === 'op' && peek().v === v;
    const isKw = (v) => peek() && peek().k === 'kw' && peek().v === v;
    const expect = (v) => { if (!isOp(v)) throw new Error(`Expected "${v}"`); p++; };
    function orE() { let l = andE(); while (isKw('or')) { p++; l = { t: 'bin', op: 'or', l, r: andE() }; } return l; }
    function andE() { let l = notE(); while (isKw('and')) { p++; l = { t: 'bin', op: 'and', l, r: notE() }; } return l; }
    function notE() { if (isKw('not')) { p++; return { t: 'not', x: notE() }; } return cmpE(); }
    function cmpE() {
      const first = addE(); const parts = []; let left = first;
      while (peek() && peek().k === 'op' && ['>', '<', '>=', '<=', '==', '!='].includes(peek().v)) {
        const op = next().v; const right = addE(); parts.push({ t: 'bin', op, l: left, r: right }); left = right;
      }
      if (!parts.length) return first;
      return parts.reduce((a, b) => ({ t: 'bin', op: 'and', l: a, r: b }));
    }
    function addE() { let l = mulE(); while (isOp('+') || isOp('-')) { const op = next().v; l = { t: 'bin', op, l, r: mulE() }; } return l; }
    function mulE() { let l = unE(); while (isOp('*') || isOp('/') || isOp('%')) { const op = next().v; l = { t: 'bin', op, l, r: unE() }; } return l; }
    function unE() { if (isOp('-')) { p++; return { t: 'neg', x: unE() }; } if (isOp('+')) { p++; return unE(); } return prim(); }
    function prim() {
      const tk = next(); if (!tk) throw new Error('Condition ends too early');
      if (tk.k === 'num') return { t: 'num', v: tk.v };
      if (tk.k === 'id') {
        if (isOp('(')) { p++; const args = []; if (!isOp(')')) { args.push(orE()); while (isOp(',')) { p++; args.push(orE()); } } expect(')'); return { t: 'call', f: tk.v, args }; }
        return { t: 'var', v: tk.v };
      }
      if (tk.k === 'op' && tk.v === '(') { const e = orE(); expect(')'); return e; }
      throw new Error(`Unexpected "${tk.v}"`);
    }
    const ast = orE(); if (p < t.length) throw new Error(`Unexpected "${t[p].v}"`); return ast;
  }

  // ---------- vector helpers (NaN = missing; booleans are 1/0)
  const N = (ctx) => ctx.n;
  const toArr = (x, n) => { if (isArr(x)) return x; const a = new Float64Array(n); a.fill(x); return a; };
  function map2(a, b, n, f) {
    if (!isArr(a) && !isArr(b)) return f(a, b);
    const A = toArr(a, n), B = toArr(b, n), o = new Float64Array(n);
    for (let i = 0; i < n; i++) o[i] = (isNaN(A[i]) || isNaN(B[i])) ? NaN : f(A[i], B[i]);
    return o;
  }
  const truthy = (v) => !isNaN(v) && v !== 0;
  function logic2(a, b, n, f) {
    if (!isArr(a) && !isArr(b)) return f(truthy(a), truthy(b)) ? 1 : 0;
    const A = toArr(a, n), B = toArr(b, n), o = new Float64Array(n);
    for (let i = 0; i < n; i++) o[i] = f(truthy(A[i]), truthy(B[i])) ? 1 : 0;
    return o;
  }
  function sma(x, len) { len = Math.round(len); const n = x.length, o = new Float64Array(n).fill(NaN); let s = 0, c = 0;
    for (let i = 0; i < n; i++) { const v = x[i]; if (isNaN(v)) { s = 0; c = 0; continue; } s += v; c++; if (c > len) { s -= x[i - len]; c = len; } if (c === len) o[i] = s / len; } return o; }
  function ema(x, len) { len = Math.round(len); const n = x.length, o = new Float64Array(n).fill(NaN), k = 2 / (len + 1); let e = NaN, c = 0;
    for (let i = 0; i < n; i++) { const v = x[i]; if (isNaN(v)) continue; e = isNaN(e) ? v : v * k + e * (1 - k); c++; if (c >= len) o[i] = e; } return o; }
  function rollExt(x, len, mx) { len = Math.max(1, Math.round(len)); const n = x.length, o = new Float64Array(n).fill(NaN);
    for (let i = 0; i < n; i++) { let m = NaN; for (let k = Math.max(0, i - len + 1); k <= i; k++) { const v = x[k]; if (isNaN(v)) continue; if (isNaN(m) || (mx ? v > m : v < m)) m = v; } o[i] = m; } return o; }
  function shift(x, k) { k = Math.round(k); const n = x.length, o = new Float64Array(n).fill(NaN); for (let i = k; i < n; i++) if (i - k >= 0 && i - k < n) o[i] = x[i - k]; return o; }
  function stdev(x, len) { len = Math.round(len); const m = sma(x, len), n = x.length, o = new Float64Array(n).fill(NaN);
    for (let i = len - 1; i < n; i++) { if (isNaN(m[i])) continue; let s = 0; for (let k = i - len + 1; k <= i; k++) s += (x[k] - m[i]) ** 2; o[i] = Math.sqrt(s / (len - 1)); } return o; }
  function rsiF(x, len) { len = Math.round(len); const n = x.length, o = new Float64Array(n).fill(NaN); let up = NaN, dn = NaN, prev = NaN, c = 0; const a = 1 / len;
    for (let i = 0; i < n; i++) { const v = x[i]; if (isNaN(v)) continue; if (!isNaN(prev)) { const d = v - prev; const u = Math.max(d, 0), w = Math.max(-d, 0);
      up = isNaN(up) ? u : up * (1 - a) + u * a; dn = isNaN(dn) ? w : dn * (1 - a) + w * a; c++; if (c >= len) o[i] = dn === 0 ? 100 : 100 - 100 / (1 + up / dn); } prev = v; } return o; }

  const FUNCS = {
    sma: (c, x, n = 20) => sma(toArr(x, c.n), n),
    ema: (c, x, n = 20) => ema(toArr(x, c.n), n),
    highest: (c, x, n = 20) => rollExt(toArr(x, c.n), n, true),
    lowest: (c, x, n = 20) => rollExt(toArr(x, c.n), n, false),
    ago: (c, x, k = 1) => shift(toArr(x, c.n), k),
    change: (c, k = 1) => map2(c.v('close'), shift(c.v('close'), k), c.n, (a, b) => 100 * (a / b - 1)),
    avg_volume: (c, n = 20) => sma(c.v('volume'), n),
    rsi: (c, n = 14, x) => rsiF(x == null ? c.v('close') : toArr(x, c.n), n),
    atr: (c, n = 14) => { const h = c.v('high'), l = c.v('low'), cl = c.v('close'), tr = new Float64Array(c.n).fill(NaN);
      for (let i = 0; i < c.n; i++) { const pc = i ? cl[i - 1] : NaN; tr[i] = isNaN(pc) ? h[i] - l[i] : Math.max(h[i] - l[i], Math.abs(h[i] - pc), Math.abs(l[i] - pc)); } return sma(tr, n); },
    crossed_above: (c, a, b) => { const A = toArr(a, c.n), B = toArr(b, c.n), o = new Float64Array(c.n); for (let i = 1; i < c.n; i++) o[i] = (A[i] > B[i] && A[i - 1] <= B[i - 1]) ? 1 : 0; return o; },
    crossed_below: (c, a, b) => { const A = toArr(a, c.n), B = toArr(b, c.n), o = new Float64Array(c.n); for (let i = 1; i < c.n; i++) o[i] = (A[i] < B[i] && A[i - 1] >= B[i - 1]) ? 1 : 0; return o; },
    macd: (c, f = 12, s = 26) => map2(ema(c.v('close'), f), ema(c.v('close'), s), c.n, (a, b) => a - b),
    macd_signal: (c, f = 12, s = 26, g = 9) => ema(FUNCS.macd(c, f, s), g),
    bb_upper: (c, n = 20, k = 2) => map2(sma(c.v('close'), n), stdev(c.v('close'), n), c.n, (m, d) => m + k * d),
    bb_lower: (c, n = 20, k = 2) => map2(sma(c.v('close'), n), stdev(c.v('close'), n), c.n, (m, d) => m - k * d),
    abs: (c, x) => isArr(x) ? Float64Array.from(x, Math.abs) : Math.abs(x),
    min: (c, a, b) => map2(a, b, c.n, Math.min),
    max: (c, a, b) => map2(a, b, c.n, Math.max),
  };
  const VARS = ['open', 'high', 'low', 'close', 'volume', 'rs', 'high52', 'low52', 'gmma_short', 'gmma_long'];

  function evalNode(node, c) {
    switch (node.t) {
      case 'num': return node.v;
      case 'var': if (!VARS.includes(node.v)) throw new Error(`Unknown word "${node.v}"`); return c.v(node.v);
      case 'neg': { const x = evalNode(node.x, c); return isArr(x) ? Float64Array.from(x, (v) => -v) : -x; }
      case 'not': { const x = evalNode(node.x, c); return isArr(x) ? Float64Array.from(x, (v) => truthy(v) ? 0 : 1) : (truthy(x) ? 0 : 1); }
      case 'call': { const f = FUNCS[node.f]; if (!f) throw new Error(`Unknown function "${node.f}()"`); return f(c, ...node.args.map((a) => evalNode(a, c))); }
      case 'bin': {
        const a = evalNode(node.l, c), b = evalNode(node.r, c), n = c.n;
        switch (node.op) {
          case 'and': return logic2(a, b, n, (x, y) => x && y);
          case 'or': return logic2(a, b, n, (x, y) => x || y);
          case '+': return map2(a, b, n, (x, y) => x + y);
          case '-': return map2(a, b, n, (x, y) => x - y);
          case '*': return map2(a, b, n, (x, y) => x * y);
          case '/': return map2(a, b, n, (x, y) => y === 0 ? NaN : x / y);
          case '%': return map2(a, b, n, (x, y) => x % y);
          case '>': return map2(a, b, n, (x, y) => x > y ? 1 : 0);
          case '<': return map2(a, b, n, (x, y) => x < y ? 1 : 0);
          case '>=': return map2(a, b, n, (x, y) => x >= y ? 1 : 0);
          case '<=': return map2(a, b, n, (x, y) => x <= y ? 1 : 0);
          case '==': return map2(a, b, n, (x, y) => Math.abs(x - y) < 1e-9 ? 1 : 0);
          case '!=': return map2(a, b, n, (x, y) => Math.abs(x - y) >= 1e-9 ? 1 : 0);
        }
      }
    }
    throw new Error('Cannot read this condition');
  }

  // ---------- context for one stock (lazy, memoised variables)
  function makeCtx(stock, tf) {
    const memo = {}; const yr = tf === 'Weekly' ? 52 : 252;
    const c = {
      n: stock.close.length,
      v(name) {
        if (memo[name]) return memo[name];
        let r;
        if (['open', 'high', 'low', 'close', 'volume'].includes(name)) r = stock[name];
        else if (name === 'rs') r = stock.rs || new Float64Array(c.n).fill(NaN);
        else if (name === 'high52') r = rollExt(stock.high, yr, true);
        else if (name === 'low52') r = rollExt(stock.low, yr, false);
        else if (name === 'gmma_short') r = avgArr([3, 5, 8, 10, 12, 15].map((k) => ema(stock.close, k)));
        else if (name === 'gmma_long') r = avgArr([30, 35, 40, 45, 50, 60].map((k) => ema(stock.close, k)));
        return (memo[name] = r);
      },
    };
    return c;
  }
  function avgArr(list) { const n = list[0].length, o = new Float64Array(n); for (let i = 0; i < n; i++) { let s = 0; for (const a of list) s += a[i]; o[i] = s / list.length; } return o; }

  // ---------- public API
  function compile(text) {
    const lines = text.split('\n').map((l) => l.replace(/#.*/, '').trim()).filter(Boolean);
    return lines.map((line) => { try { return { line, ast: parse(line) }; } catch (e) { return { line, err: e.message }; } });
  }
  function lastVal(x, n) { return isArr(x) ? x[n - 1] : x; }
  /** stocks: [{sym, open, high, low, close, volume, rs}] aligned arrays. Returns {hits:[{stock, ctx}], errors:[]} */
  function run(text, stocks, tf) {
    const conds = compile(text); const errors = conds.filter((c) => c.err).map((c) => `${c.line} → ${c.err}`);
    if (errors.length) return { hits: [], errors };
    const hits = [];
    for (const s of stocks) {
      const ctx = makeCtx(s, tf); let ok = true;
      for (const c of conds) {
        let r; try { r = evalNode(c.ast, ctx); } catch (e) { errors.push(`${c.line} → ${e.message}`); return { hits: [], errors: [...new Set(errors)] }; }
        if (!truthy(lastVal(r, ctx.n))) { ok = false; break; }
      }
      if (ok) hits.push({ stock: s, ctx });
    }
    return { hits, errors };
  }
  /** RS rating 0-99 per bar across the universe (weighted 3/6/9/12-month return). */
  function addRS(stocks, tf) {
    if (!stocks.length) return; const q = tf === 'Weekly' ? 13 : 63, n = stocks[0].close.length;
    const wr = stocks.map((s) => { const c = s.close, o = new Float64Array(n).fill(NaN);
      for (let i = 4 * q; i < n; i++) o[i] = 0.4 * (c[i] / c[i - q] - 1) + 0.2 * (c[i] / c[i - 2 * q] - 1) + 0.2 * (c[i] / c[i - 3 * q] - 1) + 0.2 * (c[i] / c[i - 4 * q] - 1); return o; });
    stocks.forEach((s) => { s.rs = new Float64Array(n).fill(NaN); });
    for (let i = 0; i < n; i++) {
      const v = []; for (let k = 0; k < stocks.length; k++) if (isFinite(wr[k][i])) v.push([k, wr[k][i]]);
      v.sort((a, b) => a[1] - b[1]); const m = Math.max(1, v.length - 1);
      v.forEach(([k], r) => { stocks[k].rs[i] = Math.round(99 * r / m); });
    }
  }
  const api = { parse, compile, run, addRS, makeCtx, evalNode, FUNCS, VARS, sma, ema, rsiF, rollExt };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.ScanEngine = api;
})(typeof window !== 'undefined' ? window : globalThis);
