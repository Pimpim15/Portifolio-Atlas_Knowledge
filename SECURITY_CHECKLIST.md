# Checklist de Segurança – Atlas Knowledge (Atualizado: Outubro/2024)

## Autenticação & Autorização
- [x] JWT RS256 com chaves armazenadas no AWS Secrets Manager / KMS.
- [x] TTL curto para access token (≤15 min) e refresh token (≤7 dias).
- [x] Revogação / blacklist via `jti` (Redis) para sessões críticas.
- [x] RBAC por organização (admin/editor/viewer) aplicado em todas as rotas.
- [x] MFA opcional para perfis administrativos (`/auth/login` exige TOTP para roles admin).

## Transporte & Perímetro
- [x] Todo tráfego externo via HTTPS (ALB + ACM) com HSTS.
- [x] CORS restrito ao domínio do frontend (config via `CORS_ALLOWED_ORIGINS`).
- [x] WAF (opcional) com regras OWASP + rate-limit defensivo (`infra/terraform/modules/waf`).
- [x] SG/IAM minimizando superfícies (sem acesso público a RDS/Redis).

## Aplicação
- [x] Rate-limit em mutações (`fastapi-limiter` + Redis/SQS).
- [x] Idempotência em POST/PUT/PATCH/DELETE críticos.
- [x] Sanitização de entradas (pydantic + validações custom).
- [x] Logs sem PII sensível; mascaramento automático (`LOG_MASK_FIELDS`, ver `docs/security/logging_standards.md`).
- [x] Content Security Policy e headers (`X-Frame-Options`, `X-Content-Type-Options`).

## Dados & Armazenamento
- [x] RDS com encriptação at-rest, backups automáticos e testes de restauração.
- [x] OpenSearch com encriptação at-rest e em trânsito, políticas de acesso IAM.
- [x] Rotação de secrets automática (AWS Secrets Manager + Lambda opcional).
- [x] Tabelas sensíveis com auditoria (`updated_by`, `updated_at`).
- [x] Política de retenção de logs/metadados documentada (`docs/security/data_retention_policy.md`).

## DevSecOps
- [x] Pre-commit com gitleaks / detect-secrets.
- [x] Dependabot + SAST (CodeQL) + SCA (Trivy/pip-audit) (`.github/dependabot.yml`, CI atualizado).
- [x] CI bloqueia PR < 85% cobertura ou lint falhando (`tools/ci/check_coverage.py`).
- [x] Builds reprodutíveis (Poetry lock check, npm audit & lockfiles verificados, Terraform modules versionados).
- [x] Revisão obrigatória e branch protection em `main` documentadas (`docs/security/access_governance.md`).

## Observabilidade & Resposta a Incidentes
- [x] Alertas p95, 5xx, backlog SQS, memória ECS, status OpenSearch.
- [x] Dashboards com contexto: trace_id, user/org, rota, latência.
- [x] Playbooks de incidente documentados (`docs/security/incident_response_playbook.md`).
- [x] Testes regulares de observabilidade descritos (`docs/security/runbooks.md`).
- [x] Runbooks automatizados para reindexação e dreno de fila (`docs/security/runbooks.md`).

## Conformidade & Governança
- [x] Política de privacidade e conservação de dados publicada (`docs/security/privacy_policy.md`).
- [x] Revisões periódicas de permissões documentadas (`docs/security/access_governance.md`).
- [x] Logs de auditoria exportados para storage WORM (processo em `docs/security/data_retention_policy.md`).
- [x] Registros de acesso administrativo auditáveis (`docs/security/access_governance.md`).
- [x] Checklist revisado a cada release maior (versão atual registrada).
