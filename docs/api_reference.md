# Referência de API do Atlas Knowledge

Esta referência descreve os principais endpoints públicos da API FastAPI do Atlas Knowledge. Todos os exemplos assumem autenticação JWT RS256 e um ambiente padrão provisionado com as migrations mais recentes.

## Convenções

- **Base URL**: `https://api.<seu-dominio>` em produção. Em desenvolvimento use `http://localhost:8000`.
- **Autenticação**: tokens Bearer (`Authorization: Bearer <access_token>`). Tokens expiram conforme `access_token_ttl_minutes`.
- **Rate limit**: limites configuráveis via `settings.rate_limit_*`. Cabeçalhos `X-Request-ID` e `Retry-After` são retornados quando aplicável.
- **Idempotência**: mutações aceitam `Idempotency-Key` (UUID recomendada) para replays seguros.

## Autenticação

### POST /auth/login

Solicita par de tokens JWT. Administradores precisam informar código MFA TOTP quando `enforce_admin_mfa` está ativo.

```http
POST /auth/login HTTP/1.1
Content-Type: application/json

{
  "email": "admin@acme.com",
  "password": "admin",
  "mfa_code": "123456"
}
```

**Resposta 200**

```json
{
  "access": "<jwt access>",
  "refresh": "<jwt refresh>",
  "expires_at": "2025-10-17T12:40:00Z"
}
```

Erros comuns: `401 Invalid credentials`, `401 MFA code required` ou `401 Invalid MFA code`.

### POST /auth/logout

Revoga tokens ativos (access obrigatório, refresh opcional).

```http
POST /auth/logout HTTP/1.1
Authorization: Bearer <access>
Content-Type: application/json

{ "refresh": "<refresh>" }
```

Retorno `204 No Content` em caso de sucesso.

## Usuário

### GET /users/me

Retorna dados do usuário autenticado.

```json
{
  "id": "fc1e9b86-56b0-4b51-92ad-3b2e3d8ff901",
  "email": "admin@acme.com",
  "roles": ["admin"],
  "organizations": ["13b9455d-..."]
}
```

## Documentos

### POST /docs

Cria documento e agenda indexação.

```http
POST /docs HTTP/1.1
Authorization: Bearer <access>
Idempotency-Key: doc-create-1
Content-Type: application/json

{
  "title": "Check-list DR",
  "body": "Passo a passo de recuperação",
  "tags": ["dr", "contingencia"]
}
```

**Resposta 200** inclui `id`, `version`, `created_at`. Replay com mesma `Idempotency-Key` devolve payload cacheado.

### PUT /docs/{id}

Atualiza documento e gera nova versão.

```http
PUT /docs/2ac4... HTTP/1.1
Authorization: Bearer <access>
Idempotency-Key: doc-update-1
Content-Type: application/json

{
  "title": "Check-list DR (rev 2)",
  "body": "Conteúdo atualizado",
  "tags": ["dr", "resiliencia"]
}
```

### GET /docs/{id}

Retorna última versão de um documento.

### GET /docs/{id}/versions

Lista versões históricas (mais recente primeiro).

### POST /docs/reindex

Dispara job de reindexação. Requer papel `admin`.

**Resposta 202**

```json
{
  "id": "a40c...",
  "status": "running",
  "total_documents": 25,
  "processed_documents": 0,
  "pending_items": 25,
  "running_items": 0,
  "success_items": 0,
  "failed_items": 0
}
```

### GET /docs/reindex

Lista jobs com paginação (`limit`, `offset`).

### GET /docs/reindex/{job_id}/items

Consulta itens de um job. Suporta `limit` e `cursor` (base64) para paginação.

### GET /docs/stats

Retorna indicadores agregados usados nos dashboards de insights.

```json
{
  "totals": { "documents": 42, "versions": 68, "unique_tags": 11, "active_authors": 5, "avg_tags_per_document": 2.3 },
  "top_tags": [{ "tag": "dr", "count": 15 }],
  "top_authors": [{ "author_id": "...", "display_name": "Alice", "count": 12 }],
  "documents_by_day": [{ "date": "2025-10-15", "count": 4 }],
  "recent_documents": [{ "id": "...", "title": "Runbook P1", "created_at": "2025-10-16T20:10:00Z", "tags": ["incidentes"], "author": "alice@acme.com" }]
}
```

## Busca

### GET /search

Parâmetros:

- `q`: termo (opcional)
- `tags`: lista separada por vírgula

A API tenta usar OpenSearch e, em caso de falha, faz _fallback_ para PostgreSQL. Resposta:

```json
{
  "results": [
    {
      "id": "...",
      "title": "Runbook P1",
      "snippet": "Procedimento oficial...",
      "tags": ["incidentes", "p1"]
    }
  ],
  "total": 8
}
```

> Após o bootstrap inicial é necessário disparar `POST /docs/reindex` para que os documentos seed
> sejam enviados ao OpenSearch. Caso contrário, a busca retornará vazia.

## Saúde, métricas e utilidades

- `GET /health` – status de dependências (DB, Redis, OpenSearch, SQS).
- `GET /metrics` – Exposição Prometheus.

## Códigos de erro padrão

| Código | Significado | Observações |
| --- | --- | --- |
| 400 | Requisição inválida | Payload mal formatado, cursor inválido, etc. |
| 401 | Não autenticado | Login inválido, token ausente ou MFA obrigatório. |
| 403 | Proibido | Usuário sem papel necessário. |
| 404 | Não encontrado | Documento inexistente ou sem acesso. |
| 409 | Conflito | Chave de idempotência em uso por outro usuário. |
| 429 | Rate limit | SlowAPI retorna cabeçalhos `Retry-After`. |
| 500 | Erro interno | Logs estruturados em CloudWatch/Grafana com máscara de PII. |

## Referências adicionais

- Fluxo completo com exemplos de requisições: `docs/tutorials/document-lifecycle.md`.
- Padrões de mascaramento e governança de logs: `docs/security/logging_standards.md`.
- Segurança e políticas corporativas: `docs/security/*.md`.
