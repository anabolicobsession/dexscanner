from typing import Callable, Generic, TypeVar

from network import Pool, Token, DEX


T = TypeVar('T')


class SetWithGet(Generic[T], set):
    def get(self, element: T, default: T = None) -> T | None:
        for x in self:
            if x == element:
                return x
        return default


Filter = Callable[[Pool], bool]
FilterKey = Callable[[Pool], float]

PoolsType = SetWithGet[Pool]
Tokens = SetWithGet[Token]
DEXes = SetWithGet[DEX]


class Pools:
    def __init__(
            self,
            pool_filter: Filter | None = None,
            repeated_pool_filter_key: FilterKey | None = None,
    ):
        self.pools: PoolsType = SetWithGet()
        self.tokens: Tokens = SetWithGet()
        self.dexes: DEXes = SetWithGet()
        self.pool_filter = pool_filter
        self.repeated_pool_filter_key = repeated_pool_filter_key
        self._iterator = None

    def __len__(self):
        return len(self.pools)

    def __iter__(self):
        self._iterator = iter(self.pools)
        return self

    def __next__(self):
        return next(self._iterator)

    def get_tokens(self) -> Tokens:
        return self.tokens

    def get_dexes(self) -> DEXes:
        return self.dexes

    def _ensure_consistent_token_and_dex_references(self, pool: Pool):
        if existing_base_token := self.tokens.get(pool.base_token):
            existing_base_token.update(pool.base_token)
            pool.base_token = existing_base_token
        else:
            self.tokens.add(pool.base_token)

        if existing_quote_token := self.tokens.get(pool.quote_token):
            existing_quote_token.update(pool.quote_token)
            pool.quote_token = existing_quote_token
        else:
            self.tokens.add(pool.quote_token)

        if existing_dex := self.dexes.get(pool.dex):
            existing_dex.update(pool.dex)
            pool.dex = existing_dex
        else:
            self.dexes.add(pool.dex)

    def _update(self, pool: Pool):
        if existing_pool := self.pools.get(pool):
            existing_pool.update(pool)
        else:
            self.pools.add(pool)

    def update(self, pool: Pool):
        if self.pool_filter and not self.pool_filter(pool):
            return

        if self.repeated_pool_filter_key:
            pool_with_same_token = None

            for p in self.pools:
                if p.base_token == pool.base_token and p.quote_token == pool.quote_token:
                    pool_with_same_token = p
                    break

            if pool_with_same_token:
                if self.repeated_pool_filter_key(pool) > self.repeated_pool_filter_key(pool_with_same_token):
                    self.pools.remove(pool_with_same_token)
                    self.dexes = DEXes([p.dex for p in self.pools])
                else:
                    return

        self._ensure_consistent_token_and_dex_references(pool)
        self._update(pool)

    def apply_filter(self):
        if self.pool_filter:
            self.pools = PoolsType(filter(self.pool_filter, self.pools))
            self.tokens = Tokens(map(lambda p: p.base_token, self.pools)) | Tokens(map(lambda p: p.quote_token, self.pools))
            self.tokens = DEXes(map(lambda p: p.dex, self.pools))

    def match_pool(self, token: Token, pool_filter_key: FilterKey) -> Pool | None:
        matches = [p for p in self.pools if p.base_token == token]

        if matches:
            if not self.repeated_pool_filter_key:
                matches.sort(key=pool_filter_key, reverse=True)
            return matches[0]

        return None
