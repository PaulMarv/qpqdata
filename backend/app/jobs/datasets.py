"""Private export worker; no import-time configuration, I/O or ledger writes."""

import sys
import time
from pathlib import Path

from app.core.config import Settings
from app.db.session import make_engine
from app.services.dataset_exports import run_one


def main() -> None:
    settings = Settings()
    if not settings.datasets_enabled:
        return
    engine = make_engine(settings.database_url.get_secret_value())
    try:
        while True:
            try:
                run_one(engine, settings)
                Path("/tmp/qpq-datasets-heartbeat").touch(mode=0o600, exist_ok=True)
            except Exception:
                print("Dataset export unavailable; retry scheduled", flush=True)
                if "--once" in sys.argv:
                    raise SystemExit(1) from None
            if "--once" in sys.argv:
                return
            time.sleep(3)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
