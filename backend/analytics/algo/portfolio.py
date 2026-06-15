"""
analytics/algo/portfolio.py
Paper-trading portfolio — a virtual book that simulates fills and tracks P&L.

NO REAL EXECUTION. This never connects to a broker, never places real orders,
never touches credentials. It simulates what a strategy *would* do so you can
validate algorithms against live data with zero risk.

State is persisted in Redis so it survives restarts.
"""
import time
import json
import logging
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol:     str
    quantity:   float = 0.0
    avg_price:  float = 0.0
    realized_pnl: float = 0.0

    def market_value(self, price: float) -> float:
        return self.quantity * price

    def unrealized_pnl(self, price: float) -> float:
        return (price - self.avg_price) * self.quantity


@dataclass
class Fill:
    ts:       float
    symbol:   str
    side:     str        # "buy" | "sell"
    quantity: float
    price:    float
    strategy: str = ""


class PaperPortfolio:
    """
    A single virtual trading account. Simulates market-order fills at the
    provided price (optionally with slippage), tracks positions, cash, and P&L.
    """

    def __init__(self, name: str = "default", starting_cash: float = 100_000.0,
                 slippage_bps: float = 1.0):
        self.name          = name
        self.starting_cash = starting_cash
        self.cash          = starting_cash
        self.slippage_bps  = slippage_bps
        self.positions: dict[str, Position] = {}
        self.fills: list[Fill] = []

    # ── Order simulation ──────────────────────────────────────────
    def market_order(self, symbol: str, side: str, quantity: float,
                     price: float, strategy: str = "") -> dict:
        """Simulate a market-order fill at `price` (+ slippage). Returns fill info."""
        if quantity <= 0 or price <= 0:
            return {"error": "quantity and price must be positive"}

        slip = price * (self.slippage_bps / 10000.0)
        fill_price = price + slip if side == "buy" else price - slip

        cost = fill_price * quantity
        if side == "buy" and cost > self.cash:
            # Scale down to available cash
            quantity = self.cash / fill_price
            if quantity <= 0:
                return {"error": "insufficient cash"}
            cost = fill_price * quantity

        pos = self.positions.get(symbol, Position(symbol=symbol))

        if side == "buy":
            new_qty = pos.quantity + quantity
            if new_qty != 0:
                pos.avg_price = (pos.avg_price * pos.quantity + fill_price * quantity) / new_qty
            pos.quantity = new_qty
            self.cash -= cost
        else:  # sell
            # Realized P&L on the portion that closes existing long
            closing = min(quantity, max(pos.quantity, 0))
            pos.realized_pnl += (fill_price - pos.avg_price) * closing
            pos.quantity -= quantity
            self.cash += fill_price * quantity
            if pos.quantity == 0:
                pos.avg_price = 0.0

        self.positions[symbol] = pos
        fill = Fill(ts=time.time(), symbol=symbol, side=side,
                    quantity=round(quantity, 4), price=round(fill_price, 4), strategy=strategy)
        self.fills.append(fill)

        return {"filled": asdict(fill), "cash": round(self.cash, 2)}

    def target_position(self, symbol: str, target_qty: float, price: float,
                        strategy: str = "") -> dict:
        """Adjust holdings to reach a target quantity (signed; negative = short)."""
        pos = self.positions.get(symbol, Position(symbol=symbol))
        delta = target_qty - pos.quantity
        if abs(delta) < 1e-6:
            return {"no_change": True, "symbol": symbol}
        side = "buy" if delta > 0 else "sell"
        return self.market_order(symbol, side, abs(delta), price, strategy)

    # ── Valuation ─────────────────────────────────────────────────
    def equity(self, prices: dict[str, float]) -> float:
        mv = sum(p.market_value(prices.get(s, p.avg_price))
                 for s, p in self.positions.items())
        return self.cash + mv

    def snapshot(self, prices: dict[str, float]) -> dict:
        equity = self.equity(prices)
        total_unreal = sum(p.unrealized_pnl(prices.get(s, p.avg_price))
                           for s, p in self.positions.items())
        total_real = sum(p.realized_pnl for p in self.positions.values())

        return {
            "name":          self.name,
            "cash":          round(self.cash, 2),
            "equity":        round(equity, 2),
            "starting_cash": self.starting_cash,
            "total_return":  round((equity / self.starting_cash - 1) * 100, 3),
            "realized_pnl":  round(total_real, 2),
            "unrealized_pnl":round(total_unreal, 2),
            "positions": [
                {
                    "symbol":        s,
                    "quantity":      round(p.quantity, 4),
                    "avg_price":     round(p.avg_price, 4),
                    "last_price":    round(prices.get(s, p.avg_price), 4),
                    "market_value":  round(p.market_value(prices.get(s, p.avg_price)), 2),
                    "unrealized_pnl":round(p.unrealized_pnl(prices.get(s, p.avg_price)), 2),
                    "realized_pnl":  round(p.realized_pnl, 2),
                }
                for s, p in self.positions.items() if abs(p.quantity) > 1e-6
            ],
            "n_fills": len(self.fills),
            "recent_fills": [asdict(f) for f in self.fills[-20:]],
        }

    # ── Persistence ───────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "starting_cash": self.starting_cash,
            "cash": self.cash,
            "slippage_bps": self.slippage_bps,
            "positions": {s: asdict(p) for s, p in self.positions.items()},
            "fills": [asdict(f) for f in self.fills[-500:]],  # cap history
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PaperPortfolio":
        pf = cls(d["name"], d["starting_cash"], d.get("slippage_bps", 1.0))
        pf.cash = d["cash"]
        pf.positions = {s: Position(**p) for s, p in d.get("positions", {}).items()}
        pf.fills = [Fill(**f) for f in d.get("fills", [])]
        return pf

    def reset(self):
        self.cash = self.starting_cash
        self.positions = {}
        self.fills = []
