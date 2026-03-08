from abc import ABC, abstractmethod


class Provider(ABC):
    """Abstract base class for all data providers."""

    @abstractmethod
    def get_stock_price(self, ticker: str) -> float:
        pass

    @abstractmethod
    def get_upcoming_earnings(self, within_days: int) -> list[dict]:
        pass