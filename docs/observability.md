# Observabilidade Atlas Knowledge

Este guia descreve o que já está instrumentado no Atlas Knowledge e os passos pendentes
para alcançar um nível "product ready" de telemetria. Até o momento, todas as evidências
foram coletadas em ambiente local (`docker compose`); os módulos Terraform para AWS ainda
não foram aplicados.

## Logs correlacionados

- **Trace context automático:** toda mensagem enfileirada segue com os cabeçalhos W3C
  (`traceparent`/`tracestate`), habilitando a correlação de logs/metrics no worker.
- **Consultas prontas:** o Terraform define _Log Insights Query Definitions_
  (`worker_failures`, `api_5xx`, `frontend_errors`). É necessário aplicar a stack em AWS
  e validar a execução das queries.
- **Capturas ilustrativas:**
  - ![Dashboard CloudWatch](screenshots/cloudwatch-dashboard.svg)
  - ![Consulta Logs Insights](screenshots/log-insights.svg)

> As capturas acima são modelos; substitua por screenshots reais assim que um ambiente
> em cloud estiver ativo.

## Tracing ponta a ponta

- O worker abre spans filhos (`worker.process_message`) reaproveitando o contexto recebido.
- No stack local os traces são exportados via OTLP para o collector ADOT. Em AWS é
  necessário confirmar o envio para X-Ray.
- Logs estruturados exibem `trace_id`/`span_id`, facilitando a navegação do alerta
  até o trace correspondente.

## Métricas adicionais

- `atlas_worker_message_age_seconds`: histograma Prometheus com a idade da mensagem ao chegar no worker.
- Dashboard CloudWatch previsto no Terraform agrega métricas de SQS, ECS, RDS e OpenSearch
  para visão de 24h (validar após primeiro deploy na cloud).

## Stack local Prometheus + Grafana

- O `docker-compose` sobe Prometheus (http://localhost:9090) e Grafana (http://localhost:3000, usuário `atlas`).
- O datasource `PROM_DS` é configurado via `infra/grafana/provisioning/datasources/datasource.yml` apontando para o serviço Prometheus local.
- Dashboards ficam em `infra/grafana/dashboards/` (overview da plataforma e painel detalhado de reindex).
- As regras de alerta residem em `infra/prometheus/rules/atlas-alerts.yml`; conecte-as a um Alertmanager
  ou ferramenta equivalente para receber notificações reais.

## Validação automatizada

Execute os testes de observabilidade (API + worker) sempre que alterar instrumentações ou métricas:

```powershell
poetry run python scripts/validate_observability.py
```

O script roda as suítes unitárias que conferem cabeçalhos de correlação, métricas Prometheus e spans do worker.

## Como executar análises rápidas

```powershell
# Inspecionar as consultas Log Insights registradas via Terraform
aws logs describe-log-groups --log-group-name-prefix /aws/ecs/atlas-api
aws logs describe-query-definitions --name-prefix atlas-prod

# Executar a consulta "worker_failures"
aws logs start-query `
  --log-group-name /aws/ecs/atlas-worker-prod `
  --start-time (Get-Date).AddHours(-1).ToUnixTimeSeconds() `
  --end-time (Get-Date).ToUnixTimeSeconds() `
  --query-string "fields @timestamp, event, trace_id\n| filter component = 'worker' and level = 'error'\n| sort @timestamp desc\n| limit 20"
```

> Consulte `bench/run_headless.py` para reproduzir cargas sintéticas e validar
> a telemetria antes de promover alterações para produção. Esses comandos assumem
> que as credenciais AWS e o ambiente já foram provisionados com o Terraform.

## Próximos passos

1. Executar `terraform apply` (dev/stage) garantindo variáveis de alarmes e budgets configuradas.
2. Capturar evidências reais (trace no X-Ray, dashboards CloudWatch/Grafana, alertas enviados).
3. Configurar webhook/Alertmanager para receber alertas Prometheus e SNS/ChatOps para CloudWatch.
4. Documentar rotina trimestral de teste (tabletop + verificação das queries Log Insights).
