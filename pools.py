from typing import Callable

import settings
from network import Pool, Token, DEX, Address


class Pools:
    def __init__(
            self,
            pool_filter: Callable[[Pool], bool] | None = None,
            repeated_pool_filter_key: Callable[[Pool], float] | None = None,
    ):
        self.pools: list[Pool] = []
        self.tokens: set[Token] = set()
        self.dexes: dict[DEXId, DEX] = {}
        self.blacklist = dict[Address, str]
        self.pool_filter = pool_filter
        self.repeated_pool_filter_key = repeated_pool_filter_key

        with open(settings.BLACKLIST_FILENAME, 'r') as file:
            self.blacklist = dict(csv.reader(file))

    def __len__(self):
        return len(self.pools)

    def __getitem__(self, index) -> Pool:
        return self.pools[index]

    def get_tokens(self) -> list[Token]:
        return list(self.tokens.values())

    def apply_filter(self):
        if self.pool_filter:
            filtered_pools = set(filter(self.pool_filter, self.pools))
            filtered_out_pools = set(self.pools) - filtered_pools
            filtered_out_tokens = set([p.base_token for p in filtered_out_pools]) - set([p.base_token for p in filtered_pools])

            self.pools = list(filtered_pools)
            self.tokens = list(set(self.tokens) - filtered_out_tokens)

    def update(self, pool):
        if pool.base_token.address in self.blacklist.keys():
            return

        if self.pool_filter and not self.pool_filter(pool):
            return

        if self.repeated_pool_filter_key:
            pool_with_same_token = None

            for p in self.pools:
                if p.base_token == pool.base_token:
                    pool_with_same_token = p
                    break

            if pool_with_same_token:
                if self.repeated_pool_filter_key(pool) > self.repeated_pool_filter_key(pool_with_same_token):
                    self.pools.remove(pool_with_same_token)
                else:
                    return

        self.pools.append(pool)
        self.tokens[pool.base_token.address] = pool.base_token
        self.tokens[pool.quote_token.address] = pool.quote_token
        self.dexes[pool.dex.id] = pool.dex

    def find_best_token_pool(self, token: Token, key: Callable) -> Pool | None:
        pools = [p for p in self.pools if p.base_token == token]

        if pools:
            pools.sort(key=key, reverse=True)
            return pools[0]

        return None
