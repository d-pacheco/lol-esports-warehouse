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

DB_HOST: str = os.environ.get("DB_HOST", "localhost")
DB_PORT: str = os.environ.get("DB_PORT", "5432")
DB_USER: str = os.environ.get("DB_USER", "riot")
DB_PASSWORD: str = os.environ.get("DB_PASSWORD", "riot")
DB_NAME: str = os.environ.get("DB_NAME", "lol_esports")
