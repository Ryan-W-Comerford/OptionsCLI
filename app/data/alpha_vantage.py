import csv
import os
import requests
from datetime import date, datetime, timedelta

from app.data.provider import Provider

CACHE_FILE = "app/data/cache/earnings_cache.csv"
CACHE_TTL_HOURS = 12


class AlphaProvider(Provider):
    def __init__(self, av_api_key: str):
        self.av_api_key = av_api_key
        self.earnings_url = (
            "https://www.alphavantage.co/query"
            f"?function=EARNINGS_CALENDAR&horizon=3month&apikey={av_api_key}"
        )

    def _cache_is_fresh(self) -> bool:
        """Returns True if cache exists and is younger than CACHE_TTL_HOURS."""
        if not os.path.exists(CACHE_FILE):
            return False
        age_seconds = datetime.now().timestamp() - os.path.getmtime(CACHE_FILE)
        return age_seconds < CACHE_TTL_HOURS * 3600

    def _filter_rows(self, rows: list[dict], today: date, end: date) -> list[dict]:
        upcoming = []
        for row in rows:
            ticker = row.get("symbol")
            earnings_date_str = row.get("reportDate")
            if not ticker or not earnings_date_str:
                continue
            try:
                edate = datetime.fromisoformat(earnings_date_str).date()
            except ValueError:
                continue
            if today <= edate <= end:
                upcoming.append({"ticker": ticker, "date": edate})
        return upcoming

    def _read_cache(self) -> list[dict]:
        with open(CACHE_FILE, newline="") as f:
            return list(csv.DictReader(f))

    def _fetch_and_cache(self) -> list[dict]:
        r = requests.get(self.earnings_url, timeout=10)
        r.raise_for_status()

        decoded = r.content.decode("utf-8")
        reader = csv.DictReader(decoded.splitlines())
        rows = list(reader)

        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=reader.fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        return rows

    def get_upcoming_earnings(self, within_days: int) -> list[dict]:
        today = date.today()
        end = today + timedelta(days=within_days)
        rows = self._read_cache() if self._cache_is_fresh() else self._fetch_and_cache()
        return self._filter_rows(rows, today, end)

    # Not applicable for this provider
    def get_stock_price(self, ticker: str) -> float:
        raise NotImplementedError("Use MassiveProvider for stock prices")