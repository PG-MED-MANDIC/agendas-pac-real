# Pipeline de atualização de dados (Python)

Scripts para regenerar as constantes de dados em `../index.html`: `RAW`,
`RAWD`, `RAWH` e `DAYCNT` (dashboard "Triagem"), a partir da API da
ConsultaJá -- **mesma conta/token já usados no pipeline do NPS-PACIENTE**.
Também regenera `SLOTS` (capacidade planejada, aba "Slots x Realizado"),
a partir de `dados-fonte/checklist-captacao.xlsx`.

## Instalação

```
cd pipeline
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha `CONSULTAJA_TOKEN` com o mesmo
token já usado no pipeline do NPS-PACIENTE. **Nunca** commite o `.env`.

## Uso

Um comando só (busca na API + recalcula os 5 arrays + regrava `index.html`):

```
python atualizar_tudo.py
```

Ou duplo clique em `Atualizar Dashboard.bat`, na raiz do projeto. Nenhum dos
dois faz `git add`/`commit`/`push` -- isso continua manual de propósito,
pra sempre ter uma revisão antes de publicar no repositório público:

```
git status
git diff -- index.html
git add index.html
git commit -m "Atualiza dados do dashboard"
git push
```

Passos individuais (equivalente ao que `atualizar_tudo.py` encadeia):

```
python fetch_consultaja.py --dry-run
python fetch_consultaja.py
```

Isso salva a planilha em `../dados-fonte/Base_Consulta_JaAA_MM_DD.xlsx`
(fora do controle de versão -- nunca é hospedada). **Atenção**: o nome do
arquivo é baseado na data de hoje e é sobrescrito sem aviso se rodar de novo
no mesmo dia.

## O que cada campo significa

- **`RAW`**: por unidade (`u`) + mês (`m`, `AAAA-MM`) + semana do mês
  (`w`, 1-5) + curso/especialidade (`c`) + turma (`t`) → contagem de
  Realizado (`r`) / Falta (`f`) / Cancelado (`x`) / Agendado-pendente (`a`).
- **`RAWD`**: igual, mas por dia (`d`, `AAAA-MM-DD`) em vez de mês/semana.
- **`RAWH`**: por unidade+mês+semana+hora (`h`, 0-23) → `n` = consultas
  **ocorridas** (realizado + falta; cancelado e agendado não entram aqui).
- **`DAYCNT`**: por unidade+mês+semana → `d` = quantidade de dias distintos
  com pelo menos um registro (usado pra calcular médias diárias no
  dashboard).
- **`SLOTS`**: por unidade (`u`, nome por extenso, ex. "Campinas") + data
  (`d`, `AAAA-MM-DD`) + curso (`c`) + turma (`t`, string) → `s` = slots
  previstos (capacidade planejada) e `md` = módulo. Usado só pela aba
  "Slots x Realizado" (o próprio `index.html` cruza `SLOTS` com `RAWD` em
  `SLOTSX`, pela chave `u|d|c|t`, pra comparar capacidade com o que a
  ConsultaJá registrou). Ver "De onde vem SLOTS" abaixo.

**Mapeamento de status** (`transform_triagem.py`): Realizado = `Compareceu`
ou `Atendido`; Falta = `Faltou`; Cancelado = `Cancelado`;
Agendado/Pendente = `Agendado` ou `Confirmado`.

**Semana do mês (`w`)**: faixas fixas de 7 dias, documentadas na própria UI
do dashboard (Sem1=01-07, Sem2=08-14, Sem3=15-21, Sem4=22-28, Sem5=29-31).
Os dados antigos (colados manualmente, antes deste pipeline existir) tinham
valores de `w` inconsistentes com essa mesma UI -- resquício de um processo
externo perdido; este pipeline usa só o esquema documentado, então a
primeira execução pode mudar levemente a distribuição por semana em relação
ao que estava publicado antes.

## "Última atualização" (decisão de 2026-09-17)

O `<div id="last-update">` do `index.html` só avança quando **os dois**
dados-fonte foram conferidos com sucesso na mesma rodada de
`atualizar_tudo.py`: a base da ConsultaJá (passo 1) **e** a
checklist-captacao/`SLOTS` (passo 3). Se a checklist-captacao não for
encontrada (ou falhar), RAW/RAWD/RAWH/DAYCNT ainda são regravados
normalmente, mas o indicador **não** muda de valor -- ele existe pra dizer
"os dois dados-fonte foram checados agora", não só "o script rodou" ou só
"a ConsultaJá foi baixada". `atualizar_tudo.py` avisa explicitamente no
relatório quando isso acontece.

## De onde vem SLOTS (decisão de 2026-09-17)

Antes deste módulo (`transform_slots.py`), `SLOTS` era um array colado à
mão dentro do `index.html` -- nunca foi regravado pelo pipeline, então
parou em 30/09/2026 (última vez que alguém repetiu o processo manual) e a
aba "Slots x Realizado" ficava zerada pra qualquer data depois dessa.

Agora `SLOTS` vem de `dados-fonte/checklist-captacao.xlsx` -- o **mesmo
arquivo** usado pelo pipeline de `agendas_pgmed` (baixado manualmente do
SharePoint, nunca por este pipeline; se não existir em `dados-fonte/`,
este pipeline só avisa e deixa o `SLOTS` já publicado como está, em vez de
falhar tudo).

A checklist guarda a turma como `"<curso> <sigla da unidade> T<número>"`
(ex. `Dermatologia Cirurgica SP T01`); a ConsultaJá guarda Unidade por
extenso e Curso/Turma em colunas separadas. Pra que a chave `u|d|c|t` que
o `index.html` já monta (`SLOTSX = SLOTS.map(...)`) encontre os
registros certos dentro de `RAWD`, `transform_slots.py` emite `c` com a
**mesma grafia de "Curso" que já aparece na ConsultaJá** para aquela
combinação curso+unidade+turma (a ConsultaJá tem inconsistência de
acentuação em Curso -- ex. "Dermatologia Cirurgica" e "Dermatologia
Cirúrgica" convivem na mesma planilha). Se uma turma da checklist ainda
não tem nenhum registro na ConsultaJá (turma nova, nome digitado
diferente etc.), o pipeline usa o texto da própria checklist e avisa no
relatório -- nunca descarta a linha silenciosamente.

## O que o pipeline garante

- **Anonimização por lista de permissão**: só `Data`/`Horário de
  início`/`Status`/`Unidade`/`Curso`/`Turma` são lidos da planilha —
  `Paciente`/`Celular`/`Profissional`/`Convênio`/`Tipo de
  agendamento`/`Formato` (que a API também traz) nunca entram no agregado
  gravado em `index.html`.
- **Regravação cirúrgica** (`render_index.py`): `upsert_all()` substitui só
  as 4 linhas `var RAW`/`RAWD`/`RAWH`/`DAYCNT` -- o resto do arquivo (HTML,
  CSS, lógica de gráficos/filtros) não é tocado.
- **Sem automação não supervisionada**: assim como no NPS-PACIENTE, nada
  aqui roda sozinho (sem agendador/cron) -- cada execução da API traz
  nome/celular de paciente, então cada execução é uma decisão de quem está
  rodando. O arquivo em `dados-fonte/` nunca é versionado nem hospedado.
