# Evidências de Segurança e Conformidade

Este documento consolida as principais evidências exigidas no Passo 3 da remediação (Segurança & Conformidade).

## 1. SAST e SCA

| Ferramenta | Escopo | Como executar manualmente | Evidência CI |
| --- | --- | --- | --- |
| `pip-audit --strict` | Dependências Python | `poetry run pip-audit --strict` | Job `lint-test` em `.github/workflows/pr.yml` |
| `npm audit --audit-level=high` | SPA Vue 3 | `npm install && npm audit --audit-level=high` na pasta `services/frontend` | Job `frontend` |
| Trivy (FS) | Repositório completo | `trivy fs --severity CRITICAL,HIGH .` | Job `security` |
| CodeQL | Python + JavaScript | `codeql database create/analyze` (via CLI GitHub) | Job `security` |

Todos os jobs anexam logs nos pipelines de PR. Ao concluir um ciclo de revisão, exporte os artefatos e armazene no Atlas (tag `sast-evidence`).

## 2. Controles de Acesso

- MFA obrigatório para papéis em `ADMIN_MFA_ROLES`. Fluxo documentado em [`docs/security/mfa_onboarding.md`](mfa_onboarding.md) e coberto pelo teste `tests/api/test_security.py::test_mfa_onboarding_flow`.
- Governança de acesso revisada em [`docs/security/access_governance.md`](access_governance.md); registre a ata trimestral anexando o JSON de `/auth/mfa/setup` e o checklist no Atlas.

## 3. Proteções de Aplicação

- Middleware de cabeçalhos garante CSP, HSTS, X-Frame-Options etc. Validação automatizada: `tests/api/test_security.py::test_security_headers_applied`.
- Rate-limit defensivo (`RATE_LIMIT_AUTH`) bloqueia abuso de login. Evidência automatizada: `tests/api/test_security.py::test_login_rate_limit_enforced`.

## 4. Privacidade e Termos

- Política de privacidade atualizada em [`docs/security/privacy_policy.md`](privacy_policy.md) com SLA de resposta (10 dias úteis).
- Política de retenção (`docs/security/data_retention_policy.md`) define tempos de guarda e destruição segura.
- Dependências e supply chain cobertas por [`docs/security/dependency_governance.md`](dependency_governance.md).

## 5. Próximos passos de auditoria

1. Exportar relatórios SAST/SCA e anexar ao repositório de evidências a cada release.
2. Registrar execução dos testes automatizados (`pytest services/api/tests/test_security.py`).
3. Atualizar o checklist (`SECURITY_CHECKLIST.md`) marcando itens concluídos e documentando pendências abertas (WAF, Secrets Manager, observabilidade em cloud).
