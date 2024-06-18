import logging
from datetime import timedelta

from api.geckoterminal_api import GeckoTerminalAPI, PoolSource, SortBy
from api.dex_screener_api import DEXScreenerAPI
import settings
from pools import Pools

NETWORK = settings.NETWORK


logger = logging.getLogger(__name__)


class PoolsWithAPI(Pools):
    REQUESTS_TIMEOUT_RESET = timedelta(seconds=60)
    CHECK_FOR_NEW_TOKENS_EVERY_UPDATE = 30

    def __init__(self, **params):
        super().__init__(**params)
        self.geckoterminal_api = GeckoTerminalAPI()
        self.dex_screener_api = DEXScreenerAPI()
        self.update_counter = 0
        
    async def close_api_sessions(self):
        await self.geckoterminal_api.close()
        await self.dex_screener_api.close()

    async def update_using_api(self):
        geckoterminal_api_requests = 0
        dex_screener_api_requests = 0
        
        if self.update_counter % PoolsWithAPI.CHECK_FOR_NEW_TOKENS_EVERY_UPDATE == 0:
            pools = await self.geckoterminal_api.get_pools(
                NETWORK,
                pool_source=PoolSource.TOP,
                pages=GeckoTerminalAPI.ALL_PAGES,
                sort_by=SortBy.VOLUME,
            )

