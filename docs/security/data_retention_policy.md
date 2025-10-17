# Política de Retenção de Dados e Logs

## Escopo

Aplica-se a todos os dados processados pelo Atlas Knowledge (PostgreSQL, OpenSearch, S3 e logs operacionais).

## Retenção Padrão

| Tipo de dado | Sistema | Retenção | Observações |
| --- | --- | --- | --- |
| Conteúdo principal (documentos) | PostgreSQL / OpenSearch | Indefinida enquanto a organização estiver ativa | Históricos de versão mantidos automaticamente |
| Metadados de auditoria (`updated_by`, `updated_at`) | PostgreSQL | 5 anos | Exportável sob demanda |
| Logs de aplicação estruturados | CloudWatch → S3 Glacier Deep Archive | 365 dias | Exportação diária para bucket com política WORM via Object Lock |
| Traces e métricas OTEL | CloudWatch / X-Ray | 90 dias | Agregados críticos exportados para S3 Parquet |
| Backups RDS automatizados | AWS RDS | 30 dias | Teste de restauração trimestral documentado |
| Snapshots manuais | AWS RDS / OpenSearch | Até conclusão do DRP | Revisados após exercícios de DR |

## Processos

1. **Exportação diária de logs**
   - CloudWatch Logs → Kinesis Firehose → S3 `atlas-<env>-logs` com Object Lock (`COMPLIANCE`, 365 dias).
   - Política IAM impede exclusões até expirar o bloqueio.
2. **Expurgo automático**
   - Lifecycle rules em S3 movem logs para Glacier Deep Archive após 30 dias.
   - Tarefas `DELETE` nos índices do OpenSearch removem documentos marcados como `deleted_at` > 90 dias.
3. **Solicitações de exclusão**
   - Recebidas via `privacy@acme.com`.
   - Time de governança executa workflow: desativar usuário → revogar acessos → anonimizar registros não obrigatórios.

## Evidências

- Runbook `docs/security/incident_response_playbook.md` inclui passo de expurgo pós-incidente.
- Relatórios trimestrais de retenção anexados no Atlas (categoria **Governança**).

## Revisão

- Política revisada semestralmente ou após mudança regulatória relevante.
- Última revisão: Outubro/2024.
