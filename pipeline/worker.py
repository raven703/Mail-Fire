"""One independently scalable worker group per process/container."""

import os
import sys

from mice.celery import app
from pipeline.config import limits


def main():
    group = os.environ["MICE_WORKER_GROUP"]
    bound = limits(group)
    args = [
        "worker",
        "--loglevel=INFO",
        "--pool=prefork",
        "--queues=" + group,
        "--hostname=" + group + "@%h",
        "--concurrency=" + str(bound["concurrency"]),
        "--prefetch-multiplier=" + str(bound["prefetch"]),
        "--soft-time-limit=" + str(bound["soft"]),
        "--time-limit=" + str(bound["hard"]),
    ]
    if bound["max_memory_kb"]:
        args.append("--max-memory-per-child=" + str(bound["max_memory_kb"]))
    if bound["max_tasks"]:
        args.append("--max-tasks-per-child=" + str(bound["max_tasks"]))
    app.worker_main(args + sys.argv[1:])


if __name__ == "__main__":
    main()
