"""Initial schema: all core ORM tables."""

import uuid
from datetime import datetime, timezone

revision = "001"
down_revision = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy import Enum as SAEnum


def upgrade():
    op.create_table(
        "market_data",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, index=True),
        sa.Column("open", sa.Numeric(20, 4), nullable=False),
        sa.Column("high", sa.Numeric(20, 4), nullable=False),
        sa.Column("low", sa.Numeric(20, 4), nullable=False),
        sa.Column("close", sa.Numeric(20, 4), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(50), server_default="yfinance"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("symbol", "timestamp", name="uq_symbol_timestamp"),
    )
    op.create_index("ix_market_data_symbol_ts", "market_data", ["symbol", "timestamp"])

    op.create_table(
        "strategies",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("version", sa.String(20), server_default="1.0.0"),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("dsl", sa.Text(), server_default=""),
        sa.Column("author", sa.String(100), server_default=""),
        sa.Column("tags", JSON(), nullable=True),
        sa.Column("sharpe", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    op.create_table(
        "hypotheses",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("status", sa.String(20), server_default="proposed"),
        sa.Column("confidence", sa.Float(), server_default="0"),
        sa.Column("keywords", JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("strategy_id", sa.String(32), sa.ForeignKey("strategies.id"), nullable=False),
        sa.Column("initial_capital", sa.Numeric(20, 2), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("total_return", sa.Float(), server_default="0"),
        sa.Column("sharpe_ratio", sa.Float(), server_default="0"),
        sa.Column("sortino_ratio", sa.Float(), server_default="0"),
        sa.Column("max_drawdown", sa.Float(), server_default="0"),
        sa.Column("win_rate", sa.Float(), server_default="0"),
        sa.Column("total_trades", sa.Integer(), server_default="0"),
        sa.Column("config", JSON(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "trades",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("backtest_id", sa.String(32), sa.ForeignKey("backtest_runs.id"), nullable=True),
        sa.Column("strategy_id", sa.String(32), sa.ForeignKey("strategies.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("entry_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("exit_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("pnl", sa.Numeric(20, 2), server_default="0"),
        sa.Column("entry_time", sa.DateTime(), nullable=False),
        sa.Column("exit_time", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("strategy_id", sa.String(32), sa.ForeignKey("strategies.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("order_type", sa.String(20), server_default="MARKET"),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(20, 4), nullable=True),
        sa.Column("status", sa.String(20), server_default="CREATED"),
        sa.Column("filled_quantity", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )


def downgrade():
    op.drop_table("orders")
    op.drop_table("trades")
    op.drop_table("backtest_runs")
    op.drop_table("hypotheses")
    op.drop_table("strategies")
    op.drop_table("market_data")
