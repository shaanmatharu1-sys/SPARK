"""
models.py — Durable per-user data (Postgres in prod, SQLite for local dev).

Everything here is scoped by user_id and cascades on user delete. This is
deliberately separate from Redis (cache/redis_client.py), which remains a
pure market-data cache — nothing "yours" should live only in an
LRU-evictable store.
"""
import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime, JSON, UniqueConstraint, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    theme: Mapped[str] = mapped_column(String(32), default="midnight-brass")
    # IANA tz name (e.g. "America/New_York") — drives the chart time axis and
    # top-bar clock. Defaults to US Eastern since that's the reference
    # session for every US-market timestamp this app shows, not the visitor's
    # machine timezone (which is what it silently used before this column
    # existed, unrelated to where the actual markets/instruments trade).
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    watchlist: Mapped["Watchlist"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    holdings: Mapped[list["PortfolioHolding"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    algos: Mapped[list["AlgoConfig"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    option_positions: Mapped[list["OptionPosition"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    workspace: Mapped["ChartWorkspace"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    symbols: Mapped[list] = mapped_column(JSON, default=list)

    user: Mapped["User"] = relationship(back_populates="watchlist")


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"
    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uq_portfolio_user_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String(16))
    shares: Mapped[float] = mapped_column(Float)
    cost_basis: Mapped[float] = mapped_column(Float)

    user: Mapped["User"] = relationship(back_populates="holdings")


class AlgoConfig(Base):
    __tablename__ = "algo_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # uuid, matches existing algo_id shape
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    config: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    user: Mapped["User"] = relationship(back_populates="algos")
    snapshot: Mapped["AlgoPortfolioSnapshot"] = relationship(
        back_populates="algo", cascade="all, delete-orphan", uselist=False
    )


class AlgoPortfolioSnapshot(Base):
    """
    Source of truth for paper-trading state. Redis (algo:portfolio:{id}) is
    kept as a hot read-through cache in front of this table, not the record
    of truth — a cache eviction must not look like losing your trade history.
    """
    __tablename__ = "algo_portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    algo_id: Mapped[str] = mapped_column(ForeignKey("algo_configs.id", ondelete="CASCADE"), unique=True)
    state: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    algo: Mapped["AlgoConfig"] = relationship(back_populates="snapshot")


class OptionPosition(Base):
    """Manual options positions for the portfolio Greeks dashboard (Phase 3)."""
    __tablename__ = "option_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String(16))
    strike: Mapped[float] = mapped_column(Float)
    expiration: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    contract_type: Mapped[str] = mapped_column(String(4))  # call | put
    qty: Mapped[int] = mapped_column(Integer)
    side: Mapped[str] = mapped_column(String(5))  # long | short
    cost_basis: Mapped[float] = mapped_column(Float)

    user: Mapped["User"] = relationship(back_populates="option_positions")


class ChartWorkspace(Base):
    """One saved multi-chart grid layout per user (rows/cols + per-cell symbol/timeframe)."""
    __tablename__ = "chart_workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    rows: Mapped[int] = mapped_column(Integer, default=2)
    cols: Mapped[int] = mapped_column(Integer, default=2)
    cells: Mapped[list] = mapped_column(JSON, default=list)  # [{row, col, symbol, timeframe}]

    user: Mapped["User"] = relationship(back_populates="workspace")


class Alert(Base):
    """A user's price alert — active until triggered (or deleted)."""
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String(16))
    condition: Mapped[str] = mapped_column(String(8))  # "above" | "below"
    threshold: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    triggered_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(default=True)

    user: Mapped["User"] = relationship(back_populates="alerts")
