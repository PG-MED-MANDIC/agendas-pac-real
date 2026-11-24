# REGRA TEMPORÁRIA DE SLOTS — BRASÍLIA (BSB)

> **TEMPORÁRIA. Só Brasília.** Vale até o Raul atualizar a view `private.vw_checklist_operacional_real` (RDS).
> Quando ele atualizar: desligar (abaixo) e voltar a ler o dado dele puro, igual à regra de Campinas.
> **Independente da regra de Campinas** (`REGRA_TEMPORARIA_SLOTS_CAMPINAS.md`): arquivos, interruptor e tag de backup separados. SP e ONL não mudam.

Criada em 23/11/2026. Fonte da regra: HTML da coordenação "Regras de Agenda · PG Med Brasília" (cópia local em `regra-brasilia-capacidade/regras_agenda_bsb.html`; regra original = banco de produção da Pós-Médica de 09/11/2026; sugestões replicadas da revisão de Campinas).

## Como ligar / desligar / voltar atrás
| Quero | Faço |
|---|---|
| **Desligar rápido** (volta ao dado do Raul) | `pipeline/regras_slots_bsb.json` -> `"ativa": false`, commit e push |
| Ligar | `"ativa": true` |
| Mudar a data de início | `"a_partir_de"` (hoje **2026-11-23**; `null` = todas as práticas) |
| Voltar o código como era antes | tag `backup-antes-regra-brasilia-20261123` (repos `agendas-pac-real` e `coord_mandic_pgmed`) ou o arquivo `pipeline/transform_slots_ANTES_regra_brasilia.py.bak`; apagar `regra_slots_bsb.py`/`regras_slots_bsb.json` |
| Quando o Raul atualizar | desligar, conferir que o RDS já traz as durações/pacientes abaixo, apagar módulo + json + este arquivo + as 3 linhas em `transform_slots._slots_do_rds` |

## PASSO A PASSO — depois de trocar true -> false, fazer valer
1. Trocar `"ativa": true` por `false` em `pipeline/regras_slots_bsb.json` (repo `PG-MED-MANDIC/agendas-pac-real`) e fazer commit.
2. Rodar o Actions: repo `automacao-dashboard` > Actions > "Atualizar dashboards NPS-PACIENTE" > Run workflow > grupo **`agendas-pac-real,agendas_pgmed,coord_mandic_pgmed`**. Atalho: n8n `RDDWtJw1m7cuhuTn`, executar o gatilho **"Diario 11:00 BRT"**. Sem rodar na mão, vale na próxima rodada automática (~06:17 e ~11:23 BRT).
3. A rodada leva alguns minutos. Conferir no log que **não** aparece "ATENCAO -- REGRA TEMPORARIA DE SLOTS BRASILIA ATIVA".

## Onde está no código
`pipeline/regra_slots_bsb.py` + `pipeline/regras_slots_bsb.json`; chamada em `transform_slots._slots_do_rds` logo depois da de Campinas. Vale também no `coord_mandic_pgmed` (mesmo `transform_slots`). `checklist_real.json` nunca é alterado.

## A regra
**Total da prática = regulares novos + buffer + extras.** Buffer e extras do Raul/ConsultaJá **não mudam**; só os regulares são recalculados (modo grade fixa).

### Janela e almoço (decididos pelo usuário em 23/11/2026)
- **Clínicas** (Endocrinologia, Oftalmologia, Psiquiatria): turma **08h–18h, almoço 12h–13h** (texto do HTML). Grade do dia: 10h, 11h; 13h, 14h, 15h, 16h = 6 horários x 3 pac = **18 por dia**.
- **Dermatologia**: **10h–18h com 1h de almoço = 7h úteis (420 min)** (janela vista no ConsultaJá: T1–T3 das 10:00 às 18:00; confirmado pelo usuário). O HTML não traz janela da Derm.

### Especialidades clínicas
| Especialidade | Regra original (HTML) | Regra nova | Regulares/dia |
|---|---|---|---|
| Endocrinologia | 60 min · 3 pac (**o RDS tem 90 min · 3 pac**) | 60 min · 3 pac | **18** |
| Oftalmologia | 60 min · 4 pac (RDS: T01 já 3 pac, só T02 em 4) | 60 min · 3 pac | **18** |
| Psiquiatria | 60 min · 4 pac (RDS: já 3 pac) | 60 min · 3 pac | **18** |

### Dermatologia — por módulo, sempre 3 pac
Regulares por dia = (420 min ÷ duração do módulo, para baixo) x 3. 60 min -> **21**; 45 min -> **27** (9 horários); 90 min -> **12** (4 horários).
| Duração | Módulos |
|---|---|
| 60 min | M2, M3 (era 90), M4, M5 (era 90), M6, M9, M13 (era 90), M14 (era 90), M17 |
| 45 min | M7, M11, M12 |
| 90 min | M8, M10, M15, M16, M18, M19 |
| sem regra (ficam como o Raul traz) | M1, M20 (teórico) |
Sem a exceção de 30 min do M9 que existe só em Campinas (T06/T08): em BSB o M9 é 60 min em todas as turmas. M16: aplicado 90 min · 3 pac conforme o HTML (o RDS tem 60 min · 2 pac).

## Efeito (RDS de 18/11, práticas de 23/11/2026 em diante)
| Especialidade | Slots hoje (Raul) | Regra | Variação |
|---|---|---|---|
| Dermatologia | 713 | 1.040 | +327 |
| Endocrinologia | 123 | 249 | +126 |
| Oftalmologia | 430 | 466 | +36 |
| Psiquiatria | 77 | 96 | +19 |
| **Brasília** | **1.343** | **1.851** | **+508 (+38%)** |
79 práticas ajustadas (M1/M20 ficam fora). Semana 23–28/11: Oftalmologia T2 (26, 27 e 28/11) 12 -> 18 slots/dia; Psiquiatria T1 (25/11) 37 -> 38. Campinas, SP e Online ficam iguais.

## Pontos para o usuário avaliar
1. O aumento é grande (+38%) porque a grade fixa abre vagas onde o RDS hoje abre menos (ex.: Endocrinologia hoje 90 min; Derm 21 regulares/dia onde o RDS traz menos).
2. Endo: o HTML dá "original 60 min", mas o RDS tem 90 min; aplicado 60 min conforme o HTML.
3. A janela da Derm (10h–18h) vem do ConsultaJá, não do HTML.
4. Buffer/extras continuam somando por cima da grade.
