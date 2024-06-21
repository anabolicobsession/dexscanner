from abc import ABC
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from itertools import chain
from typing import Self, Iterable, Collection

from network import Pool as NetworkPool, DEX


TICK_MERGE_MAXIMUM_CHANGE = 0.03


Index = int


CHART_MAX_TICKS = 2000


class TimeGapBetweenCharts(Exception):
    ...


class OutdatedData(Exception):
    ...


@dataclass(frozen=True)
class _AbstractDataclass(ABC):
    def __new__(cls, *args, **kwargs):
        if cls == _AbstractDataclass or cls.__bases__[0] == _AbstractDataclass:
            raise TypeError('Can\'t instantiate an abstract class')
        return super().__new__(cls)


@dataclass(frozen=True)
class BaseTick(_AbstractDataclass):
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


class CircularList(list):
    def __init__(self, capacity):
        super().__init__([None] * capacity)
        self.beginning = 0
        self.size = 0
        self.capacity = capacity

    def _get_index(self, shift):
        base = self.beginning if shift >= 0 else self.beginning + self.size
        return (base + shift) % self.capacity

    def _is_integral(self):
        return self.beginning + self.size <= self.capacity

    def __len__(self):
        return self.size

    def __getitem__(self, index: Index | slice):
        if isinstance(index, int):
            if not -self.size < index < self.size:
                raise IndexError(f'Index out of range: {index}')
            return super().__getitem__(self._get_index(index))
        else:
            start = index.start if index.start is not None else 0
            stop = index.stop if index.stop is not None else self.size

            if start > stop or start < 0 or stop > self.size:
                raise IndexError(f'Slice out of range: {start}:{stop}')

            start = self._get_index(start)
            stop = self._get_index(stop)

            if self._is_integral() or stop > start or index.start == index.stop:
                return super().__getitem__(slice(start, stop))
            else:
                return list(chain(
                    super().__getitem__(slice(start, self.capacity)),
                    super().__getitem__(slice(stop)),
                ))

    def __iter__(self):
        for index in range(self.size):
            yield super().__getitem__(self._get_index(index))

    def __repr__(self):
        return '[' + ', '.join([repr(item) for item in self]) + ']'

    def get_internal_repr(self):
        super_class = super()
        internal = [repr(super_class.__getitem__(i)) for i in range(self.capacity)]
        return '[' + ', '.join(internal) + ']'

    def append(self, item):
        index = self._get_index(self.size)

        if self.size < self.capacity:
            self.size += 1
        else:
            self.beginning = self._get_index(1)

        self[index] = item

    def extend(self, iterable: Iterable):
        for item in iterable:
            self.append(item)

    def set(self, index: Index, iterable: Collection):
        if not 0 <= index <= self.size:
            raise IndexError(f'Index out of range: {index}')

        if index + len(iterable) >= self.size:
            self.size = index
            self.extend(iterable)
        else:
            raise IndexError(
                'Too few items to set or too small index. '
                'New items must override existing items for a small enough index, otherwise behaviour is undefined'
            )

    def pop(self, index=None):
        if self.size:
            self[self._get_index(self.size - 1)] = None
            self.size -= 1
        else:
            raise IndexError('No items to pop')


@dataclass
class Trend:
    change: float
    beginning: Index
    end: Index

    def __add__(self, other) -> Self:
        return Trend(self.change + other.change, self.beginning, other.end)

    @staticmethod
    def have_same_trend(a, b):
        return a.change * b.change >= 0

    @staticmethod
    def can_be_merged(a, b, c):
        if Trend.have_same_trend(a, c) and not Trend.have_same_trend(a, b):
            return a.change + c.change >= b.change and b.change <= TICK_MERGE_MAXIMUM_CHANGE
        return False


class Chart:
    def __init__(self):
        self.ticks: CircularList[BaseTick] = CircularList(capacity=CHART_MAX_TICKS)
        self.trends: deque[Trend] | None = None

    def __repr__(self):
        return f'{type(self).__name__}({[repr(t) for t in self.ticks]})'

    def update(self, ticks: BaseTick | Collection[BaseTick]):
        if isinstance(ticks, BaseTick):
            ticks = [ticks]

        if ticks:
            self.ticks.set(
                next(
                    (
                        i for i in range(len(self.ticks))
                        if ticks[0].timestamp >= self.ticks[i].timestamp
                    ),
                    len(self.ticks)
                ),
                ticks
            )

    def _construct_segments(self):
        prices = [c.price for c in self.ticks]
        previous_prices = [0, *prices[:-1]]

        changes = [
            (current - previous) / previous if previous else 0 for current, previous in zip(
                prices,
                previous_prices,
            )
        ]

        trends = deque(Trend(c, beginning=i, end=i) for i, c in enumerate(changes))

        i = 0
        while i + 2 < len(trends):
            t1, t2, t3 = trends[i], trends[i + 1], trends[i + 2]

            if Trend.have_same_trend(t1, t2):
                trends.remove(t1)
                trends.remove(t2)
                trends.insert(i, t1 + t2)
                i = max(i - 2, 0)
                continue

            if Trend.have_same_trend(t2, t3):
                trends.remove(t2)
                trends.remove(t3)
                trends.insert(i, t2 + t3)
                i = max(i - 2, 0)
                continue

            if Trend.can_be_merged(t1, t2, t3):
                trends.remove(t1)
                trends.remove(t2)
                trends.remove(t3)
                trends.insert(i, t1 + t2 + t3)
                i = max(i - 2, 0)
                continue

            i += 1

        self.trends = trends

    def get_ticks_separated_by_trend(self) -> tuple[list[Trend], list[Trend]]:
        uptrends = []
        downtrends = []

        for t in self.trends:
            if t.change > 0:
                uptrends.append(t)
            else:
                downtrends.append(t)

        return uptrends, downtrends

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
