# Governança de Acessos e Permissões

## Ciclo de Revisão

| Frequência | Responsáveis | Escopo |
| --- | --- | --- |
| Mensal | Time de plataforma | Revisar perfis administradores no Atlas e expirar contas inativas > 90 dias |
| Trimestral | Segurança + RH | Validar permissões IAM, roles do Terraform e usuários CI/CD |
| Semestral | Comitê de governança | Auditoria cruzada entre Atlas, GitHub, AWS Organizations |

## Procedimento Mensal

1. Exportar relatório `GET /users/admins` (rota interna) e comparar com planilha de gestores.
2. Verificar se todos os administradores estão com MFA ativo (consultar `/auth/mfa/setup` logs conforme [guia de onboarding](mfa_onboarding.md)).
3. Desativar (flag `is_active = false`) usuários sem justificativa válida.
4. Registrar evidências no Atlas (categoria **Auditoria**).

## Revisão Trimestral IAM

- Rodar `aws iam generate-service-last-accessed-details` por role crítica.
- Comparar com manifesto `infra/terraform` e garantir que apenas o Terraform gerencia permissões permanentes.
- Apagar chaves de acesso não utilizadas > 45 dias.

## Auditoria Semestral

- Conferir branch protection (`main`) com revisão obrigatória e assinaturas de commits.
- Validar integridade dos pipelines (CodeQL, Trivy, pip-audit) e atualizar versões de actions.
- Emitir declaração formal assinada pelo CISO e arquivar no Atlas (tag `compliance`).
- Revisar registros do AWS CloudTrail (`terraform apply`, `ecs:update-service`) e anexar relatório.

## Ferramentas de Suporte

- Dashboard `docs/security/dependency_governance.md` contém checklist automatizado.
- Script `tools/security/iam_review.md` oferece template de evidências.
