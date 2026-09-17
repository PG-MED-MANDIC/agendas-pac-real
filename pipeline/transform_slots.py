"""Lê dados-fonte/checklist-captacao.xlsx (mesma planilha usada pelo
pipeline de agendas_pgmed -- ver config.py) e monta o array `SLOTS` que
../index.html usa na aba "Slots x Realizado": capacidade planejada
(slots previstos) por unidade+curso+turma+data.

Decisão de 2026-09-17: antes deste módulo, `SLOTS` era um array colado à
mão dentro do index.html, nunca atualizado pelo pipeline -- parou em
30/09/2026 porque ninguém repetiu o processo manual depois disso. Este
módulo automatiza a mesma coisa, na mesma forma que o array já tinha,
pra alimentar sem mudar nada no JS que já consome `SLOTS`
(`SLOTSX = SLOTS.map(...)` dentro de index.html).

Casamento de nomes: a checklist guarda a turma como
"<curso> <sigla da unidade> T<número>" (ex.: "Dermatologia Cirurgica SP
T01"); a ConsultaJá guarda Unidade por extenso e Curso/Turma em colunas
separadas. Pra que a chave `u|d|c|t` que o JS monta encontre os
registros certos dentro de RAWD_IDX, o `c` emitido aqui usa a MESMA
grafia de "Curso" já vista na ConsultaJá para aquela combinação
curso+unidade+turma (a ConsultaJá tem inconsistência de acentuação em
Curso -- ex. "Dermatologia Cirurgica" e "Dermatologia Cirúrgica" convivem
na mesma planilha, ver attendance_consultaja.py do pipeline vizinho). Se
uma turma da checklist ainda não tem nenhum registro na ConsultaJá (turma
nova, nome digitado diferente etc.), cai de volta pro texto da própria
checklist e avisa -- nunca descarta a linha silenciosamente.
"""
from __future__ import annotations

import math
import re
import unicodedata
from pathlib import Path

import pandas as pd

UNIDADE_MAP = {"BSB": "Brasília", "CPS": "Campinas", "SP": "São Paulo", "ONL": "Online"}

_TURMA_RE = re.compile(r"^(.+)\s(BSB|CPS|SP|ONL)\sT0*(\d+)$")

TURMAS_IGNORADAS = {"", "total do mês", "total do mes", "turma"}

_ALIASES = {
    "turma": ["turma"],
    "modulo": ["modulo"],
    "data": ["data da pratica", "data"],
    "slots_previstos": ["slots da pratica", "slots previstos"],
}
CAMPOS_OBRIGATORIOS = ("turma", "data", "slots_previstos")


