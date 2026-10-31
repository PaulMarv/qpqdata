"""Explicit notification worker; never connects or sends on import."""

import sys
import time
from pathlib import Path

from app.core.config import Settings
from app.db.session import make_engine
from app.services.notifications import deliver_pending


def main() -> None:
    settings = Settings()
    if not settings.auth_enabled:
        return
    engine = make_engine(settings.database_url.get_secret_value())
    try:
        while True:
            try:
                count = deliver_pending(engine, settings)
                Path("/tmp/qpq-notifications-heartbeat").touch(mode=0o600, exist_ok=True)
                print(f"Outcome notifications: {count} delivered", flush=True)
            except Exception:
                print("Outcome delivery unavailable; retry scheduled", flush=True)
                if "--once" in sys.argv:
                    raise SystemExit(1) from None
            if "--once" in sys.argv:
                return
            time.sleep(15)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
