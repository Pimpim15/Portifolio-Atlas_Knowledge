# Governança de Dependências e Segurança de Supply Chain

## Visão Geral

| Stack | Ferramenta | Frequência | Ação |
| --- | --- | --- | --- |
| Python | Dependabot + `pip-audit` | Diária | PR automática com atualização de patch; auditoria roda no CI |
| Node/Vue | Dependabot + `npm audit` | Diária | PR automática; builds falham em vulnerabilidades críticas |
| Terraform | tfsec (manual) + revisões | Semanal | Execução manual antes de releases; validar módulos externos |
| Containers | Trivy FS/Imagem | Cada PR | Bloqueia merge em CVEs High/Critical |

## Pipeline CI (`.github/workflows/pr.yml`)

1. `poetry install`
2. `poetry run pip-audit --strict`
3. `npm audit --audit-level=high` (frontend)
4. Trivy + CodeQL (já versionados)
5. Enforce cobertura ≥ 85% (`tools/ci/check_coverage.py`)

## Dependabot

Arquivo `.github/dependabot.yml` mantém as seguintes schedules:

- **Python Poetry** – intervalo diário (`interval: daily`).
- **npm** – intervalo diário.
- **GitHub Actions** – semanal para acompanhar patches das Actions usadas no pipeline.

## Regras de Merge

- PRs de Dependabot exigem aprovação humana e execução do pipeline completo.
- Para upgrades de versão major, abrir ticket de planejamento com impacto/regressão.

## Evidências

- Logs do GitHub Actions permanecem 30 dias (config padrão) e são exportados semanalmente para S3.
- Histórico de auditorias `pip-audit` anexado no Atlas (tag `supply-chain`).
