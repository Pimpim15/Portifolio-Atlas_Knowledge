# Onboarding de MFA para Administradores

Este guia descreve o fluxo oficial para habilitar MFA TOTP em contas administrativas do Atlas Knowledge. As rotas fazem parte da API `/auth` e exigem autenticação prévia com token de acesso válido.

## Requisitos

- Usuário com papel listado em `ADMIN_MFA_ROLES` (por padrão: `admin`).
- Login inicial realizado com senha temporária gerada pelo time de plataforma.
- Aplicativo autenticador compatível com TOTP (Google Authenticator, 1Password, Authy, etc.).

## Passo a passo

1. **Login inicial** – autentique-se com `/auth/login` usando as credenciais provisórias. Como o usuário ainda não possui MFA ativo, o login será aceito sem código (apenas nesta primeira vez).
2. **Gerar segredo** – invoque `POST /auth/mfa/setup` com o header `Authorization: Bearer <token>`. A resposta contém:
   - `secret`: chave base32 para guardar em local seguro.
   - `provisioning_uri`: URI `otpauth://` pronta para ser lida pelo autenticador.
   - `issuer`: identificador exibido no app para diferenciar contas.
3. **Registrar no autenticador** – escaneie a URI no aplicativo ou informe o `secret` manualmente.
4. **Ativar MFA** – confirme o código gerado chamando `POST /auth/mfa/activate` com `{"code": "123456"}`. Após ativação, `mfa_enabled` passa a `true` e o próximo login já exigirá MFA.
5. **Validar** – finalize a sessão (`/auth/logout`) e realize novo login passando o `mfa_code`. Falhas consecutivas acionam rate-limit defensivo.

## Exemplos em PowerShell

```powershell
# 1. Login inicial
$loginBody = @{ email = 'novo.admin@acme.com'; password = 'SenhaTemporaria123' } | ConvertTo-Json
$loginResponse = Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/auth/login' -Body $loginBody -ContentType 'application/json'
$token = $loginResponse.access

# 2. Solicitar segredo TOTP
$setup = Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/auth/mfa/setup' -Headers @{ Authorization = "Bearer $token" }
$setup.secret
$setup.provisioning_uri

# 3. Confirmar código do autenticador
$activateBody = @{ code = Read-Host 'Informe o código MFA' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/auth/mfa/activate' -Headers @{ Authorization = "Bearer $token" } -Body $activateBody -ContentType 'application/json'
```

## Recuperação e rotação

- Chamar novamente `POST /auth/mfa/setup` invalida o segredo anterior e força nova ativação (ideal para reset administrativo).
- Para contas bloqueadas sem código válido, um operador com acesso ao banco pode zerar `mfa_secret`/`mfa_enabled` e obrigar o processo desde o passo 1.
- Documente a finalização do onboarding na planilha de acessos e anexe evidência (screenshot ou JSON) ao ticket de provisionamento.
