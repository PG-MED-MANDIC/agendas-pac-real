# REGRA TEMPORÁRIA DE SLOTS — SÃO PAULO (SP)

> **TEMPORÁRIA. Só São Paulo.** Vale até o Raul atualizar a view `private.vw_checklist_operacional_real` (RDS).
> Independente de Campinas e Brasília (arquivos e interruptor próprios).

Criada em 24/11/2026. Fonte: HTML da coordenação "Regras de Agenda · PG Med São Paulo" (cópia em `regra-sao-paulo-capacidade/regras-agenda-sp_7 (1).html`; estudo em `ESTUDO_SAO_PAULO_FORMATO_CAMPINAS.md` na mesma pasta).

## Ligar / desligar / voltar
| Quero | Faço |
|---|---|
| Desligar | `pipeline/regras_slots_sp.json` -> `"ativa": false`, commit e push; rodar o Actions (grupo `agendas-pac-real,agendas_pgmed,coord_mandic_pgmed`) |
| Data de início | `"a_partir_de"` (hoje 2026-11-23) |
| Voltar o código | tag `backup-antes-regra-sp-20261124` ou `pipeline/transform_slots_ANTES_regra_sp.py.bak`; apagar `regra_slots_sp.py` e `regras_slots_sp.json` |
| Quando o Raul atualizar | desligar, conferir, apagar módulo + json + este arquivo + as 3 linhas em `transform_slots._slots_do_rds` |

## A regra
**Total = regulares novos + buffer + extras** (buffer e extras do Raul não mudam).
- **Janela A (turma 8h–18h):** 7 horários de 60 min. **Janela B (10h–20h):** 6 horários (12h, 14h, 15h, 16h, 17h, 18h). B = turmas listadas em `turmas_janela_B_10h_20h` (inferidas pelo 1º horário na ConsultaJá); turma fora da lista (inclusive futuras) = A.
- Clínicas (pac x horários A/B): Derm Cirúrgica 3 (21/18); Oftalmologia 4 (28/24); Pediatria 3 (21/18); Psiquiatria T2 e T5 3 (21/18), T3 5 (35/30); Psiq. Infantil 3 (18); Tricologia 3 (21/18). Fixos: Endocrinologia **só T5** 18; Neuropediatria 13; Nutrologia 9.
- Dermatologia (turmas "Dermatologia SP Tn"): 3 pac, minutos úteis (A 420 / B 360) ÷ duração do módulo. 60 min: M2–M7, M9, M11, M13, M14, M17; 90 min: M8, M10, M15, M16, M18, M19; **45 min: M12**. M1 e M20 sem regra.
- **Ficam como o Raul traz (decisão 24/11):** Dermatologia One, Psiquiatria T4/T6 e Endocrinologia T2/T3/T4/T6/T7/T8 (não estão no HTML), Derm M1/M20.

## Efeito (RDS de 24/11, práticas de 23/11 em diante)
SP **8.793 -> 10.851 (+23%)**, 381 práticas ajustadas. Derm +914, Endo +18, Oftalmo +756, Psiq +319, Nutro +39, Psiq Inf +12, Tricologia +27, Neuropediatria −3, Pediatria −24.

## Pendências
- **M12 (45 min) e M16 (90 min): "a confirmar" no HTML** — aplicados como está; reconfirmar com a coordenação.
- Turmas B inferidas pela ConsultaJá; confirmar com a coordenação, principalmente Derm T17–T24 e Cirúrgica T02.
- Endocrinologia T2/T3/T4/T6/T7/T8: se a coordenação mandar a regra, incluir (estudo antigo previa +191).