def _norm(value) -> str:
    s = str(value if value is not None else "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _find_col(headers_norm: list[str], aliases: list[str]) -> int:
    for alias in aliases:
        for i, h in enumerate(headers_norm):
            if alias in h:
                return i
    return -1


def _find_header_row(sheet_df: pd.DataFrame) -> int | None:
    for i in range(min(10, len(sheet_df))):
        values = [str(c).strip() for c in sheet_df.iloc[i].tolist()]
        if "Turma" in values:
            return i
    return None


def _to_date_iso(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    d = pd.to_datetime(value, dayfirst=True, errors="coerce")
    if pd.isna(d):
        return ""
    return d.strftime("%Y-%m-%d")


def _to_int(value) -> int:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0
    try:
        return round(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def _parse_turma(turma: str) -> tuple[str, str, int] | None:
    m = _TURMA_RE.match(turma.strip())
    if not m:
        return None
    curso, unidade_code, num = m.groups()
    return curso.strip(), unidade_code, int(num)


def _curso_lookup(df_consultaja: pd.DataFrame) -> dict[tuple[str, str, int], str]:
    """(curso_norm, unidade_full, turma_num) -> grafia de "Curso" mais
    frequente na ConsultaJá para essa combinação."""
    counts: dict[tuple[str, str, int], dict[str, int]] = {}
    for row in df_consultaja.itertuples(index=False):
        try:
            turma_num = int(row.Turma)
        except (TypeError, ValueError):
            continue
        key = (_norm(row.Curso), str(row.Unidade).strip(), turma_num)
        bucket = counts.setdefault(key, {})
        bucket[row.Curso] = bucket.get(row.Curso, 0) + 1
    return {key: max(bucket.items(), key=lambda kv: kv[1])[0] for key, bucket in counts.items()}


def build_slots(
    xlsx_path: Path, df_consultaja: pd.DataFrame, warnings: list[str] | None = None
) -> list[dict]:
    if warnings is None:
        warnings = []

    curso_por_combo = _curso_lookup(df_consultaja)
    warned_turmas: set[str] = set()
    agg: dict[tuple[str, str, str, str], dict] = {}

    with pd.ExcelFile(xlsx_path) as xls:
        sheet_names = [s for s in xls.sheet_names if s.startswith("Ocupação")]
        if not sheet_names:
            raise RuntimeError('Nenhuma aba iniciada com "Ocupação" encontrada na planilha.')

        for sheet in sheet_names:
            raw = xls.parse(sheet, header=None, dtype=object)
            header_row = _find_header_row(raw)
            if header_row is None:
                warnings.append(f'Aba "{sheet}" pulada -- nenhuma linha de cabeçalho com "Turma" encontrada.')
                continue

            headers_norm = [_norm(c) for c in raw.iloc[header_row].tolist()]
            col = {key: _find_col(headers_norm, aliases) for key, aliases in _ALIASES.items()}
            faltando = [k for k in CAMPOS_OBRIGATORIOS if col[k] < 0]
            if faltando:
                warnings.append(f'Aba "{sheet}" pulada pro cálculo de Slots -- colunas não encontradas: {", ".join(faltando)}.')
                continue

            for i in range(header_row + 1, len(raw)):
                r = raw.iloc[i].tolist()
                turma_full = str(r[col["turma"]] or "").strip()
                if _norm(turma_full) in TURMAS_IGNORADAS:
                    continue

                data_iso = _to_date_iso(r[col["data"]])
                if not data_iso:
                    continue

                parsed = _parse_turma(turma_full)
                if parsed is None:
                    if turma_full not in warned_turmas:
                        warned_turmas.add(turma_full)
                        warnings.append(
                            f'Turma "{turma_full}": nome fora do padrão "<curso> <sigla> T<número>" -- não entra em Slots.'
                        )
                    continue

                curso_raw, unidade_code, turma_num = parsed
                unidade_full = UNIDADE_MAP[unidade_code]
                combo = (_norm(curso_raw), unidade_full, turma_num)
                curso_final = curso_por_combo.get(combo)
                if curso_final is None:
                    if turma_full not in warned_turmas:
                        warned_turmas.add(turma_full)
                        warnings.append(
                            f'Turma "{turma_full}": nenhum registro dessa combinação curso/unidade/turma na ConsultaJá ainda -- '
                            "usando o nome de curso da própria checklist (pode não casar com Realizado/Falta/Cancelado até a "
                            "ConsultaJá ter algum agendamento registrado)."
                        )
                    curso_final = curso_raw

                slots = _to_int(r[col["slots_previstos"]])
                modulo = str(r[col["modulo"]] or "").strip() if col["modulo"] >= 0 else ""

                key = (unidade_full, data_iso, curso_final, str(turma_num))
                if key not in agg:
                    agg[key] = {"u": unidade_full, "d": data_iso, "c": curso_final, "t": str(turma_num), "s": 0, "md": modulo}
                agg[key]["s"] += slots

    if not agg:
        raise RuntimeError("Nenhuma linha de Slots válida encontrada em nenhuma aba.")

    return sorted(agg.values(), key=lambda d: (d["u"], d["d"], d["c"], d["t"]))
