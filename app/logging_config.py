import os
import json
import logging
from datetime import datetime, timezone

class Formatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        formatted_record = {
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        }
        if record.exc_info is not None:
            formatted_record["exc"] = self.formatException(record.exc_info)
        return json.dumps(formatted_record)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(Formatter())

    root = logging.getLogger()
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    root.handlers = [handler]