import os

from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


RIOT_API_KEY: str = _require("RIOT_API_KEY")
PERSISTED_BASE: str = _require("PERSISTED_BASE")
FEED_BASE: str = _require("FEED_BASE")
