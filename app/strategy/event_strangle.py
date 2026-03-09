"""
Event-Driven Long Strangle Strategy (`longStrangleEvent`)

Same as longStrangleEarnings but the catalyst is discovered by Claude via web search
rather than an earnings calendar.
"""
from __future__ import annotations

from app.config.config import config

from app.data.provider import Provider
from app.strategy.iv_strangle import LongStrangleEarningsStrategy


class LongStrangleEventStrategy(LongStrangleEarningsStrategy):
    """
    Reuses all filtering logic from LongStrangleEarningsStrategy.
    Overrides generate_candidates to use Claude event discovery
    instead of the earnings calendar.
    """

    def generate_candidates(
        self,
        market: Provider,
        earnings: Provider,
        ticker_filter: str | None = None,
        events: list | None = None,
    ) -> list:
        if events is None:
            return []

        candidates = []
        seen = set()

        for event in events:
            for ticker in event.tickers:
                if ticker_filter and ticker.upper() != ticker_filter.upper():
                    continue
                if ticker not in config.STOCKS:
                    print(f"  Skipping {ticker} — not on watchlist")
                    continue

                key = (ticker, str(event.event_date))
                if key in seen:
                    continue
                seen.add(key)

                print(f"  Scanning {ticker} [{event.event}  {event.event_date}]...")
                try:
                    result = self._evaluate(market, ticker, event.event_date)
                    if result:
                        candidates.append(result)
                except Exception as ex:
                    print(f"  Skipping {ticker}: {ex}")

        return candidates