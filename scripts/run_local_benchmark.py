"""Executa a API localmente e roda o benchmark oficial.

Uso:
    poetry run python scripts/run_local_benchmark.py
"""

from __future__ import annotations

import multiprocessing as mp
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent


def _run_server() -> None:
    import uvicorn

    uvicorn.run("services.api.atlas_api.main:app", host="127.0.0.1", port=8000, log_level="warning")


def _wait_for_healthcheck(deadline: float) -> None:
    url = "http://127.0.0.1:8000/healthz"
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=1)
        except Exception:
            time.sleep(1)
            continue

        if response.status_code == 200:
            return
        time.sleep(1)

    raise RuntimeError("API não ficou saudável a tempo")


def main() -> None:
    mp.freeze_support()
    server = mp.Process(target=_run_server, daemon=True)
    server.start()

    try:
        _wait_for_healthcheck(time.time() + 60)

        cmd = [
            sys.executable,
            "bench/run_headless.py",
            "--host",
            "http://127.0.0.1:8000",
            "--users",
            "20",
            "--spawn-rate",
            "5",
            "--run-time",
            "3m",
            "--prefix",
            "local-official",
            "--max-avg-ms",
            "1000",
            "--max-fail-rate",
            "0.01",
        ]
        subprocess.run(cmd, cwd=ROOT, check=True)
    finally:
        server.terminate()
        server.join(timeout=10)


if __name__ == "__main__":
    main()
