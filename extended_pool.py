from abc import ABC
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import chain
from typing import Self, Iterable, Collection, Sequence

from network import Pool as NetworkPool, DEX


TICK_MERGE_MAXIMUM_CHANGE = 0.05


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


@dataclass(frozen=True)
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
            return abs(b.change) <= min(abs(a.change), abs(c.change)) and abs(b.change) <= TICK_MERGE_MAXIMUM_CHANGE
        return False


@dataclass(frozen=True)
class Pattern:
    min_change: float
    min_duration: timedelta = None
    max_duration: timedelta = None

    def match(self, trend: Trend, ticks: Sequence[BaseTick]):

        if trend.change >= self.min_change >= 0 or 0 >= self.min_change >= trend.change:

            duration = ticks[trend.end].timestamp - ticks[trend.beginning].timestamp

            if self.min_duration and duration < self.min_duration:
                return False

            if self.max_duration and duration > self.max_duration:
                return False

            return True

        return False


def _fraction(percent):
    return percent / 100


_UPTREND = [
    Pattern(_fraction(5), min_duration=timedelta(minutes=20)),
]

_DUMP = [
    Pattern(_fraction(-5),  max_duration=timedelta(minutes=10)),
]

_DOWNTREND_REVERSAL = [
    Pattern(_fraction(-10), min_duration=timedelta(minutes=20)),
    Pattern(_fraction(3)),
]

PATTERNS = [_DUMP, _UPTREND, _DOWNTREND_REVERSAL]


class Chart:
    def __init__(self):
        self.ticks: CircularList[BaseTick] = CircularList(capacity=CHART_MAX_TICKS)
        self.trends: deque[Trend] | None = None
        self.signal_end_timestamp: datetime | None = None

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

        trends = deque(Trend(c, beginning=i - 1 if i else 0, end=i) for i, c in enumerate(changes))

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
                trends.insert(i + 1, t2 + t3)
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

    def has_signal(self, only_new=False):
        self._construct_segments()

        if len(self.trends) < max(map(len, PATTERNS)):
            return False

        for pattern in PATTERNS:
            last_trends = [self.trends[i] for i in range(-len(pattern), 0)]

            if all([
                p.match(t, self.ticks)
                for p, t in zip(pattern, last_trends)
            ]):
                if only_new:
                    first_timestamp = self.ticks[last_trends[0].beginning].timestamp

                    if first_timestamp < self.signal_end_timestamp:
                        return False

                    self.signal_end_timestamp = self.ticks[last_trends[-1].end].timestamp

                return True

        return False

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
