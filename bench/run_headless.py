"""Utilitário para executar os cenários do Locust em modo headless.

Exemplo:

    poetry run python bench/run_headless.py --host https://api.dev.atlas

Isso executará o teste com 50 usuários concorrentes durante 5 minutos e
armazenará os CSVs em `bench/results` com o prefixo escolhido.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

DEFAULT_USERS = 50
DEFAULT_SPAWN_RATE = 5
DEFAULT_RUN_TIME = "5m"
DEFAULT_PREFIX = "atlas-load-test"


def _pick_metric(row: dict[str, str], candidates: list[str], *, default: float = 0.0) -> float:
    for key in candidates:
        value = row.get(key)
        if value not in (None, ""):
            try:
                return float(value)
            except ValueError:  # pragma: no cover - CSV corrupt
                continue
    return default


def _validate_thresholds(results_dir: Path, prefix: str, *, max_avg_ms: float | None, max_fail_rate: float | None) -> None:
    stats_path = results_dir / f"{prefix}_stats.csv"

    if not stats_path.exists():
        raise FileNotFoundError(f"Arquivo de estatísticas não encontrado: {stats_path}")

    with stats_path.open(newline="") as fp:
        reader = csv.DictReader(fp)
        total_row: dict[str, str] | None = None
        for row in reader:
            if row.get("Name") in {"Total", "Aggregated"}:
                total_row = row
                break

    if total_row is None:
        raise RuntimeError("Linha agregada ('Total') não encontrada em stats.csv")

    average_ms = _pick_metric(total_row, ["Average Response Time", "AverageResponseTime"])
    request_count = _pick_metric(total_row, ["Requests", "Request Count"], default=0.0)
    failure_count = _pick_metric(total_row, ["Failures", "Failure Count"], default=0.0)
    fail_rate = 0.0 if request_count == 0 else failure_count / request_count

    violations: list[str] = []
    if max_avg_ms is not None and average_ms > max_avg_ms:
        violations.append(f"tempo médio {average_ms:.2f} ms (limite {max_avg_ms:.2f} ms)")
    if max_fail_rate is not None and fail_rate > max_fail_rate:
        violations.append(f"taxa de falha {fail_rate:.3f} (limite {max_fail_rate:.3f})")

    if violations:
        details = ", ".join(violations)
        raise SystemExit(f"Locust smoke test acima dos limites: {details}")

    print(
        "Locust smoke test aprovado: tempo médio = "
        f"{average_ms:.2f} ms, taxa de falha = {fail_rate:.3f} (limites respeitados)")


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
    parser.add_argument(
        "--max-avg-ms",
        type=float,
        default=None,
        help="Tempo médio de resposta permitido (ms). Faltando para desabilitar a validação.",
    )
    parser.add_argument(
        "--max-fail-rate",
        type=float,
        default=None,
        help="Taxa máxima de falhas (ex.: 0.01 = 1%). Faltando para desabilitar a validação.",
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

    if args.max_avg_ms is not None or args.max_fail_rate is not None:
        _validate_thresholds(
            results_dir,
            args.prefix,
            max_avg_ms=args.max_avg_ms,
            max_fail_rate=args.max_fail_rate,
        )


if __name__ == "__main__":
    run()
