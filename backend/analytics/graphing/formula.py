"""
analytics/graphing/formula.py — Safe formula evaluator for the Graph Builder
("type an expression, get a chart" — a Bloomberg GP-style custom graph).

Expressions reference tickers as bare names (AAPL, MSFT, ...), combine them
with + - * / ** and parentheses, and can call a small whitelist of
indicator functions: SMA, EMA, RSI, ROC, ZSCORE, STD, CORR.

This is deliberately NOT eval()/exec() on user input — that would be
arbitrary code execution from an HTTP body. Instead we parse to an AST
(ast.parse(..., mode="eval")) and walk it ourselves, only ever handling a
fixed whitelist of node types (Constant, Name, BinOp with +-*/**, unary
minus, and Call to a whitelisted function). Anything else — imports,
attribute access, comprehensions, lambdas, subscripts, string literals,
arbitrary function names — raises FormulaError before it's ever evaluated.
"""
import ast

import numpy as np

from analytics.indicators import sma as _sma, ema as _ema, rsi as _rsi

MAX_EXPR_LEN = 300
MAX_NODES = 80
MAX_POW_EXPONENT = 10  # guards against e.g. "2**100000000" as a CPU/memory DoS


class FormulaError(ValueError):
    pass


# ── Whitelisted functions ──────────────────────────────────────────
# Each takes an aligned numpy series (+ params) and returns a same-length,
# NaN-padded series, mirroring analytics/indicators.py's convention.

def _roc(series, n=10):
    n = int(n)
    out = np.full(len(series), np.nan)
    if n > 0 and n < len(series):
        out[n:] = (series[n:] / series[:-n] - 1) * 100
    return out


def _zscore(series, n=20):
    n = int(n)
    out = np.full(len(series), np.nan)
    for i in range(n - 1, len(series)):
        window = series[i - n + 1:i + 1]
        m, sd = window.mean(), window.std()
        out[i] = (series[i] - m) / sd if sd > 0 else 0.0
    return out


def _std(series, n=20):
    n = int(n)
    out = np.full(len(series), np.nan)
    for i in range(n - 1, len(series)):
        out[i] = series[i - n + 1:i + 1].std()
    return out


def _corr(a, b, n=20):
    n = int(n)
    out = np.full(len(a), np.nan)
    for i in range(n - 1, len(a)):
        wa, wb = a[i - n + 1:i + 1], b[i - n + 1:i + 1]
        if wa.std() > 0 and wb.std() > 0:
            out[i] = np.corrcoef(wa, wb)[0, 1]
    return out


def _sma_np(series, n=20):
    return np.array(_sma(list(series), int(n)), dtype=float)


def _ema_np(series, n=20):
    return np.array(_ema(list(series), int(n)), dtype=float)


def _rsi_np(series, n=14):
    return np.array(_rsi(list(series), int(n)), dtype=float)


def _bb_upper(series, n=20, num_std=2):
    n = int(n)
    mid = _sma_np(series, n)
    out = np.full(len(series), np.nan)
    for i in range(n - 1, len(series)):
        out[i] = mid[i] + num_std * series[i - n + 1:i + 1].std()
    return out


def _bb_lower(series, n=20, num_std=2):
    n = int(n)
    mid = _sma_np(series, n)
    out = np.full(len(series), np.nan)
    for i in range(n - 1, len(series)):
        out[i] = mid[i] - num_std * series[i - n + 1:i + 1].std()
    return out


def _macd_line(series, fast=12, slow=26):
    return _ema_np(series, fast) - _ema_np(series, slow)


def _macd_signal(series, fast=12, slow=26, signal=9):
    macd_line = _macd_line(series, fast, slow)
    first_valid = np.argmax(~np.isnan(macd_line)) if np.any(~np.isnan(macd_line)) else len(macd_line)
    out = np.full(len(series), np.nan)
    tail = _ema_np(macd_line[first_valid:], signal)
    out[first_valid:first_valid + len(tail)] = tail
    return out


FUNCTIONS = {
    "SMA": _sma_np, "EMA": _ema_np, "RSI": _rsi_np,
    "ROC": _roc, "ZSCORE": _zscore, "STD": _std, "CORR": _corr,
    "BBUPPER": _bb_upper, "BBLOWER": _bb_lower,
    "MACDLINE": _macd_line, "MACDSIGNAL": _macd_signal,
}

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)


def _validate(expr: str) -> ast.Expression:
    if len(expr) > MAX_EXPR_LEN:
        raise FormulaError(f"expression too long (max {MAX_EXPR_LEN} chars)")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"syntax error: {e.msg}")
    n_nodes = sum(1 for _ in ast.walk(tree))
    if n_nodes > MAX_NODES:
        raise FormulaError("expression too complex")
    return tree


def extract_symbols(expr: str) -> list[str]:
    """Parse `expr` and return bare names referenced that aren't function
    calls — these are the tickers the caller needs to fetch price history
    for before evaluate() can run."""
    tree = _validate(expr)
    func_names = {
        node.func.id for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    symbols = {
        node.id.upper() for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id not in func_names and node.id not in FUNCTIONS
    }
    return sorted(symbols)


def evaluate(expr: str, series: dict[str, np.ndarray]) -> np.ndarray:
    """
    series: {SYMBOL: aligned numpy array of closes}, all the same length.
    Returns the evaluated numpy array. Raises FormulaError on anything
    outside the whitelist (unknown name, disallowed syntax, wrong arity).
    """
    tree = _validate(expr)

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise FormulaError(f"unsupported constant: {node.value!r}")
            return float(node.value)
        if isinstance(node, ast.Name):
            sym = node.id.upper()
            if sym not in series:
                raise FormulaError(f"unknown symbol '{node.id}'")
            return series[sym]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -_eval(node.operand)
        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, _ALLOWED_BINOPS):
                raise FormulaError(f"operator '{type(node.op).__name__}' not allowed")
            if isinstance(node.op, ast.Pow) and isinstance(node.right, ast.Constant) \
                    and abs(node.right.value) > MAX_POW_EXPONENT:
                raise FormulaError(f"exponent too large (max {MAX_POW_EXPONENT})")
            left, right = _eval(node.left), _eval(node.right)
            if isinstance(node.op, ast.Add):  return left + right
            if isinstance(node.op, ast.Sub):  return left - right
            if isinstance(node.op, ast.Mult): return left * right
            if isinstance(node.op, ast.Div):  return left / right
            if isinstance(node.op, ast.Pow):  return left ** right
        if isinstance(node, ast.Call):
            if node.keywords or not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
                allowed = ", ".join(FUNCTIONS)
                raise FormulaError(f"unknown function — allowed: {allowed}")
            args = [_eval(a) for a in node.args]
            try:
                return FUNCTIONS[node.func.id](*args)
            except TypeError as e:
                raise FormulaError(f"{node.func.id}(): {e}")
        raise FormulaError(f"unsupported syntax: {type(node).__name__}")

    with np.errstate(divide="ignore", invalid="ignore"):
        result = _eval(tree)
    if isinstance(result, (int, float)):
        n = len(next(iter(series.values()))) if series else 1
        result = np.full(n, float(result))
    return np.asarray(result, dtype=float)
