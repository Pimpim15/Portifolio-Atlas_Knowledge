# Atlas Knowledge

Atlas Knowledge é um catálogo interno multi-tenant com busca full-text que consolida conhecimento institucional com governança forte. A plataforma foi pensada como um projeto vitrine de arquitetura moderna, resiliente e observável, combinando FastAPI, PostgreSQL, OpenSearch, processamento assíncrono com Celery/SQS e deploy completo em AWS.

## Visão geral

- **API**: FastAPI + SQLAlchemy + Alembic, autenticação JWT RS256, RBAC, idempotência e rate-limit.
- **Worker**: Celery consumindo SQS para pipeline assíncrona de indexação no OpenSearch.
- **Frontend**: Vue 3 + Pinia + Vite consumindo a API.
- **Busca**: OpenSearch com analyzers PT/EN, sinônimos e filtros por tags.
- **Infraestrutura**: Terraform para VPC, ECS Fargate, RDS, OpenSearch, SQS, Secrets Manager, IAM OIDC.
- **Observabilidade**: OpenTelemetry → ADOT → AWS X-Ray, CloudWatch Logs, métricas e alarmes.
- **Qualidade**: pytest (unit, integração, e2e), cobertura ≥ 85%, lint (ruff), mypy, pre-commit, Trivy e CodeQL.

## Arquitetura

```mermaid
flowchart LR
  User --> ALB
  ALB --> API[ECS Fargate - FastAPI]
  API --> RDS[(RDS Postgres)]
  API --> SQS[(SQS)]
  API --> OS[(OpenSearch)]
  SQS --> Worker[ECS Fargate - Celery]
  Worker --> OS
  API -. OTEL .-> ADOT[(Collector)]
  ADOT --> XRay[(AWS X-Ray)]
```

## Estrutura do repositório

```
atlas-knowledge/
├─ services/
│  ├─ api/              # FastAPI app + testes
│  ├─ worker/           # Celery worker
│  └─ frontend/         # Vue 3 + Pinia
├─ infra/
│  ├─ terraform/        # IaC (módulos + ambientes)
│  └─ docker-compose.yml# Ambiente local
├─ .github/workflows/   # Pipelines CI/CD
├─ scripts/             # Seeds, utilitários
├─ bench/               # Locust/wrk cenários
├─ tests/               # Suites transversais
├─ README.md            # Este documento
└─ SECURITY_CHECKLIST.md
```

## Como rodar localmente

1. Instale pré-requisitos: Docker, Docker Compose, Python 3.11+, Node 20+.
2. Copie `.env.example` para `.env` preenchendo variáveis mínimas.
3. Use o Makefile:

```bash
make bootstrap
make dev
```

4. Acesse:
   - API: http://localhost:8000/docs
   - Frontend: http://localhost:5173
   - OpenSearch Dashboards: http://localhost:5601

### Fluxo atual no frontend

O login usa as credenciais fixas `admin@acme.com` / `admin`. Após autenticar, você verá a tela de busca. Os componentes principais ainda são _stubs_:

- O campo de busca dispara `GET /search?q=<termo>`, mas o _guard_ de RBAC ainda não está conectado ao JWT decodificado. Por isso, a API responde `403 Insufficient role` e o frontend permanece sem resultados.
- As rotas de documentos (`POST /docs`, `GET /docs/{id}`) guardam o conteúdo em memória apenas durante o ciclo de vida do processo e também dependem do mesmo RBAC, então retornam `403` no estado atual.

Para inspecionar o que está acontecendo abra o DevTools → aba **Network** e tente uma busca; você verá a resposta `403` da rota `/search`. Para validar as chamadas diretamente, utilize o Swagger em http://localhost:8000/docs ou scripts como:

```powershell
$token = (Invoke-RestMethod -Method Post -Uri http://localhost:8000/auth/login -Body (@{ email = 'admin@acme.com'; password = 'admin' } | ConvertTo-Json) -ContentType 'application/json').access
Invoke-RestMethod -Method Get -Uri 'http://localhost:8000/search?q=runbook' -Headers @{ Authorization = "Bearer $token" }
```

O próximo passo de evolução é ligar o `RBACGuard` à decodificação do JWT (claims `roles`) e implementar a busca real contra o OpenSearch ou, provisoriamente, contra a coleção em memória de documentos.

## Pipelines

- `pr.yml`: lint (ruff), type-check (mypy), testes (pytest + coverage ≥ 85%), CodeQL, Trivy.
- `deploy.yml`: build/push imagens para ECR, Terraform plan/apply, ECS deploy (dev/prod).

## Observabilidade

- Logs JSON com structlog (campos: trace_id, span_id, route, org_id, user, status, latency).
- OpenTelemetry instrumentando FastAPI, SQLAlchemy, HTTP clients. Export via OTLP para collector.
- Dashboards CloudWatch: latência p95, erros 5xx, backlog SQS, métricas RDS, saúde do OpenSearch.

## Segurança

Confira a lista completa em [`SECURITY_CHECKLIST.md`](SECURITY_CHECKLIST.md). Destaques:

- JWT RS256, chaves em AWS Secrets Manager.
- Rate-limit e idempotência em mutações.
- IAM least privilege, SG fechados, HTTPS obrigatório, CORS estrito.
- SAST/DAST (CodeQL, Trivy), Dependabot, gitleaks.
- Backups RDS, testes de restauração, logs sem PII sensível.

## Roadmap inicial

- [ ] Implementar modelos SQLAlchemy e migrations iniciais.
- [ ] Construir roteadores (auth, users, docs, search) com RBAC.
- [ ] Configurar Celery + pipeline SQS → OpenSearch.
- [ ] Implementar UI Vue (login, CRUD docs, busca, dashboards).
- [ ] Completar módulos Terraform com recursos reais.
- [ ] Automatizar deploy dev (GitHub Actions + Terraform).
- [ ] Criar cenários Locust/wrk e capturar métricas.
- [ ] Publicar screenshots/logs/dashboards no README.

## Créditos

Projeto idealizado para demonstrar arquitetura moderna, escalável e observável em um único monorepo, servindo como portfólio profissional.
