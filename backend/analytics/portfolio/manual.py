"""
analytics/portfolio/manual.py
Manual portfolio tracker — user enters their own holdings (symbol, shares,
cost basis) and the terminal marks them to live market prices, computing P&L,
weights, and basic risk stats. Persisted in Redis.

This is distinct from the algo paper-portfolios: those are simulated by
strategies; this is the user's own real book, entered by hand.
"""
import logging

logger = logging.getLogger(__name__)


def compute_portfolio(holdings: list[dict], prices: dict[str, float]) -> dict:
    """
    holdings: [{symbol, shares, cost_basis}]
    prices:   {symbol: current_price}
    Returns marked-to-market portfolio with P&L, weights, allocation.
    """
    positions = []
    total_value = 0.0
    total_cost = 0.0

    for h in holdings:
        sym = h["symbol"].upper()
        shares = float(h.get("shares", 0))
        cost = float(h.get("cost_basis", 0))
        price = prices.get(sym)

        market_value = shares * price if price else None
        cost_value = shares * cost
        unreal = (market_value - cost_value) if market_value is not None else None
        unreal_pct = (unreal / cost_value * 100) if (unreal is not None and cost_value) else None

        if market_value is not None:
            total_value += market_value
        total_cost += cost_value

        positions.append({
            "symbol":         sym,
            "shares":         shares,
            "cost_basis":     round(cost, 2),
            "last_price":     round(price, 2) if price else None,
            "market_value":   round(market_value, 2) if market_value is not None else None,
            "cost_value":     round(cost_value, 2),
            "unrealized_pnl": round(unreal, 2) if unreal is not None else None,
            "unrealized_pct": round(unreal_pct, 2) if unreal_pct is not None else None,
        })

    # Weights
    for p in positions:
        p["weight"] = round(p["market_value"] / total_value * 100, 2) \
            if (p["market_value"] and total_value) else None

    total_pnl = total_value - total_cost
    return {
        "positions":       sorted(positions, key=lambda p: p.get("market_value") or 0, reverse=True),
        "total_value":     round(total_value, 2),
        "total_cost":      round(total_cost, 2),
        "total_pnl":       round(total_pnl, 2),
        "total_pnl_pct":   round(total_pnl / total_cost * 100, 2) if total_cost else None,
        "n_positions":     len([p for p in positions if p["shares"] != 0]),
    }
