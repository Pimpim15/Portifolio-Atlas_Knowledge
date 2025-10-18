# Fluxo de Reindexação e Idempotência

Este documento explica como o backend garante que os documentos chegam ao OpenSearch a partir do momento em que são criados (ou seedados) e descreve as rotinas de idempotência e recuperação usadas pelo worker.

## Sequência do fluxo

1. **Bootstrap (`services/api/atlas_api/bootstrap.py`)**
   - Cria organização, usuário admin e documentos seed.
   - Enfileira cada documento recém-criado via `enqueue_document`, garantindo que seeds também sigam o caminho padrão de indexação.
2. **Fila SQS (`services/api/atlas_api/tasks/indexing.py`)**
   - Publica payloads contendo ação (`index`/`delete`), documento e metadados de job.
   - Garante idempotência utilizando `message_deduplication_id` quando o ambiente suporta FIFO.
3. **Worker (`services/worker/atlas_worker/run.py`)**
   - Consome mensagens, aplica tracing Prometheus/Otel e executa `index_document` ou `delete_document` no OpenSearch.
   - Marca progresso via `mark_job_item_*`, registra métricas e faz requeue com backoff exponencial quando necessário.
4. **Fallback de busca (`services/api/atlas_api/routes/search.py`)**
   - Caso o OpenSearch esteja fora ou ainda vazio, retorna dados direto do banco para evitar telas vazias.

## Idempotência e reprocessamento

- Mensagens carregam `job_id` e `job_item_id` que identificam a origem do documento em um job de reindex.
- O worker marca `started`, `retry`, `success` ou `error` para cada item, permitindo auditoria e reexecução manual.
- Quando falha, a mensagem é republicada com atraso progressivo (`WORKER_RETRY_BACKOFF_SECONDS` e `WORKER_RETRY_BACKOFF_MAX_SECONDS`).
- Se o limite de tentativas (`WORKER_MAX_ATTEMPTS`) for atingido, `mark_job_item_error` registra a falha e a mensagem é descartada para evitar loops infinitos.

## Validação automatizada

Use o script `scripts/validate_backend_flow.py` para rodar os testes que cobrem o fluxo ponta a ponta:

```bash
poetry run python scripts/validate_backend_flow.py
```

O script executa:

- `services/api/tests/unit/test_bootstrap.py` – valida enqueue automático dos seeds.
- `services/api/tests/unit/test_search.py` – garante fallback para o banco quando OpenSearch falha ou retorna vazio.
- `services/api/tests/integration/test_search_seeds.py` – verifica que `/search` retorna documentos seed sem precisar de reindex manual.
- `services/worker/tests/unit/test_run.py` – cobre retries, marcações de job e requeue/idempotência do worker.

Todas as execuções são feitas via `pytest`, retornando código de saída diferente de zero se algo falhar.

## Monitoramento

- Métricas expostas em `/metrics` na API e em `:9000` pelo worker (`prometheus_client`).
- `WORKER_*` métricas contabilizam ações, latência, idade das mensagens e retries.
- Logs estruturados incluem `job_id`, `job_item_id`, `document_id` e `attempt`, permitindo reconstruir o histórico do processamento.

## Próximos passos

- Provisionar scrape Prometheus para o worker e dashboards (Passo 2 – Observabilidade).
- Publicar guia de operação detalhando reprocessamentos manuais e inspeção de métricas.
