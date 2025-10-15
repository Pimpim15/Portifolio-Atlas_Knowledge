"""Utilitário para executar os cenários do Locust em modo headless.

Exemplo:

    poetry run python bench/run_headless.py --host https://api.dev.atlas

Isso executará o teste com 50 usuários concorrentes durante 5 minutos e
armazenará os CSVs em `bench/results` com o prefixo escolhido.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_USERS = 50
DEFAULT_SPAWN_RATE = 5
DEFAULT_RUN_TIME = "5m"
DEFAULT_PREFIX = "atlas-load-test"


def run() -> None:
    parser = argparse.ArgumentParser(description="Executa o Locust em modo headless")
    parser.add_argument("--host", required=True, help="URL base da API")
    parser.add_argument("--users", type=int, default=DEFAULT_USERS, help="Usuários concorrentes")
    parser.add_argument("--spawn-rate", type=int, default=DEFAULT_SPAWN_RATE, help="Taxa de ramp-up por segundo")
    parser.add_argument("--run-time", default=DEFAULT_RUN_TIME, help="Duração do teste (ex.: 5m, 10m)")
    parser.add_argument(
        "--prefix",
        default=DEFAULT_PREFIX,
        help="Prefixo usado nos arquivos CSV gerados em bench/results",
    )

    args = parser.parse_args()

    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        str(Path(__file__).resolve().parent / "locustfile.py"),
        "--headless",
        "-H",
        args.host,
        "-u",
        str(args.users),
        "-r",
        str(args.spawn_rate),
        "--run-time",
        args.run_time,
        "--csv",
        str(results_dir / args.prefix),
        "--csv-full-history",
    ]

    subprocess.run(command, check=True)


if __name__ == "__main__":
    run()
