from dataclasses import dataclass
from datetime import datetime


Index = int


class TimeGapBetweenCharts(Exception):
    ...


class OutdatedData(Exception):
    ...


@dataclass
class _BaseTick:
    timestamp: datetime
    price: float

    def __repr__(self):
        return f'{self.__name__}({self.timestamp}, {self.price})'


class Tick(_BaseTick):
    volume: float


class IncompleteTick(_BaseTick):
    ...


@dataclass
class Segment:
    change: float
    beginning: Index
    end: Index


class Chart:
    def __init__(self):
        self.ticks: list[Tick] = []
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
