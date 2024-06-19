from datetime import datetime
from enum import Enum
from typing import Self
from dataclasses import dataclass


Id = str
Address = str


class UnknownNetwork(Exception):
    ...


class TimeGapBetweenCharts(Exception):
    ...


class OutdatedData(Exception):
    ...


@dataclass
class _NetworkValue:
    id: Id
    native_token_address: Address


class Network(Enum):
    TON = _NetworkValue('ton', 'EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c')

    def get_id(self) -> Id:
        return self.value.id

    def get_native_token_address(self) -> Address:
        return self.value.native_token_address

    @classmethod
    def from_id(cls, id: Id) -> Self | None:
        for network in cls:
            if network.get_id() == id:
                return network
        raise UnknownNetwork(id)


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
        return self.address == self.network.get_native_token_address()


@dataclass
class DEX:
    id: Id
    name: str = None

    def __eq__(self, other):
        return isinstance(other, DEX) and self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def update(self, other: Self):
        self.name = other.name


@dataclass
class TimePeriodsData:
    m5:  float = None
    h1:  float = None
    h6:  float = None
    h24: float = None


@dataclass
class Candlestick:
    timestamp: datetime
    price: float
    volume: float = None

    def __repr__(self):
        return f'{self.__name__}({self.timestamp}, {self.price})'


@dataclass
class Segment:
    change: float


class Chart:
    def __init__(self):
        self.candlesticks: list[Candlestick] = []

    def update(self, candlesticks: Candlestick | list[Candlestick]):
        if not isinstance(candlesticks, Candlestick):

            if not self.candlesticks:
                self.candlesticks = candlesticks
            else:
                oldest_timestamp = candlesticks[0].timestamp

                if idx_to_insert := next(
                    (i for i in range(len(self.candlesticks)) if self.candlesticks[i].timestamp == oldest_timestamp),
                    None
                ):
                    self.candlesticks[idx_to_insert:] = candlesticks
                else:
                    raise TimeGapBetweenCharts('Charts are too far in time from each other to be concatenated')
        else:
            if self.candlesticks:
                new_candlestick = candlesticks
                last_candlestick = self.candlesticks[-1]

                if   new_candlestick.timestamp >  last_candlestick.timestamp:
                    self.candlesticks.append(new_candlestick)
                elif new_candlestick.timestamp == last_candlestick.timestamp:
                    last_candlestick.price = new_candlestick.price
                else:
                    raise OutdatedData(f'Candlestick is too outdated to be inserted: {new_candlestick}')

    def has_signal(self):
        pass


@dataclass
class Pool:
    network: Network
    address: Address
    base_token: Token
    quote_token: Token

    price_usd: float
    price_native: float
    liquidity: float
    volume: float
    fdv: float

    price_change: TimePeriodsData
    dex: DEX
    creation_date: datetime

    chart: Chart = Chart()

    def __eq__(self, other):
        return isinstance(other, Pool) and self.network == other.network and self.address == other.address

    def __hash__(self):
        return hash((self.network, self.address))

    def __repr__(self):
        return self.base_token.ticker + '/' + self.quote_token.ticker

    def update(self, other: Self):
        self.base_token.update(other.base_token)
        self.quote_token.update(other.quote_token)

        self.price_usd = other.price_usd
        self.price_native = other.price_native
        self.liquidity = other.liquidity
        self.volume = other.volume
        self.fdv = other.fdv

        self.price_change = other.price_change
        self.dex.update(other.dex)
        self.creation_date = other.creation_date
