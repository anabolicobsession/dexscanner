from typing import Self
from dataclasses import dataclass

import settings
from utils import DateTime


Network = str
Address = str


@dataclass
class Token:
    network: Network
    address: Address
    ticker: str = None
    name: str = None

    def __eq__(self, other):
        return isinstance(other, Token) and self.network == other.network and self.address == other.address

    def __hash__(self):
        return hash((self.network, self.address))

    def __repr__(self):
        return self.ticker

    def update(self, other: Self):
        self.ticker = other.ticker
        self.name = other.name

    def is_native_currency(self):
        return self.address == settings.NETWORK_NATIVE_CURRENCY_ADDRESS


@dataclass
class DEX:
    id: str
    name: str = None

    def __eq__(self, other):
        return isinstance(other, DEX) and self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def update(self, dex: Self):
        self.name = dex.name


@dataclass
class TimePeriodsData:
    m5:  float = None
    h1:  float = None
    h6:  float = None
    h24: float = None


@dataclass
class Pool:
    address: Address
    base_token: Token = None
    quote_token: Token = None


    def __init__(
            self,
            quote_token,
            dex,
            creation_date: DateTime,

            price,
            price_in_native_token,
            fdv,
            market_cap,
            volume,
            liquidity,
            transactions,
            makers,

            price_change: TimePeriodsData,
            buys_sells_ratio: TimePeriodsData,
            buyers_sellers_ratio: TimePeriodsData,
            volume_ratio: TimePeriodsData
    ):
        self.address: Address = address
        self.base_token: Token = base_token
        self.quote_token: Token = quote_token
        self.dex: DEX = dex
        self.creation_date: DateTime = creation_date

        self.price = price
        self.price_in_native_token = price_in_native_token
        self.fdv = fdv
        self.market_cap = market_cap
        self.volume = volume
        self.liquidity = liquidity
        self.transactions = transactions
        self.makers = makers

        self.price_change: TimePeriodsData = price_change
        self.buys_sells_ratio: TimePeriodsData = buys_sells_ratio
        self.buyers_sellers_ratio: TimePeriodsData = buyers_sellers_ratio
        self.volume_ratio: TimePeriodsData = volume_ratio

    def __eq__(self, other):
        if isinstance(other, Pool):
            return self.address == other.address
        return False

    def __hash__(self):
        return self.address.__hash__()

    def __repr__(self):
        return self.base_token.ticker + '/' + self.quote_token.ticker


