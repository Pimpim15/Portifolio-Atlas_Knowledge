# Playbook de Resposta a Incidentes

## Objetivos

- Garantir resposta coordenada a incidentes de segurança envolvendo o Atlas Knowledge.
- Minimizar impacto operacional e de reputação.
- Preservar evidências para investigação e obrigações legais.

## Equipe On-Call

| Função | Responsável | Contato |
| --- | --- | --- |
| Incident Commander | Engenheiro On-Call | pagerduty://atlas-ic |
| Comms Lead | Marketing/PR | pr@acme.com |
| Liaison Jurídico | Jurídico Corporativo | legal@acme.com |
| Observabilidade | SRE de Plantão | sre@acme.com |

## Fluxo (P1/P2)

1. **Detecção**
   - Alertas Prometheus/CloudWatch ou reporte manual pelo canal `#atlas-incidentes`.
2. **Classificação**
   - Incident Commander avalia severidade (P1/P2) e decide ativar ponte Zoom.
3. **Contenção Imediata**
   - Revogar tokens comprometidos (`/auth/logout` com blacklist).
   - Escalar WAF rule para **block** se ataque ativo.
   - Isolar workloads (ECS deploy com imagem estável).
4. **Comunicação**
   - Atualizações a cada 30 minutos em `#atlas-status`.
   - Registrar timeline no Atlas (tipo `incident_report`).
5. **Erradicação**
   - Aplicar patches, rotacionar secrets com Terraform/Secrets Manager.
   - Executar `scripts/run_local_benchmark.py --type post-incident` para validar estabilidade.
6. **Recuperação**
   - Monitorar KPIs (latência p95, erros 5xx) por 2h.
   - Emitir comunicado final aos stakeholders.
7. **Post-mortem (até 5 dias úteis)**
   - Realizar análise de causa raiz.
   - Documentar ações preventivas no Atlas (template `docs/templates/post_mortem.md`).

## Automação

- **Runbook**: `docs/security/runbooks.md` descreve scripts de verificação.
- **Retenção**: logs correlatos marcados e preservados conforme [política de retenção](data_retention_policy.md).

## Métricas

- MTTA alvo: ≤ 5 min.
- MTTR alvo: ≤ 90 min para incidentes P1.
- Percentual de post-mortem concluído em até 5 dias: ≥ 95%.
