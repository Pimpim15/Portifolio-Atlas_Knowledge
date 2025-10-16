"""Acrescenta métricas de um resumo Locust à planilha de histórico.

Uso:
    poetry run python scripts/bench_append_history.py \
        --summary bench/results/pr-smoke_summary.md \
        --environment stage \
        --notes "Smoke de regressão"

O script lê o arquivo Markdown gerado automaticamente pelo `bench/run_headless.py`
(`*_summary.md`), extrai as métricas principais e as adiciona ao CSV definido em
`--history` (padrão `docs/performance-history.csv`).

A ideia é facilitar a publicação incremental de resultados oficiais sem editar
manualmente planilhas ou documentos.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from pathlib import Path
from typing import Any

SUMMARY_KEYS = {
    "Duração": "duration",
    "Usuários simultâneos": "users",
    "Requisições totais": "requests",
    "Taxa média (req/s)": "rps",
    "Latência média": "latency_avg_ms",
    "Latência p95": "latency_p95_ms",
    "Erros": "errors",
    "Taxa de falha": "fail_rate",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append Locust summary to history CSV")
    parser.add_argument("--summary", required=True, help="Arquivo *_summary.md gerado pelo runner")
    parser.add_argument("--environment", required=True, help="Ambiente alvo (ex.: dev, stage, prod)")
    parser.add_argument("--history", default="docs/performance-history.csv", help="Caminho para o CSV de histórico")
    parser.add_argument("--notes", default="", help="Observações adicionais a serem registradas")
    parser.add_argument(
        "--timestamp",
        default=dt.datetime.utcnow().isoformat(timespec="seconds"),
        help="Timestamp ISO8601 a registrar (padrão = agora em UTC)",
    )
    return parser.parse_args()


def _convert_value(key: str, value: str) -> Any:
    value = value.strip()
    if key in {"latency_avg_ms", "latency_p95_ms"}:
        if value.lower() in {"n/d", "na", ""}:
            return ""
        return float(value.split()[0])
    if key == "fail_rate":
        return float(value.rstrip("%")) / 100.0
    if key in {"users", "requests", "errors"}:
        return int(value.replace(" ", ""))
    if key == "rps":
        return float(value.replace(",", "."))
    return value


def parse_summary(summary_path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    with summary_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line.startswith("|") or line.startswith("| Métrica"):
                continue
            parts = [part.strip() for part in line.split("|")[1:-1]]
            if len(parts) != 2:
                continue
            label, raw_value = parts
            if label in SUMMARY_KEYS:
                key = SUMMARY_KEYS[label]
                data[key] = _convert_value(key, raw_value)

    missing = [key for key in SUMMARY_KEYS.values() if key not in data]
    if missing:
        raise ValueError(f"Campos ausentes no resumo: {', '.join(missing)}")

    return data


def append_to_history(history_path: Path, row: dict[str, Any]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = history_path.exists()

    with history_path.open("a", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "timestamp",
            "environment",
            "duration",
            "users",
            "requests",
            "rps",
            "latency_avg_ms",
            "latency_p95_ms",
            "errors",
            "fail_rate",
            "notes",
            "summary_file",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def main() -> None:
    args = parse_args()
    summary_path = Path(args.summary)
    if not summary_path.exists():
        raise FileNotFoundError(f"Resumo não encontrado: {summary_path}")

    metrics = parse_summary(summary_path)
    summary_rel = summary_path.as_posix()
    history_row = {
        "timestamp": args.timestamp,
        "environment": args.environment,
        "duration": metrics["duration"],
        "users": metrics["users"],
        "requests": metrics["requests"],
        "rps": metrics["rps"],
        "latency_avg_ms": metrics["latency_avg_ms"],
        "latency_p95_ms": metrics["latency_p95_ms"],
        "errors": metrics["errors"],
        "fail_rate": metrics["fail_rate"],
        "notes": args.notes,
        "summary_file": summary_rel,
    }

    append_to_history(Path(args.history), history_row)
    print("Histórico atualizado com sucesso")


if __name__ == "__main__":
    main()
