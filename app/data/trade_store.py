"""
TradeStore — SQLite persistence for straddle candidates.

Status lifecycle:
  pending      → candidate found by scanner, awaiting earnings
  resolved_win → post-earnings move exceeded breakeven (move_pct > cost_pct)
  resolved_loss→ post-earnings move did not exceed breakeven
  unresolvable → no cost data (bid/ask=0), move stored but win/loss unknown
  expired      → options expired worthless / past expiry with no resolution
"""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from app.models.models import StraddleCandidate


class TradeStore:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker              TEXT NOT NULL,
                    scan_date           TEXT NOT NULL,
                    earnings_date       TEXT NOT NULL,
                    days_to_earnings    INTEGER,
                    status              TEXT NOT NULL DEFAULT 'pending',

                    -- Greeks & IV at scan time
                    iv_rank             REAL,
                    vega_theta_ratio    REAL,
                    current_iv          REAL,

                    -- Call leg
                    call_symbol         TEXT,
                    call_strike         REAL,
                    call_expiry         TEXT,
                    call_delta          REAL,
                    call_theta          REAL,
                    call_vega           REAL,
                    call_iv             REAL,
                    call_ask            REAL,
                    call_oi             INTEGER,

                    -- Put leg
                    put_symbol          TEXT,
                    put_strike          REAL,
                    put_expiry          TEXT,
                    put_delta           REAL,
                    put_theta           REAL,
                    put_vega            REAL,
                    put_iv              REAL,
                    put_ask             REAL,
                    put_oi              INTEGER,

                    -- Entry pricing
                    total_cost          REAL,
                    stock_price_at_scan REAL,

                    -- Resolution (filled in by resolve command)
                    stock_price_at_earnings  REAL,
                    actual_move_pct          REAL,
                    breakeven_pct            REAL,
                    pnl_estimate             REAL,
                    resolved_date            TEXT,
                    notes                    TEXT,

                    -- Dedup key
                    UNIQUE(ticker, earnings_date, call_symbol, put_symbol)
                )
            """)

    def save_candidate(
        self,
        candidate: StraddleCandidate,
        stock_price: float,
    ) -> bool:
        """Insert candidate. Returns True if inserted, False if duplicate."""
        c = candidate
        current_iv = (c.call.iv + c.put.iv) / 2
        with self._conn() as conn:
            try:
                conn.execute("""
                    INSERT INTO trades (
                        ticker, scan_date, earnings_date, days_to_earnings,
                        iv_rank, vega_theta_ratio, current_iv,
                        call_symbol, call_strike, call_expiry, call_delta,
                        call_theta, call_vega, call_iv, call_ask, call_oi,
                        put_symbol, put_strike, put_expiry, put_delta,
                        put_theta, put_vega, put_iv, put_ask, put_oi,
                        total_cost, stock_price_at_scan
                    ) VALUES (
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )
                """, (
                    c.ticker, str(date.today()), str(c.earnings_date), c.days_to_earnings,
                    c.iv_rank, c.vega_theta_ratio, current_iv,
                    c.call.symbol, c.call.strike, str(c.call.expiration), c.call.delta,
                    c.call.theta, c.call.vega, c.call.iv, c.call.ask, c.call.open_interest,
                    c.put.symbol, c.put.strike, str(c.put.expiration), c.put.delta,
                    c.put.theta, c.put.vega, c.put.iv, c.put.ask, c.put.open_interest,
                    c.total_cost, stock_price,
                ))
                return True
            except sqlite3.IntegrityError:
                return False  # duplicate

    def get_pending(self) -> list[sqlite3.Row]:
        """Return all trades still pending resolution."""
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM trades WHERE status = 'pending' ORDER BY earnings_date"
            ).fetchall()

    def resolve_trade(
        self,
        trade_id: int,
        stock_price_at_earnings: float,
        stock_price_at_scan: float,
        total_cost: float,
    ) -> str:
        """Resolve a pending trade. Returns the new status."""
        actual_move_pct = abs(stock_price_at_earnings - stock_price_at_scan) / stock_price_at_scan * 100

        if total_cost <= 0 or stock_price_at_scan <= 0:
            status = "unresolvable"
            breakeven_pct = None
            pnl_estimate = None
            notes = "No cost data — enter manually to resolve"
        else:
            breakeven_pct = (total_cost / stock_price_at_scan) * 100
            pnl_estimate = actual_move_pct - breakeven_pct
            status = "resolved_win" if pnl_estimate > 0 else "resolved_loss"
            notes = None

        with self._conn() as conn:
            conn.execute("""
                UPDATE trades SET
                    status = ?,
                    stock_price_at_earnings = ?,
                    actual_move_pct = ?,
                    breakeven_pct = ?,
                    pnl_estimate = ?,
                    resolved_date = ?,
                    notes = ?
                WHERE id = ?
            """, (
                status, stock_price_at_earnings, actual_move_pct,
                breakeven_pct, pnl_estimate, str(date.today()), notes,
                trade_id,
            ))
        return status

    def get_all(self) -> list[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM trades ORDER BY earnings_date DESC"
            ).fetchall()

    def get_stats(self) -> dict:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status='resolved_win' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN status='resolved_loss' THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN status='unresolvable' THEN 1 ELSE 0 END) as unresolvable,
                    AVG(CASE WHEN status IN ('resolved_win','resolved_loss') THEN pnl_estimate END) as avg_pnl,
                    AVG(CASE WHEN status='resolved_win' THEN pnl_estimate END) as avg_win,
                    AVG(CASE WHEN status='resolved_loss' THEN pnl_estimate END) as avg_loss
                FROM trades
            """).fetchone()
            return dict(rows)