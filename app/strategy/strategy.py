from app.data.polygon import PolygonProvider

class Strategy:
    def generate_candidates(self, provider: PolygonProvider):
        raise NotImplementedError

    def simulate_trade(self, provider: PolygonProvider, candidate):
        raise NotImplementedError