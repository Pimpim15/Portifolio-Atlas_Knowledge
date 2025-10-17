# Relatório de Validação de UX / Frontend

Última atualização: 17/10/2025 (branch `feature/product-ready-progress`).

## Objetivo

Garantir que a experiência do usuário no Atlas Knowledge esteja alinhada às expectativas de release público. O relatório consolida os cenários críticos validados manualmente e evidencia as lacunas que ainda impedem uma entrega "product ready".

## Metodologia

1. **Smoke manual guiado** – seguindo o tutorial `docs/tutorials/document-lifecycle.md` em ambiente local (`docker compose + npm run dev`).
2. **Testes automatizados** – backend (`poetry run pytest services/api/tests`) garante consistência dos fluxos usados pelo frontend; ainda não há testes E2E de UI.
3. **Checklist heurístico** – verificação de copy, feedback visual e acessibilidade básica (navegação por teclado e foco visível). Itens de ARIA e contraste permanecem sem validação.

## Cenários exercitados

| Cenário | Passos | Resultado |
| --- | --- | --- |
| Login com MFA | Abrir SPA → inserir credenciais → código TOTP | ✅ Sucesso, fallback de erro presente para código inválido |
| Busca de runbooks | Termo "Runbook" + filtros de tag | ⚠️ Requer rodar `/docs/reindex` manualmente para que documentos seed apareçam |
| CRUD de documentos | Criar, editar e visualizar histórico | ✅ Versão incrementada, histórico ordenado, feedback de toast |
| Painel de reindex | Listar jobs → disparar reindex → acompanhar progresso | ⚠️ Contadores atualizam apenas quando o worker/SQS estão ativos; em modo inline não há feedback visual |
| Insights analíticos | Visualizar gráficos e tabela de documentos recentes | ⚠️ Depende da reindex manual e do endpoint `/docs/stats`; gráficos sem dados quando o seed não foi reprocessado |
| Sessão e logout | Acessar `/users/me`, revogar tokens via botão sair | ✅ Tokens limpos, redirect para tela de login |

## Feedback de copy/posicionamento

- Terminologia alinhada com público de operações ("Runbook", "Checklist", "Reindex").
- Mensagens de erro orientam próximas ações (ex.: "Inclua o código MFA gerado no autenticador").
- Call to action principal usa verbos claros ("Novo documento", "Reindexar agora").
- Documentação externa foi atualizada para evidenciar as lacunas ainda não resolvidas.

## Melhorias aplicadas

- Ajuste do README e dos guias (`docs/onboarding.md`, `docs/tutorials/document-lifecycle.md`) para registrar dependências de reindex manual e cobertura parcial.
- Validação do fluxo de insights condicionada ao worker/SQS funcionando; documentado como limitação conhecida.
- Scripts de benchmarks e testes automatizados listados como próximos passos obrigatórios para a release.

## Próximos passos sugeridos

1. Automatizar cenários E2E (Playwright) usando roteiro deste relatório.
2. Incluir testes de acessibilidade (axe-core) no pipeline de CI.
3. Conduzir sessões de teste com usuários finais para coletar feedback qualitativo pós-release.
4. Garantir que o worker/SQS esteja ativo em ambientes de demo ou ajustar o painel para operar em modo inline.

Registre as sessões futuras com data, ambiente e observações neste arquivo para manter rastreabilidade.
