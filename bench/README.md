# Benchmarks Atlas Knowledge

Este diretório contém cenários básicos de carga para validar performance da API. Foram pensados para rodar em pipelines de _smoke test_ ou para investigações manuais.

## Locust (recomendado)

### Instalação

```bash
python -m venv .venv-bench
source .venv-bench/bin/activate  # No Windows: .venv-bench\Scripts\activate
pip install -r bench/requirements.txt
```

### Execução rápida (smoke)

```bash
locust -f bench/locustfile.py --headless --users 10 --spawn-rate 2 --run-time 5m --host https://atlas.dev.example.com
```

### Runner automatizado

```bash
poetry run python bench/run_headless.py \
	--host https://atlas.stage.example.com \
	--users 50 \
	--spawn-rate 5 \
	--run-time 5m \
	--prefix stage-$(date +%Y%m%d%H%M) \
	--max-avg-ms 1500 \
	--max-fail-rate 0.01
```

- Os CSVs e gráficos serão armazenados em `bench/results/<prefix>*`.
- Consulte `bench/results/sample_report.md` para um exemplo de análise consolidada.
- Ajuste `--max-avg-ms` e `--max-fail-rate` conforme os SLOs de cada ambiente.
- Um resumo Markdown (`<prefix>_summary.md`) é gerado automaticamente com as métricas principais.
- Para versionar resultados oficiais, utilize `poetry run python scripts/bench_append_history.py --summary <arquivo> --environment <env> --notes <texto>`.

### Execução interativa

```bash
locust -f bench/locustfile.py --host https://atlas.dev.example.com
```

> Ajuste o host conforme o ambiente alvo. O cenário autentica usando as credenciais `admin@acme.com` / `admin`.

## wrk (picos de throughput)

Para validar _throughput_ máximo de endpoints estáticos (
ex.: `/health`), use o wrk:

```bash
wrk -t4 -c128 -d60s https://atlas.dev.example.com/health
```

## Métricas de saída

- Acompanhe as métricas expostas no CloudWatch Dashboard `atlas-<env>-operations`.
- Monitore os alarmes de CPU/Memory do ECS para detectar _throttling_.
- Combine os resultados com os _logs_ exportados pelo ADOT sidecar.

## Próximos passos sugeridos

- ✅ Smoke test Locust integrado ao pipeline de PR (`.github/workflows/pr.yml` → job `locust-smoke`) com guardrails de 1.5s/1% e artefatos CSV/Markdown.
- Adicionar cenários que publiquem documentos em lote antes das consultas.
- Armazenar artefatos com os relatórios de teste para comparação histórica.