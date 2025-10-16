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
from dataclasses import dataclass
from pathlib import Path

DEFAULT_USERS = 50
DEFAULT_SPAWN_RATE = 5
DEFAULT_RUN_TIME = "5m"
DEFAULT_PREFIX = "atlas-load-test"


@dataclass
class AggregatedMetrics:
    average_ms: float
    p95_ms: float | None
    request_count: int
    failure_count: int
    requests_per_second: float

    @property
    def fail_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.failure_count / self.request_count


def _pick_metric(row: dict[str, str], candidates: list[str], *, default: float = 0.0) -> float:
    for key in candidates:
        value = row.get(key)
        if value not in (None, ""):
            try:
                return float(value)
            except ValueError:  # pragma: no cover - CSV corrupt
                continue
    return default


def _load_aggregated_metrics(results_dir: Path, prefix: str) -> AggregatedMetrics:
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
        raise RuntimeError("Linha agregada ('Total'/'Aggregated') não encontrada em stats.csv")

    average_ms = _pick_metric(total_row, ["Average Response Time", "AverageResponseTime"])
    p95_ms = _pick_metric(total_row, ["95%", "95%ile", "95_percentile"], default=float("nan"))
    if p95_ms != p95_ms:  # NaN check
        p95_ms_value: float | None = None
    else:
        p95_ms_value = p95_ms

    request_count = int(_pick_metric(total_row, ["Requests", "Request Count"], default=0.0))
    failure_count = int(_pick_metric(total_row, ["Failures", "Failure Count"], default=0.0))
    rps = _pick_metric(total_row, ["Requests/s", "Requests_per_second", "Requests Per Second"], default=0.0)

    return AggregatedMetrics(
        average_ms=average_ms,
        p95_ms=p95_ms_value,
        request_count=request_count,
        failure_count=failure_count,
        requests_per_second=rps,
    )


def _enforce_thresholds(metrics: AggregatedMetrics, *, max_avg_ms: float | None, max_fail_rate: float | None) -> None:
    if max_avg_ms is None and max_fail_rate is None:
        return

    violations: list[str] = []
    if max_avg_ms is not None and metrics.average_ms > max_avg_ms:
        violations.append(f"tempo médio {metrics.average_ms:.2f} ms (limite {max_avg_ms:.2f} ms)")
    if max_fail_rate is not None and metrics.fail_rate > max_fail_rate:
        violations.append(f"taxa de falha {metrics.fail_rate:.3f} (limite {max_fail_rate:.3f})")

    if violations:
        details = ", ".join(violations)
        raise SystemExit(f"Locust smoke test acima dos limites: {details}")

    print(
        "Locust smoke test aprovado: tempo médio = "
        f"{metrics.average_ms:.2f} ms, taxa de falha = {metrics.fail_rate:.3f} (limites respeitados)")


def _write_summary(
    results_dir: Path,
    prefix: str,
    metrics: AggregatedMetrics,
    *,
    run_time: str,
    users: int,
) -> None:
    summary_path = results_dir / f"{prefix}_summary.md"
    fail_rate_percent = metrics.fail_rate * 100
    p95_display = f"{metrics.p95_ms:.2f} ms" if metrics.p95_ms is not None else "n/d"

    content = [
        "# Atlas Knowledge – Benchmark",
        "",
        "| Métrica | Valor |",
        "| --- | --- |",
        f"| Duração | {run_time} |",
        f"| Usuários simultâneos | {users} |",
        f"| Requisições totais | {metrics.request_count} |",
        f"| Taxa média (req/s) | {metrics.requests_per_second:.2f} |",
        f"| Latência média | {metrics.average_ms:.2f} ms |",
        f"| Latência p95 | {p95_display} |",
        f"| Erros | {metrics.failure_count} |",
        f"| Taxa de falha | {fail_rate_percent:.2f}% |",
        "",
        "> Relatório gerado automaticamente por bench/run_headless.py.",
    ]

    summary_path.write_text("\n".join(content) + "\n", encoding="utf-8")
    print(f"Resumo salvo em {summary_path}")


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

    metrics = _load_aggregated_metrics(results_dir, args.prefix)
    _enforce_thresholds(metrics, max_avg_ms=args.max_avg_ms, max_fail_rate=args.max_fail_rate)
    _write_summary(
        results_dir,
        args.prefix,
        metrics,
        run_time=args.run_time,
        users=args.users,
    )


if __name__ == "__main__":
    run()
