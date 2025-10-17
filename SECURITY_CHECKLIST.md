# Checklist de Segurança – Atlas Knowledge (Atualizado: Outubro/2025)

## Autenticação & Autorização
- [ ] JWT RS256 com chaves armazenadas no AWS Secrets Manager / KMS (atualmente definidos via variáveis `.env`; migrar para secret gerenciado na cloud).
- [x] TTL curto para access token (≤15 min) e refresh token (≤7 dias) configurados em `settings`.
- [x] Revogação / blacklist via `jti` (Redis) para sessões críticas.
- [x] RBAC por organização (admin/editor/viewer) aplicado nas rotas principais.
- [x] MFA obrigatório para perfis administrativos (`/auth/login` exige TOTP quando `ENFORCE_ADMIN_MFA=true`).

## Transporte & Perímetro
- [ ] Todo tráfego externo via HTTPS (ALB + ACM) com HSTS – previsto em Terraform, falta provisionar certificados e validar redirects.
- [x] CORS restrito ao domínio do frontend (config via `CORS_ALLOWED_ORIGINS`).
- [ ] WAF com regras OWASP + rate-limit defensivo (`infra/terraform/modules/waf`) – módulo pronto, precisa ser habilitado por ambiente.
- [ ] SG/IAM minimizando superfícies (sem acesso público a RDS/Redis) – depende do apply das stacks Terraform.

## Aplicação
- [x] Rate-limit em mutações (`fastapi-limiter` + Redis/SQS).
- [x] Idempotência em POST/PUT/PATCH/DELETE críticos.
- [x] Sanitização de entradas (pydantic + validações custom).
- [x] Logs sem PII sensível; mascaramento automático (`LOG_MASK_FIELDS`, ver `docs/security/logging_standards.md`).
- [ ] Content Security Policy e headers (`X-Frame-Options`, `X-Content-Type-Options`) – middleware implementado, mas revisar valores antes da publicação.

## Dados & Armazenamento
- [ ] RDS com encriptação at-rest, backups automáticos e testes de restauração – infraestrutura descrita em Terraform, resta validar apply/testes.
- [ ] OpenSearch com encriptação at-rest e em trânsito, políticas de acesso IAM – idem RDS.
- [ ] Rotação de secrets automática (AWS Secrets Manager + Lambda) – módulo disponível, ainda não habilitado em nenhum ambiente.
- [x] Tabelas sensíveis com auditoria (`updated_by`, `updated_at`).
- [x] Política de retenção de logs/metadados documentada (`docs/security/data_retention_policy.md`).

## DevSecOps
- [x] Pre-commit com gitleaks.
- [x] Dependabot + SAST (CodeQL) + SCA (Trivy/pip-audit) configurados no CI.
- [ ] CI bloqueia PR < 85% cobertura ou lint falhando (`tools/ci/check_coverage.py`) – script existe, mas faltam gates obrigatórios na pipeline `pr.yml`.
- [x] Builds reprodutíveis (Poetry lock check, npm audit & lockfiles versionados, módulos Terraform versionados).
- [ ] Revisão obrigatória e branch protection em `main` – política definida no doc, porém não aplicada no repositório público.

## Observabilidade & Resposta a Incidentes
- [ ] Alertas p95, 5xx, backlog SQS, memória ECS, status OpenSearch – definidos no Terraform/Prometheus, aguardam integração com canais de alerta.
- [ ] Dashboards com contexto: trace_id, user/org, rota, latência – modelos prontos, mas sem evidência de uso em ambiente cloud.
- [x] Playbooks de incidente documentados (`docs/security/incident_response_playbook.md`).
- [ ] Testes regulares de observabilidade descritos (`docs/security/runbooks.md`) – roteiro existe, porém execuções não foram registradas.
- [ ] Runbooks automatizados para reindexação e dreno de fila (`docs/security/runbooks.md`) – scripts/processos ainda não automatizados.

## Conformidade & Governança
- [x] Política de privacidade e conservação de dados publicada (`docs/security/privacy_policy.md`).
- [ ] Revisões periódicas de permissões documentadas (`docs/security/access_governance.md`) – fluxo descrito, falta calendarização real.
- [ ] Logs de auditoria exportados para storage WORM – processo planejado, ainda não implantado.
- [ ] Registros de acesso administrativo auditáveis – depende de implantação efetiva do Secrets Manager/CloudTrail.
- [ ] Checklist revisado a cada release maior (versão atual registrada) – esta é a primeira revisão com visão honesta das pendências.
