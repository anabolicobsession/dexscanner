from datetime import timedelta
from itertools import chain

from network import Pool, Network, Token, TimePeriodsData, DEX
from pools import Pools
from api.geckoterminal_api import GeckoTerminalAPI, PoolSource, SortBy, Pool as DEXScreenerPool, Timeframe, Currency
from api.dex_screener_api import DEXScreenerAPI
import settings


def make_batches(sequence: list, n: int) -> list[list]:
    return [sequence[i:n + i] for i in range(0, len(sequence), n)]


class PoolsWithAPI(Pools):

    REQUESTS_RESET_TIMEOUT = timedelta(seconds=60)
    CHECK_FOR_NEW_TOKENS_EVERY_UPDATE = 20
    APPLY_FILTER_EVERY_UPDATE = 20

    def __init__(self, **params):
        super().__init__(**params)
        self.geckoterminal_api = GeckoTerminalAPI()
        self.dex_screener_api = DEXScreenerAPI()
        self.update_counter = 0
        
    async def close_api_sessions(self):
        await self.geckoterminal_api.close()
        await self.dex_screener_api.close()

    def _increment_update_counter(self):
        self.update_counter += 1

    def _satisfy(self, every_update):
        return self.update_counter % every_update == 0

    @staticmethod
    def _dex_screener_pool_to_network_pool(p: DEXScreenerPool) -> Pool:
        return Pool(
            network=Network.from_id(p.network_id),
            address=p.address,
            base_token=Token(
                network=Network.from_id(p.network),
                address=p.base_token.address,
                ticker=p.base_token.ticker,
                name=p.base_token.name,
            ),
            quote_token=Token(
                network=Network.from_id(p.network),
                address=p.quote_token.address,
                ticker=p.quote_token.ticker,
                name=p.quote_token.name,
            ),

            price_usd=p.price_usd,
            price_native=p.price_native,
            liquidity=p.liquidity.total,
            volume=p.volume.h24,
            fdv=p.fdv,

            price_change=TimePeriodsData(
                m5=p.price_change.m5,
                h1=p.price_change.h1,
                h6=p.price_change.h6,
                h24=p.price_change.h24,
            ),
            dex=DEX(p.dex_id),
            creation_date=p.creation_date,
        )

    async def update_using_api(self):
        if self._satisfy(PoolsWithAPI.APPLY_FILTER_EVERY_UPDATE):
            self.apply_filter()

        addresses = []
        if self._satisfy(PoolsWithAPI.CHECK_FOR_NEW_TOKENS_EVERY_UPDATE):

            for source in (PoolSource.TOP, PoolSource.TRENDING):
                addresses.extend([p.address for p in await self.geckoterminal_api.get_pools(
                    settings.NETWORK.get_id(),
                    pool_source=source,
                    pages=GeckoTerminalAPI.ALL_PAGES,
                    sort_by=SortBy.VOLUME,
                )])

        self.update(list(chain(*[
            map(self._dex_screener_pool_to_network_pool, await self.dex_screener_api.get_pools(settings.NETWORK.get_id(), batch))
            for batch in make_batches(addresses, DEXScreenerAPI.MAX_ADDRESSES)
        ])))

        priority_list = [(p.address, p.volume * p.price_change.h1) for p in self]
        priority_list.sort(key=lambda t: t[1], reverse=True)

        for address in map(lambda t: t[0], priority_list[:self.geckoterminal_api.get_requests_left()]):
            await self.geckoterminal_api.get_ohlcv(
                settings.NETWORK.get_id(),
                pool_address=address,
                timeframe=Timeframe.Minute.ONE,
                currency=Currency.TOKEN,
            )

        self._increment_update_counter()
        self.geckoterminal_api.reset_request_counter()
        self.dex_screener_api.reset_request_counter()