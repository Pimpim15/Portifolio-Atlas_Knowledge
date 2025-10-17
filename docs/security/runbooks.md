# Runbooks Operacionais

## Reindexação de Documentos

1. Disparar `POST /docs/reindex` com token admin (MFA).
2. Monitorar métrica `atlas_reindex_in_flight`. Deve zerar em ≤ 10 minutos.
3. Se houver falhas:
   - Consultar *dashboards*: Grafana `Atlas Reindex` e CloudWatch `atlas-<env>-operations`.
   - Executar `scripts/seed.py` (ambiente local) ou job ECS "Reindex Retry" (prod).

## Dreno de Fila SQS

1. Acionar workflow `infra/terraform` (`make terraform plan` + `apply`).
2. Verificar métricas `ApproximateNumberOfMessagesVisible` e `NotVisible` via CloudWatch.
3. Se > 100 mensagens atrasadas, escalar worker Fargate (`desired_count +2`).
4. Validar que dead-letter queue permaneça vazia.

## Validação de Observabilidade

- Rodar `make smoke-observability` (script que exercita `/metrics`, `/healthz` e verifica traces).
- Confirmar presença de `trace_id` nos logs (`jq '.trace_id'` em CloudWatch export).
- Executar `pytest services/api/tests/observability` (verifica métricas atualizadas) uma vez por sprint.

## Rotação de Secrets

1. Habilitar `enable_rds_secret_rotation = true` no `terraform.tfvars` do ambiente.
2. Executar pipeline `deploy.yml` (modo apply) com aprovação.
3. Validar que nova senha foi propagada (`aws secretsmanager get-secret-value`).
4. Rode testes de fumaça (`bench/run_headless.py`) para confirmar integridade.

## Checklist Pós-Incidente

- Validar que tokens comprometidos foram revogados (consulta Redis blacklist).
- Confirmar que WAF retornou ao modo **count**.
- Atualizar status page e anexar relatório no Atlas (tag `post-mortem`).
