import httpx

from lol_esports_warehouse.config import RIOT_API_KEY, PERSISTED_BASE, FEED_BASE


class _BaseClient:
    def __init__(self, base_url: str, api_key: str | None = None):
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "Origin": "https://lolesports.com",
                "Referrer": "https://lolesports.com",
                "x-api-key": api_key or RIOT_API_KEY,
            },
            timeout=30.0,
        )

    def get(self, endpoint: str, params: dict | None = None) -> dict:
        resp = self._client.get(endpoint, params=params)
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class PersistedClient(_BaseClient):
    """Client for the persisted esports API (schedules, leagues, etc.)."""

    def __init__(self, api_key: str | None = None):
        super().__init__(PERSISTED_BASE, api_key)


class LiveStatsClient(_BaseClient):
    """Client for the live stats feed API."""

    def __init__(self, api_key: str | None = None):
        super().__init__(FEED_BASE, api_key)

    def get_window(self, game_id: str, starting_time: str | None = None) -> dict | None:
        params = {}
        if starting_time:
            params["startingTime"] = starting_time
        resp = self._client.get(f"/window/{game_id}", params=params or None)
        if resp.status_code == 204:
            return None
        resp.raise_for_status()
        return resp.json()
