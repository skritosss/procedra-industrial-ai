import argparse
import os
import signal
import socket
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.settings import get_settings  # noqa: E402
from app.storage.database import apply_migrations, connect_database  # noqa: E402
from app.workers.video_jobs import run_one_video_job  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the durable Procedra video-job worker")
    parser.add_argument("--once", action="store_true", help="Claim at most one job and exit")
    parser.add_argument("--worker-id", default="", help="Stable worker identifier for leases")
    args = parser.parse_args()

    settings = get_settings()
    worker_id = args.worker_id.strip() or (
        f"video-worker-{socket.gethostname()}-{os.getpid()}-{os.urandom(4).hex()}"
    )
    with connect_database(settings.database_path) as connection:
        apply_migrations(connection)

    if args.once:
        run_one_video_job(worker_id, settings=settings)
        return 0

    stopping = False

    def stop_worker(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop_worker)
    signal.signal(signal.SIGINT, stop_worker)
    while not stopping:
        processed = run_one_video_job(worker_id, settings=settings)
        if not processed:
            time.sleep(settings.video_job_poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
