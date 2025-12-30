from app.data.polygon import PolygonProvider
from app.config.config import config
from app.strategy.iv_straddle import LongStraddleIVStrategy
from app.strategy.strategy import Strategy

strategy_map = {
    "longStraddleIV": LongStraddleIVStrategy
}

class OptionsApp:
    def __init__(self):
        self.provider = PolygonProvider(config.POLYGON_API_KEY)

    def get_strategy(self, name: str) -> Strategy:
        if name not in strategy_map:
            raise ValueError(
                f"Unknown strategy used '{name}'. "
                "Available: longStraddleIV"
            )
        
        return strategy_map[name]()
