# Guia de Onboarding do Atlas Knowledge

Este guia conduz novas equipes de produto, operações e suporte pelos primeiros passos com o Atlas Knowledge. Ele complementa o `README.md` com instruções práticas para colocar a plataforma em produção e garantir que cada squad entenda responsabilidades compartilhadas.

## 1. Perfis de público e objetivos

- **Equipe de Produto/UX**: validar jornadas, revisar copy e garantir aderência às necessidades do cliente final.
- **Equipe de Engenharia**: provisionar infraestrutura, configurar pipelines e manter observabilidade.
- **Equipe de Operações/CS**: acompanhar métricas, operar reindexações, revisar incidentes e atender clientes.

Cada perfil tem trilhas recomendadas, mas todos devem concluir os passos de infraestrutura mínima, segurança e validação funcional antes do handoff.

## 2. Pré-requisitos

1. Conta AWS com permissões para usar os módulos Terraform fornecidos (`infra/terraform`).
2. Repositório clonado e acesso ao GitHub Actions do projeto.
3. Ferramentas instaladas localmente: Docker, Docker Compose, Python 3.11+, Node 20+, Poetry e AWS CLI configurada.
4. Domínio e certificado TLS emitido no AWS Certificate Manager para o ALB.
5. Contas de e-mail para administradores iniciais (MFA obrigatório) e canal de incidentes definido (Slack/Teams).

## 3. Provisionamento inicial

1. Preencha `infra/terraform/envs/<env>/terraform.tfvars` com valores da organização (CIDR, subdomínios, ARNs, limites de custo).
2. Execute `make infra-plan ENV=dev` e revise o plano. Após validação, aplique com `make infra-apply ENV=dev`.
3. Configure secrets no GitHub (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `ECR_REGISTRY`) e habilite o pipeline `deploy.yml`.
4. Rode `make bootstrap` localmente para gerar `.env`, instalar dependências (Poetry/NPM) e popular o banco seed.
5. Execute `docker compose up -d` e confirme a saúde via `http://localhost:8000/health` e dashboards Grafana/Prometheus.

## 4. Segurança e conformidade

1. Atualize `.env` com as chaves RSA de produção e variáveis de CORS/MFA (`ATLAS_ENFORCE_ADMIN_MFA=true`).
2. Registre administradores iniciais acessando a API `/auth/login` com `admin@acme.com`/`admin` e configure TOTP via aplicativo autenticador (o seed inicial é impresso no console durante `make bootstrap`).
3. Revise `docs/security/*.md` e ajuste políticas para o cliente (governança de acesso, privacidade, retenção de dados, runbooks de incidentes).
4. Garanta que o WAF esteja habilitado (flag `enable_waf = true`) e que o CI esteja rodando `pip-audit`, `npm audit`, Trivy e CodeQL.
5. Configure os alertas de custo em `AWS Budgets` e o fluxo de incidentes (pager/Slack) com base no `SECURITY_CHECKLIST.md`.

## 5. Validação funcional end-to-end

1. Rode `poetry run pytest services/api/tests` para garantir que a API está íntegra com o SQLite recriado.
2. Execute `npm install` e `npm run dev` na pasta `services/frontend`; valide manualmente as jornadas descritas em `docs/ux/validation_report.md`.
3. Use o tutorial `docs/tutorials/document-lifecycle.md` para validar o ciclo completo de criação → atualização → reindex → análise.
4. Opcional: execute o cenário de carga com `python bench/run_headless.py --env local` e compare resultados com o histórico em `docs/performance-history.csv`.

## 6. Observabilidade e operações

1. Configure integrações de alerta para Prometheus e CloudWatch usando os `atlas-alerts.yml` e dashboards Terraform provisionados.
2. Revise o playbook de incidente (`docs/security/incident_response_playbook.md`) e realize um tabletop exercise.
3. Cadastre as rotinas de backup/restauração detalhadas em `docs/security/data_retention_policy.md` no runbook corporativo.
4. Documente no seu CMDB/Notion as URLs e credenciais iniciais (com rotação planejada) e vincule os dashboards principais.

## 7. Handoff e checklist final

- ✅ Infraestrutura provisionada (Terraform state versionado e pipelines autorizados).
- ✅ Admins com MFA ativo e políticas de segurança revisadas.
- ✅ Jornadas críticas validadas no frontend (login, busca, CRUD, reindex, analytics).
- ✅ Observabilidade conectada (Grafana, Prometheus, CloudWatch, alertas acionáveis).
- ✅ Documentação compartilhada com stakeholders (onboarding, API reference, tutoriais, políticas).

Com este checklist concluído, a equipe está pronta para iniciar o Passo 5 (go-to-market). Ajustes específicos do cliente devem ser versionados em `docs/customers/<cliente>/` para manter rastreabilidade.
