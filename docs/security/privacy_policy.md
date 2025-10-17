# Política de Privacidade e Proteção de Dados

Esta política descreve como o Atlas Knowledge coleta, utiliza, retém e compartilha dados pessoais e institucionais.

## Princípios

- **Minimização**: apenas atributos necessários para autenticação, autorização e auditoria são coletados (e-mail corporativo e identificadores organizacionais).
- **Transparência**: usuários têm acesso ao histórico de auditoria dos seus acessos e podem solicitar exportação dos dados pertinentes via time de governança.
- **Segurança**: todo o tráfego é criptografado (HTTPS/TLS 1.2+), secrets permanecem no AWS Secrets Manager/KMS e dados sensíveis em repouso são cifrados com chaves gerenciadas.

## Categorias de Dados

| Categoria | Finalidade | Base legal |
| --- | --- | --- |
| Credenciais (e-mail corporativo) | Autenticação e contato de incidente | Legítimo interesse |
| Metadados de acesso (IP, timestamps, organização) | Auditoria, resposta a incidentes | Legítimo interesse |
| Conteúdo publicado no Atlas | Gestão do conhecimento institucional | Consentimento organizacional |

## Direitos dos Usuários

1. **Acesso** – usuários podem visualizar dados pessoais relacionados ao seu perfil na tela **Meu Acesso**.
2. **Correção** – alterações cadastrais devem ser solicitadas ao RH/gestor da organização.
3. **Exclusão** – remoção de contas inativas acontece automaticamente após o período de retenção definido na [política de retenção](data_retention_policy.md).
4. **Portabilidade** – exportações são disponibilizadas mediante chamado para o time de governança.

## Compartilhamento

- Não há compartilhamento com terceiros. Logs e backups permanecem restritos às contas AWS dedicadas do Atlas.
- Fornecedores (AWS, GitHub) seguem os contratos padrão corporativos da Acme Corp.

## Segurança Operacional

- MFA obrigatório para perfis administrativos.
- Revisões trimestrais de permissões conforme [procedimento de governança](access_governance.md).
- Logs mascaram PII automaticamente e são exportados para armazenamento WORM (S3 Glacier) por 365 dias.

## Contato

Solicitações e dúvidas devem ser encaminhadas para `privacy@acme.com`. Tempo máximo de resposta: **10 dias úteis**.
