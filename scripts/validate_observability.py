"""Executa testes focados na observabilidade da API e do worker."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TEST_TARGETS = [
    "services/api/tests/unit/test_observability.py",
    "services/worker/tests/unit/test_run.py",
]


def run_tests() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, "-m", "pytest", "-q", *TEST_TARGETS]
    print("[observability] Rodando:", " ".join(TEST_TARGETS))
    process = subprocess.run(cmd, cwd=repo_root, check=False)
    if process.returncode == 0:
        print("[observability] ✅ Observabilidade validada com sucesso.")
    else:
        print("[observability] ❌ Falha nos testes de observabilidade. Consulte a saída acima.")
    return process.returncode


def main() -> None:
    raise SystemExit(run_tests())


if __name__ == "__main__":
    main()
