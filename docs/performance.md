# Atlas Knowledge – Guia de Benchmarks

Este documento descreve como executar, validar e publicar os testes de carga oficiais
utilizando os cenários fornecidos em `bench/`. Até o momento apenas o cenário local foi
executado; ambientes `stage`/`prod` ainda dependem do provisionamento Terraform.

## Pré-requisitos

- Docker em funcionamento para subir o stack local (`infra/docker-compose.yml`) ou acesso a um
  ambiente remoto (dev/stage/prod) com URL pública.
- Poetry instalado (versão 1.8.x) com o ambiente do repositório configurado.
- Credenciais válidas para o ambiente alvo (variáveis `JWT_*`, `DATABASE_URL`, etc.) caso execute
  fora do stack local.

## Execução padrão (stage)

> Ainda não existe um ambiente `stage` provisionado. Use esta seção como referência para quando
> o deploy cloud estiver habilitado. Enquanto isso, execute o script apontando para o stack local.

```powershell
# 1. Certifique-se de que o ambiente alvo está saudável
curl https://atlas.stage.example.com/healthz

# 2. Rode o Locust headless com guardrails padrão
poetry run python bench/run_headless.py `
  --host https://atlas.stage.example.com `
  --users 50 `
  --spawn-rate 5 `
  --run-time 10m `
  --prefix stage-$(Get-Date -Format 'yyyyMMddHHmm') `
  --max-avg-ms 1500 `
  --max-fail-rate 0.01
```

> Ajuste `--users`, `--run-time` e os limites conforme os SLOs de cada ambiente. Para smoke tests ou
> execução local, utilize valores menores (ex.: `--users 5`, `--run-time 1m`, `--host http://localhost:8000`).

## Resultados gerados

Após a execução, os seguintes artefatos estarão disponíveis em `bench/results/`:

- `<prefix>_stats.csv`, `<prefix>_stats_history.csv`, `<prefix>_failures.csv` – dados completos do Locust.
- `<prefix>_summary.md` – resumo Markdown com duração, requisições, latência média/p95 e taxa de falha.

Inclua o arquivo de resumo em revisões de PR ou anexos de incident response para dar visibilidade às
métricas coletadas.

Para registrar o resultado no histórico versionado (`docs/performance-history.csv`), utilize o helper
`scripts/bench_append_history.py`:

```powershell
poetry run python scripts/bench_append_history.py `
  --summary bench/results/stage-202510151230_summary.md `
  --environment stage `
  --notes "Carga após otimização do índice"
```

O script cria o CSV caso não exista e appenda uma linha com as métricas principais, facilitando o
acompanhamento longitudinal.

## Checklist de publicação

1. Executar o teste no ambiente desejado.
2. Armazenar os artefatos (CSV + resumo) como _build artifacts_ ou em um bucket dedicado.
3. Atualizar este documento com um snapshot das métricas relevantes (ver seção "Histórico").
4. Adicionar comentários no PR descrevendo as observações principais (gargalos, regressões, etc.).

## Histórico

| Data | Ambiente | Duração | Usuários | Média (ms) | p95 (ms) | Erros | Notas |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-10-16 | local | 3m | 20 | 108.90 | 580.00 | 0 | Real OpenSearch via docker compose |

> Ao registrar um novo teste, aponte para o respectivo resumo (`<prefix>_summary.md`) no artefato da
> esteira ou bucket utilizado.
