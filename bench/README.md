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

- Integrar um _smoke test_ Locust no pipeline de PR.
- Adicionar cenários que publiquem documentos em lote antes das consultas.
- Armazenar artefatos com os relatórios de teste para comparação histórica.