# Política de Logs e Mascaramento de PII

## Objetivo

Garantir que logs operacionais forneçam contexto útil sem expor informações sensíveis.

## Diretrizes

1. **Estrutura JSON** – todos os logs usam `structlog` com campos: `event`, `trace_id`, `span_id`, `route`, `user_id`, `org_id`, `status_code`, `latency_ms`.
2. **Mascaramento automático** – os campos listados em `LOG_MASK_FIELDS` (por padrão `email`, `user_email`, `user_id`, `subject`, `customer_email`) são substituídos por `***redacted***` no momento do logging.
3. **Tokens e secrets** – qualquer chave contendo `token`, `secret`, `password` ou `key` é sempre mascarada.
4. **PII adicional** – campos ad-hoc devem ser normalizados para `pii.<tipo>` e adicionados à lista de mascaramento via variável de ambiente.
5. **Retenção** – exportação diária para S3 Object Lock conforme [política de retenção](data_retention_policy.md).

## Procedimentos de Verificação

- Testes automatizados (`services/api/tests/unit/test_logging_masking.py`) validam mascaramento.
- Revisões de código devem rejeitar logs com interpolação direta de dados sensíveis.
- Ferramenta `gitleaks` roda nos commits para detectar strings aparentes de secrets.

## Exceções

Qualquer necessidade de logar PII integral deve ser aprovada pelo DPO e registrada no Atlas (tag `pii-exception`) com data de expiração.
