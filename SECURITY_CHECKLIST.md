# Checklist de Segurança – Atlas Knowledge

## Autenticação & Autorização
- [x] JWT RS256 com chaves armazenadas no AWS Secrets Manager / KMS.
- [x] TTL curto para access token (≤15 min) e refresh token (≤7 dias).
- [x] Revogação / blacklist via `jti` (Redis) para sessões críticas.
- [x] RBAC por organização (admin/editor/viewer) aplicado em todas as rotas.
- [ ] MFA opcional para perfis administrativos.

## Transporte & Perímetro
- [x] Todo tráfego externo via HTTPS (ALB + ACM) com HSTS.
- [ ] CORS restrito ao domínio do frontend.
- [ ] WAF (opcional) com regras OWASP + rate-limit defensivo.
- [x] SG/IAM minimizando superfícies (sem acesso público a RDS/Redis).

## Aplicação
- [x] Rate-limit em mutações (`fastapi-limiter` + Redis/SQS).
- [x] Idempotência em POST/PUT/PATCH/DELETE críticos.
- [x] Sanitização de entradas (pydantic + validações custom).
- [ ] Logs sem PII sensível; mascarar campos (email, ids) se necessário.
- [x] Content Security Policy e headers (`X-Frame-Options`, `X-Content-Type-Options`).

## Dados & Armazenamento
- [x] RDS com encriptação at-rest, backups automáticos e testes de restauração.
- [x] OpenSearch com encriptação at-rest e em trânsito, políticas de acesso IAM.
- [x] Rotação de secrets automática (AWS Secrets Manager + Lambda opcional).
- [x] Tabelas sensíveis com auditoria (`updated_by`, `updated_at`).
- [ ] Política de retenção de logs/metadados documentada.

## DevSecOps
- [x] Pre-commit com gitleaks / detect-secrets.
- [ ] Dependabot + SAST (CodeQL) + SCA (Trivy/pip-audit).
- [ ] CI bloqueia PR < 85% cobertura ou lint falhando.
- [ ] Builds reprodutíveis (hash lockfiles: Poetry, npm, Terraform).
- [ ] Revisão obrigatória e branch protection em `main`.

## Observabilidade & Resposta a Incidentes
- [x] Alertas p95, 5xx, backlog SQS, memória ECS, status OpenSearch.
- [x] Dashboards com contexto: trace_id, user/org, rota, latência.
- [ ] Playbooks de incidente documentados no próprio Atlas.
- [ ] Testes regulares de observabilidade (traces presentes, métricas atualizadas).
- [ ] Runbooks automatizados para reindexação e dreno de fila.

## Conformidade & Governança
- [ ] Política de privacidade e conservação de dados publicada.
- [ ] Revisões periódicas de permissões (IAM, RBAC, Secrets).
- [ ] Logs de auditoria exportados para storage WORM (ex.: S3 Glacier, 365 dias).
- [ ] Registros de acesso administrativo (terraform apply, ECS update) auditáveis.
- [ ] Checklist revisado a cada release maior.
