# Pipeline de atualização de dados (Python)

Scripts para regenerar as constantes de dados em `../index.html`: `RAW`,
`RAWD`, `RAWH` e `DAYCNT` (dashboard "Triagem"), a partir da API da
ConsultaJá -- **mesma conta/token já usados no pipeline do NPS-PACIENTE**.

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

Um comando só (busca na API + recalcula os 4 arrays + regrava `index.html`):

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

Não há campo de "última atualização" embutido no `index.html` -- não
precisa tratar isso aqui (diferente do `CONSULTAJA_END_DATE` dinâmico do
NPS-PACIENTE).

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
