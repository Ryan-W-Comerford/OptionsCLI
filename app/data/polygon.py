import requests
from datetime import date, timedelta
from app.models.models import OptionContract
from app.data.provider import Provider

class PolygonProvider(Provider):
    def __init__(self, api_key: str):
        self.key = api_key
        self.base = "https://api.polygon.io"

    def get_upcoming_earnings(self, within_days: int):
        end = date.today() + timedelta(days=within_days)
        url = f"{self.base}/v3/reference/earnings"
        r = requests.get(url, params={
            "apiKey": self.key,
            "from": date.today().isoformat(),
            "to": end.isoformat(),
            "limit": 1000
        }).json()
        return [
            {"ticker": e["ticker"], "date": date.fromisoformat(e["earnings_date"])}
            for e in r.get("results", [])
        ]

    def get_stock_price(self, ticker: str) -> float:
        r = requests.get(
            f"{self.base}/v2/aggs/ticker/{ticker}/prev",
            params={"apiKey": self.key}
        ).json()
        return r["results"][0]["c"]

    def get_option_chain(self, ticker: str):
        r = requests.get(
            f"{self.base}/v3/reference/options/contracts",
            params={"apiKey": self.key, "underlying_ticker": ticker, "limit": 1000}
        ).json()

        chain = []
        for c in r.get("results", []):
            g = c.get("greeks")
            if not g:
                continue
            chain.append(OptionContract(
                symbol=c["ticker"],
                strike=c["strike_price"],
                expiration=date.fromisoformat(c["expiration_date"]),
                option_type=c["contract_type"],
                delta=g.get("delta", 0),
                theta=g.get("theta", 0),
                vega=g.get("vega", 0),
                iv=c.get("implied_volatility", 0),
            ))
        return chain

    def get_historical_iv(self, ticker: str, start: date, end: date):
        """Proxy: use historical 30d ATM IV from Polygon aggregates"""
        r = requests.get(
            f"{self.base}/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}",
            params={"apiKey": self.key}
        ).json()

        return [abs(x["h"] - x["l"]) / x["o"] for x in r.get("results", [])]

    def get_iv_rank(self, iv_series: list[float], current_iv: float) -> float:
        low, high = min(iv_series), max(iv_series)
        return 100 * (current_iv - low) / (high - low) if high != low else 50

