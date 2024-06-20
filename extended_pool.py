from dataclasses import dataclass
from datetime import datetime
from itertools import chain
from typing import Self, Iterable

from network import Pool as NetworkPool, DEX


Index = int


class TimeGapBetweenCharts(Exception):
    ...


class OutdatedData(Exception):
    ...


@dataclass(frozen=True)
class BaseTick:
    timestamp: datetime
    price: float

    def __repr__(self):
        return f'{self.__name__}({self.timestamp}, {self.price})'


@dataclass(frozen=True)
class Tick(BaseTick):
    volume: float


@dataclass(frozen=True)
class IncompleteTick(BaseTick):
    ...


@dataclass
class Segment:
    change: float
    beginning: Index
    end: Index


class CircularList(list):
    def __init__(self, capacity):
        super().__init__()
        self.capacity = capacity
        self.next = 0
        self.iterator = None

    def __iter__(self):
        if len(self) < self.capacity or len(self) == self.capacity and self.next == 0:
            return super().__iter__()
        else:
            return chain(self[self.next:], self[:self.next])

    def __repr__(self):
        return '[' + ', '.join([repr(item) for item in self]) + ']'

    def append(self, item):
        if len(self) < self.capacity:
            super().append(item)
        else:
            self[self.next] = item

        self.next = (self.next + 1) % self.capacity

    def extend(self, iterable: Iterable):
        for item in iterable:
            self.append(item)


class Chart:
    def __init__(self):
        self.ticks: list[BaseTick] = []
        self.segments = None

    def update(self, ticks: Tick | list[Tick]):
        if not isinstance(ticks, Tick):

            if not self.ticks:
                self.ticks = ticks
            else:
                oldest_timestamp = ticks[0].timestamp

                if idx_to_insert := next(
                    (i for i in range(len(self.ticks)) if self.ticks[i].timestamp == oldest_timestamp),
                    None
                ):
                    self.ticks[idx_to_insert:] = ticks
                else:
                    raise TimeGapBetweenCharts('Charts are too far in time from each other to be concatenated')
        else:
            if self.ticks:
                new_candlestick = ticks
                last_candlestick = self.ticks[-1]

                if   new_candlestick.timestamp >  last_candlestick.timestamp:
                    self.ticks.append(new_candlestick)
                elif new_candlestick.timestamp == last_candlestick.timestamp:
                    last_candlestick.price = new_candlestick.price
                else:
                    raise OutdatedData(f'Candlestick is too outdated to be inserted: {new_candlestick}')

    def _construct_segments(self):
        prices = [c.price for c in self.ticks]
        previous_prices = [0, *prices[:-1]]

        changes = [
            (current - previous) / previous if previous else 0 for current, previous in zip(
                prices,
                previous_prices,
            )
        ]

        segments = [Segment(c, beginning=i, end=i) for i, c in enumerate(changes)]

    def has_signal(self):
        pass


@dataclass
class TimePeriodsData:
    m5:  float = None
    h1:  float = None
    h6:  float = None
    h24: float = None


@dataclass
class Pool(NetworkPool):
    price_usd: float
    price_native: float
    liquidity: float
    volume: float
    fdv: float

    price_change: TimePeriodsData
    dex: DEX
    creation_date: datetime

    chart: Chart = Chart()

    def update(self, other: Self):
        super().update(other)

        self.price_usd = other.price_usd
        self.price_native = other.price_native
        self.liquidity = other.liquidity
        self.volume = other.volume
        self.fdv = other.fdv

        self.price_change = other.price_change
        self.dex.update(other.dex)
        self.creation_date = other.creation_date
