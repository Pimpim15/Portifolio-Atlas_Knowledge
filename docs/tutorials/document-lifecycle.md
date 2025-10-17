# Tutorial: Ciclo de Vida de Documentos no Atlas Knowledge

Este passo a passo demonstra como um time operacional usa o Atlas Knowledge para cadastrar e manter runbooks. O fluxo cobre frontend e API, incluindo validações, reindexação e análises.

## 1. Preparação

1. Certifique-se de que o ambiente local está ativo (`docker compose up -d`).
2. Rode `npm run dev` em `services/frontend` para iniciar o SPA na porta 5173.
3. Garanta que o usuário `admin@acme.com` foi bootstrapado e já possui MFA configurado.

## 2. Login com MFA

1. Acesse `http://localhost:5173`.
2. Informe email/senha padrão (`admin@acme.com` / `admin`).
3. Gere o TOTP no autenticador e insira no campo "Código MFA".
4. Confirme que o token de sessão é armazenado e você é redirecionado para a busca.

## 3. Localizar runbooks existentes

1. Use o campo de busca para procurar "Runbook".
2. Valide que os cartões mostram `snippet`, tags e data relativa.
3. Clique em um item para abrir o modal de detalhes; verifique campos `Versão`, `Atualizado por` e tags.

## 4. Criar novo documento (UI)

1. Clique em **Novo documento** (disponível para admins/editores).
2. Preencha:
   - Título: `Checklist de Continuidade`
   - Conteúdo: descreva passos críticos.
   - Tags: `dr`, `resposta`.
3. Envie e verifique o toast de sucesso.
4. O documento deve aparecer na grade automaticamente.

## 5. Editar documento existente (UI)

1. Abra o documento recém-criado.
2. Clique em **Editar** e atualize o corpo e uma tag extra (`comunicacao`).
3. Salve e confirme que a versão subiu (ex.: de 1 para 2) e o histórico foi atualizado.

## 6. Reindexar pela API

1. Copie o `Id` do documento.
2. Usando o terminal PowerShell:

   ```powershell
   $login = Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/auth/login' -Body (@{ email = 'admin@acme.com'; password = 'admin'; mfa_code = '<TOTPAqui>' } | ConvertTo-Json) -ContentType 'application/json'
   $headers = @{ Authorization = "Bearer $($login.access)" }
   Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/docs/reindex' -Headers $headers
   ```

3. Retorne à UI e abra o painel de reindex. O job criado deve aparecer com status `running` e evoluir para `success`.

## 7. Verificar estatísticas

1. Acesse o menu **Insights**.
2. Confirme que os gráficos exibem o documento recém-criado nas métricas de recentes e top tags.
3. Se desejar validar via API: `Invoke-RestMethod -Method Get -Uri 'http://localhost:8000/docs/stats' -Headers $headers`.

## 8. Excluir e restaurar (opcional)

Caso o ambiente esteja com SQS/worker ativos, experimente apagar o documento via API (`DELETE /docs/{id}`—rotina disponível na API) e executar uma restauração criando uma nova versão. Verifique como o histórico registra a mudança.

## 9. Checklist de validação

- Login com MFA funciona em UI e API.
- Criação/edição refletem na grade, no histórico e nos índices de busca.
- Reindex job aparece com contadores consistentes e termina em `success`.
- Métricas e dashboards foram atualizados.
- Logs em `docker compose logs api` mostram `request_completed` sem PII sensível.

Documente qualquer divergência e abra issue no GitHub usando o template `bug-report`. Para automatizar esse fluxo no futuro, planeje cenários E2E (Cypress/Playwright) com base nestes passos.
