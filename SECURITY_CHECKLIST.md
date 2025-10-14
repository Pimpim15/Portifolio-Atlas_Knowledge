# Checklist de Segurança – Atlas Knowledge

## Autenticação & Autorização
- [ ] JWT RS256 com chaves armazenadas no AWS Secrets Manager / KMS.
- [ ] TTL curto para access token (≤15 min) e refresh token (≤7 dias).
- [ ] Revogação / blacklist via `jti` (Redis) para sessões críticas.
- [ ] RBAC por organização (admin/editor/viewer) aplicado em todas as rotas.
- [ ] MFA opcional para perfis administrativos.

## Transporte & Perímetro
- [ ] Todo tráfego externo via HTTPS (ALB + ACM) com HSTS.
- [ ] CORS restrito ao domínio do frontend.
- [ ] WAF (opcional) com regras OWASP + rate-limit defensivo.
- [ ] SG/IAM minimizando superfícies (sem acesso público a RDS/Redis).

## Aplicação
- [ ] Rate-limit em mutações (`fastapi-limiter` + Redis/SQS).
- [ ] Idempotência em POST/PUT/PATCH/DELETE críticos.
- [ ] Sanitização de entradas (pydantic + validações custom).
- [ ] Logs sem PII sensível; mascarar campos (email, ids) se necessário.
- [ ] Content Security Policy e headers (`X-Frame-Options`, `X-Content-Type-Options`).

## Dados & Armazenamento
- [ ] RDS com encriptação at-rest, backups automáticos e testes de restauração.
- [ ] OpenSearch com encriptação at-rest e em trânsito, políticas de acesso IAM.
- [ ] Rotação de secrets automática (AWS Secrets Manager + Lambda opcional).
- [ ] Tabelas sensíveis com auditoria (`updated_by`, `updated_at`).
- [ ] Política de retenção de logs/metadados documentada.

## DevSecOps
- [ ] Pre-commit com gitleaks / detect-secrets.
- [ ] Dependabot + SAST (CodeQL) + SCA (Trivy/pip-audit).
- [ ] CI bloqueia PR < 85% cobertura ou lint falhando.
- [ ] Builds reprodutíveis (hash lockfiles: Poetry, npm, Terraform).
- [ ] Revisão obrigatória e branch protection em `main`.

## Observabilidade & Resposta a Incidentes
- [ ] Alertas p95, 5xx, backlog SQS, memória ECS, status OpenSearch.
- [ ] Dashboards com contexto: trace_id, user/org, rota, latência.
- [ ] Playbooks de incidente documentados no próprio Atlas.
- [ ] Testes regulares de observabilidade (traces presentes, métricas atualizadas).
- [ ] Runbooks automatizados para reindexação e dreno de fila.

## Conformidade & Governança
- [ ] Política de privacidade e conservação de dados publicada.
- [ ] Revisões periódicas de permissões (IAM, RBAC, Secrets).
- [ ] Logs de auditoria exportados para storage WORM (ex.: S3 Glacier, 365 dias).
- [ ] Registros de acesso administrativo (terraform apply, ECS update) auditáveis.
- [ ] Checklist revisado a cada release maior.
