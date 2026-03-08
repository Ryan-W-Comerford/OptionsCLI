import os

import yaml


class Config:
    def __init__(self):
        secrets_path = os.environ.get("SECRETS_FILE_PATH")
        if not secrets_path:
            raise EnvironmentError("SECRETS_FILE_PATH environment variable is not set")
        if not os.path.exists(secrets_path):
            raise FileNotFoundError(f"Secrets file not found: {secrets_path}")

        with open(secrets_path) as f:
            key_file = yaml.safe_load(f)

        self.POLYGON_API_KEY: str = key_file["POLYGON_API_KEY"]
        self.ALPHA_API_KEY: str = key_file["ALPHA_API_KEY"]

        # High Beta S&P 500 stocks that are liquid with reasonable option pricing
        self.STOCKS: list[str] = [
            "AMD", "TSM", "INTC", "CRM", "ADBE", "ORCL", "NOW",
            "META", "NFLX", "AMZN", "EBAY", "PYPL", "COIN",
            "MU", "QCOM", "AVGO", "BA", "CAT", "DE", "UNH",
            "ABBV", "MRK", "XOM", "CVX", "SLB",
        ]

        self.EARNINGS_LOOKAHEAD_DAYS: int = 30
        self.TARGET_DTE_RANGE: tuple[int, int] = (15, 50)

        self.MIN_IV_RANK: float = 30.0
        self.MAX_ENTRY_IV_RANK: float = 80.0
        self.EXIT_IV_RANK: float = 85.0

        self.MIN_VEGA_THETA_RATIO: float = 0.0  # disabled — unreliable with delayed greeks
        self.ATM_DELTA_RANGE: tuple[float, float] = (0.35, 0.65)

        self.MIN_OPTION_VOLUME: int = 50
        self.MIN_OPEN_INTEREST: int = 250
        self.MAX_BID_ASK_SPREAD_PCT: float = 0.15

        self.EXIT_DAYS_BEFORE_EARNINGS: int = 2
        self.TARGET_PNL: float = 0.30

        # Trade history DB — SQLite, auto-created on first run. Set TRADE_DB_PATH in secrets.yaml
        self.TRADE_DB_PATH: str = key_file.get("TRADE_DB_PATH", "app/data/history/trades.db")


config = Config()
# NOTE: appending TRADE_DB_PATH — paste into Config.__init__ before config = Config()