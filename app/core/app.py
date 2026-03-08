from app.config.config import config
from app.data.alpha_vantage import AlphaProvider
from app.data.massive import MassiveProvider
from app.data.trade_store import TradeStore
from app.strategy.iv_straddle import LongStraddleIVStrategy
from app.strategy.iv_strangle import LongStrangleIVStrategy
from app.strategy.iv_rank_screen import IVRankScreenStrategy
from app.strategy.strategy import Strategy

strategy_map = {
    "longStraddleIV": LongStraddleIVStrategy,
    "longStrangleIV": LongStrangleIVStrategy,
    "ivRankScreen":   IVRankScreenStrategy,
}


class OptionsApp:
    def __init__(self):
        self.market   = MassiveProvider(config.POLYGON_API_KEY)
        self.earnings = AlphaProvider(config.ALPHA_API_KEY)
        self.store    = TradeStore(config.TRADE_DB_PATH)

    def get_strategy(self, name: str) -> Strategy:
        if name not in strategy_map:
            available = ", ".join(strategy_map.keys())
            raise ValueError(f"Unknown strategy '{name}'. Available: {available}")
        return strategy_map[name]()

    def upcoming_earnings_count(self) -> int:
        return len(self.earnings.get_upcoming_earnings(config.EARNINGS_LOOKAHEAD_DAYS))