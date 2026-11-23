# REGRA TEMPORÁRIA DE SLOTS — CAMPINAS (CPS)

> **TEMPORÁRIA. Só Campinas.** Vale até o Raul atualizar a view `private.vw_checklist_operacional_real` (RDS).
> Quando ele atualizar: desligar (abaixo) e voltar a ler o dado dele puro. SP, BSB e ONL não mudam.
> Regras temporárias de Brasília ficarão em outro arquivo: `REGRA_TEMPORARIA_SLOTS_BRASILIA.md`.

Criada em 23/11/2026. Estudo de origem: `regra-campinas-capacidade/` (HTML da coordenação `regras_agenda_cps_2 (1).html`, estudos de Endocrinologia T01 e Dermatologia T09).

## Como ligar / desligar / voltar atrás
| Quero | Faço |
|---|---|
| **Desligar rápido** (volta ao dado do Raul, sem mexer em código) | `pipeline/regras_slots_cps.json` -> `"ativa": false`, commit e push |
| Ligar | `"ativa": true` |
| Valer só de uma data em diante | `"a_partir_de": "2026-11-23"` (**hoje = 2026-11-23**; `null` = todas, inclusive passadas) |
| Voltar o código como era antes | `git checkout backup-antes-regra-campinas-20261123 -- pipeline/transform_slots.py` e apagar `regra_slots_cps.py`/`regras_slots_cps.json` (tag nos repos `agendas-pac-real` e `coord_mandic_pgmed`; cópia do arquivo original: `pipeline/transform_slots_ORIGINAL_antes_regra_campinas.py.bak`) |
| Quando o Raul atualizar | desligar, conferir que o RDS já traz as durações/pacientes novos, apagar módulo + json + este arquivo + a chamada em `transform_slots._slots_do_rds` |

`checklist_real.json` (RDS) **nunca é alterado**: a regra só recalcula na memória, na hora de montar os slots. O log da rodada traz o aviso "ATENCAO -- REGRA TEMPORARIA DE SLOTS CAMPINAS ATIVA ... N práticas, X -> Y slots".

## PASSO A PASSO — voltar atrás (true -> false) e fazer valer
1. Abrir `pipeline/regras_slots_cps.json` (no GitHub: repo `PG-MED-MANDIC/agendas-pac-real` > pipeline > regras_slots_cps.json > lápis) e trocar `"ativa": true` por `"ativa": false`. Commit.
2. Fazer a rodada rodar: GitHub > repo **`automacao-dashboard`** > Actions > workflow de atualização > **Run workflow** > grupo **`agendas-pac-real,agendas_pgmed,coord_mandic_pgmed`** (a regra só afeta agendas-pac-real e coord_mandic_pgmed). Se não rodar na mão, vale sozinho na próxima rodada automática (~06:17 e ~11:23 BRT; a das 08:51 é só csat).
   Atalho: n8n, workflow `RDDWtJw1m7cuhuTn` (gatilhos 06:00/08:45/11:00) — o das 08:45 é só csat, então prefira o botão do GitHub. O token local dá 403.
3. Conferir no log da rodada: **não** deve aparecer "ATENCAO -- REGRA TEMPORARIA DE SLOTS CAMPINAS ATIVA". Conferir no dash: Derm CPS T09 em 26/11 volta a 32 slots (com a regra: 28).

## Onde está no código
- `pipeline/regra_slots_cps.py` (a regra) + `pipeline/regras_slots_cps.json` (números e interruptor).
- Chamada única em `pipeline/transform_slots.py`, função `_slots_do_rds`. O `coord_mandic_pgmed` usa o mesmo `transform_slots` (via `agendas-pac-real`), então **o ajuste vale nos dois dashboards**.

## A regra
**Total da prática = regulares novos + buffer + extras.** Buffer e extras (ConsultaJá) são os do Raul, não mudam. Só os regulares são recalculados.

### "Clínicas" = todas as especialidades menos Dermatologia (termo do HTML "Especialidades clínicas"; NÃO é a unidade Online) — grade fixa por dia (turma 8h–18h, almoço 12h–13h)
| Especialidade | Duração · pac | Regulares por dia |
|---|---|---|
| Endocrinologia | 60 min · 3 pac | **18** (10h, 11h; 13h–16h) |
| Neuropediatria | 60 min · 3 pac | **13** (10h x3 + 10h30 x1; 13h, 14h30, 16h) |
| Nutrologia | 90 min · 3 pac | **9** (13h, 14h30, 16h) |
| Oftalmologia | 60 min · 3 pac | **18** |
| Pediatria | 60 min · 2 pac | **14** (tarde a confirmar) |
| Psiquiatria | 60 min · 3 pac | **18** (horários a confirmar) |
| Psiquiatria T2 | 60 min · 2 pac | **12** |
Psiquiatria Infantil e Tricologia: sem regra (sem turma em CPS).

### Dermatologia — janela real da turma + duração do módulo
- Janela (ConsultaJá, confirmada pelo usuário): **T03–T07 10:00–17:30 (6h30 úteis); T08–T10 12:00–19:00 (6h úteis)**; 1h de almoço.
- Regulares por dia = (minutos úteis ÷ duração do módulo, para baixo) x 3 pac. 60 min -> 18; 45 -> 24; 90 -> 12; 30 -> 36 (T08) ou 39 (T06).
- Duração por módulo (HTML): M2, M3, M4, M5, M6, M7, M9, M11, M13, M14, M17 = 60 min; M8, M10, M15, M16, M18, M19 = 90 min; M12 = 45 min; **M9 = 30 min só nas turmas T06 e T08**. **M1 e M20 sem regra** (ficam como o Raul traz).

## Efeito (calculado em 23/11/2026 sobre o RDS de 18/11)
| Especialidade | Slots hoje (Raul) | Regra | Variação |
|---|---|---|---|
| Dermatologia | 3.053 | 3.247 | +194 |
| Endocrinologia | 1.210 | 1.415 | +205 |
| Neuropediatria | 314 | 494 | +180 |
| Nutrologia | 68 | 93 | +25 |
| Oftalmologia | 319 | 377 | +58 |
| Pediatria | 487 | 376 | −111 |
| Psiquiatria | 981 | 1.185 | +204 |
| **Campinas** | **6.432** | **7.187** | **+755 (+12%)** |

Semana 23–28/11: 393 -> 317 slots (−76; Endo T01 61, Derm T09 86, Pediatria T06 38).

## Pontos em aberto (decisões do usuário)
1. **Modo das clínicas = grade fixa (confirmado em 23/11)** (abre a grade cheia onde o RDS abre menos). Alternativa "teto" (nunca acima do atual) daria total menor. Decisão registrada como "grade fixa" por seguirmos os estudos; confirmar.
2. **Buffer/extras seguem somando** por cima da grade (confirmado pelo usuário em 23/11). Sem eles Endocrinologia T01, Pediatria T06 e Psiquiatria T05 estouram menos.
3. **Decidido (23/11/2026): vale só de 23/11/2026 em diante** (`a_partir_de`). Práticas anteriores ficam como o Raul traz.
4. "A confirmar" do HTML: Pediatria tarde, Psiquiatria horários, Derm M12 e M16.
5. Janela da T10 (a maioria dos dias termina 18h; usado 19h).
6. Dias em que o ConsultaJá tem mais agendados que vagas passam a aparecer >100% (roxo).
