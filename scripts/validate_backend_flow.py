"""Roda a suíte mínima que valida o fluxo de reindex e retries do backend."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TEST_TARGETS = [
    "services/api/tests/unit/test_bootstrap.py",
    "services/api/tests/unit/test_search.py",
    "services/api/tests/integration/test_search_seeds.py",
    "services/worker/tests/unit/test_run.py",
]


def run_tests() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, "-m", "pytest", "-q", *TEST_TARGETS]
    print("[validate] Rodando:", " ".join(TEST_TARGETS))
    process = subprocess.run(cmd, cwd=repo_root, check=False)
    if process.returncode == 0:
        print("[validate] ✅ Fluxo backend validado com sucesso.")
    else:
        print("[validate] ❌ Falha nos testes. Consulte a saída acima.")
    return process.returncode


def main() -> None:
    raise SystemExit(run_tests())


if __name__ == "__main__":
    main()
