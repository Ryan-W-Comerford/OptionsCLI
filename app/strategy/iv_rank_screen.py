"""
IV Rank Screen (`ivRankScreen`)

A lightweight scanner that flags any watchlist stock with elevated implied
volatility right now — regardless of earnings proximity. Useful for spotting
stocks pricing in a big move for any reason: earnings, FDA, legal, macro.

No options chain fetch needed — uses only historical price aggregates and
the stock snapshot, making it fast and cheap on API calls.

Output: ranked list of tickers by IV rank, filtered to a configurable
        minimum threshold (default: IV rank >= 50).
"""
from __future__ import annotations
from datetime import date, timedelta

from app.config.config import config
from app.data.provider import Provider
from app.models.models import IVRankAlert
from app.strategy.strategy import Strategy

# Minimum IV rank to surface an alert — lower than straddle entry to catch more names
IV_SCREEN_MIN_RANK: float = 50.0


class IVRankScreenStrategy(Strategy):
    def generate_candidates(
        self,
        market: Provider,
        earnings: Provider,
        ticker_filter: str | None = None,
    ) -> list[IVRankAlert]:
        tickers = [ticker_filter.upper()] if ticker_filter else config.STOCKS
        alerts = []
        today = date.today()

        for ticker in tickers:
            print(f"  Scanning {ticker}...")
            try:
                spot = market.get_stock_price(ticker)

                iv_hist = market.get_historical_iv(
                    ticker,
                    start=today - timedelta(days=252),
                    end=today - timedelta(days=1),
                )
                if not iv_hist:
                    print(f"  Skipping {ticker}: insufficient historical data")
                    continue

                # Use most recent realized vol window as current IV proxy
                current_iv = iv_hist[-1]
                iv_rank = market.get_iv_rank(iv_hist, current_iv)

                if iv_rank < IV_SCREEN_MIN_RANK:
                    continue

                alerts.append(IVRankAlert(
                    ticker=ticker,
                    iv_rank=round(iv_rank, 1),
                    current_iv=round(current_iv, 4),
                    spot=round(spot, 2),
                    iv_52w_low=round(min(iv_hist), 4),
                    iv_52w_high=round(max(iv_hist), 4),
                ))
            except Exception as ex:
                print(f"  Skipping {ticker}: {ex}")

        return sorted(alerts, key=lambda a: a.iv_rank, reverse=True)