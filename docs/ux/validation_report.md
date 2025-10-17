# Relatório de Validação de UX / Frontend

Última atualização: 17/10/2025 (feature branch `feature/product-ready-progress`).

## Objetivo

Garantir que a experiência do usuário no Atlas Knowledge esteja alinhada às expectativas de release público. O relatório consolida os cenários críticos validados manualmente e via suite de testes automatizados.

## Metodologia

1. **Smoke manual guiado** – seguindo o tutorial `docs/tutorials/document-lifecycle.md` em ambiente local (`docker compose + npm run dev`).
2. **Testes automatizados** – backend (`poetry run pytest services/api/tests`) garante consistência dos fluxos usados pelo frontend.
3. **Checklist heurístico** – verificação de copy, feedback visual e acessibilidade básica (navegação por teclado e foco visível).

## Cenários exercitados

| Cenário | Passos | Resultado |
| --- | --- | --- |
| Login com MFA | Abrir SPA → inserir credenciais → código TOTP | ✅ Sucesso, fallback de erro presente para código inválido |
| Busca de runbooks | Termo "Runbook" + filtros de tag | ✅ Resultados com snippet e badges de tags, mensagens de vazio contextualizadas |
| CRUD de documentos | Criar, editar e visualizar histórico | ✅ Versão incrementada, histórico ordenado, feedback de toast |
| Painel de reindex | Listar jobs → disparar reindex → acompanhar progresso | ✅ Contadores sincronizados com API, estados `running` → `success` |
| Insights analíticos | Visualizar gráficos e tabela de documentos recentes | ✅ Dados refletindo alterações recentes após reindex |
| Sessão e logout | Acessar `/users/me`, revogar tokens via botão sair | ✅ Tokens limpos, redirect para tela de login |

## Feedback de copy/posicionamento

- Terminologia alinhada com público de operações ("Runbook", "Checklist", "Reindex").
- Mensagens de erro orientam próximas ações (ex.: "Inclua o código MFA gerado no autenticador").
- Call to action principal usa verbos claros ("Novo documento", "Reindexar agora").
- Documentação externa (`README.md`, `docs/onboarding.md`) complementa narrativa com benefícios de negócio.

## Melhorias aplicadas

- Secção "Proposta de Valor" adicionada ao README para reforçar posicionamento público.
- Atualização dos guias de onboarding, API reference e tutorial de ciclo de vida.
- Lista de pendências do README revisada para refletir status atualizado de UX.

## Próximos passos sugeridos

1. Automatizar cenários E2E (Playwright) usando roteiro deste relatório.
2. Incluir testes de acessibilidade (axe-core) no pipeline de CI.
3. Conduzir sessões de teste com usuários finais para coletar feedback qualitativo pós-release.

Registre as sessões futuras com data, ambiente e observações neste arquivo para manter rastreabilidade.
