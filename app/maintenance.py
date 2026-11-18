import time

import psutil

from app.db import transaction
from app.integrations import deliver_one
from app.models import Metric
from app.retention import cleanup


def main():
    last_metric = 0
    last_cleanup = 0
    while True:
        try:
            if time.monotonic() - last_cleanup > 3600:
                cleanup(dry_run=False)
                last_cleanup = time.monotonic()
            if time.monotonic() - last_metric > 30:
                with transaction() as session:
                    memory = psutil.virtual_memory()
                    session.add(
                        Metric(
                            service="maintenance",
                            values={
                                "cpu_percent": psutil.cpu_percent(),
                                "ram_used": memory.used,
                                "ram_total": memory.total,
                                "swap_used": psutil.swap_memory().used,
                                "disk_free": psutil.disk_usage("/").free,
                            },
                        )
                    )
                last_metric = time.monotonic()
            if not deliver_one():
                time.sleep(2)
        except Exception:
            time.sleep(5)


if __name__ == "__main__":
    main()
