import json
import logging
from datetime import datetime, timezone

_BUILTIN_ATTRS = set(logging.LogRecord("", 0, "", 0, None, None, None).__dict__)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, val in record.__dict__.items():
            if key not in _BUILTIN_ATTRS:
                entry[key] = val
        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def setup_logging(log_file: str = "lol_esports_warehouse.log", level: int = logging.INFO) -> None:
    root = logging.getLogger("lol_esports_warehouse")
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s [%(name)s] %(message)s"))

    file = logging.FileHandler(log_file)
    file.setFormatter(JsonFormatter())

    root.addHandler(console)
    root.addHandler(file)
