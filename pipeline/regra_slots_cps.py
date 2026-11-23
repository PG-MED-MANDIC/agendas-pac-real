"""REGRA TEMPORARIA de slots para Campinas (CPS) -- ver REGRA_TEMPORARIA_SLOTS_CAMPINAS.md.

Por cima da view do RDS (checklist_real.json). Muda so os slots REGULARES; buffer e
extras do Raul seguem somando. Desligar: "ativa": false em regras_slots_cps.json
(ou apagar a chamada em transform_slots._slots_do_rds). Quando o Raul atualizar a
view, desligar e apagar este modulo.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("regras_slots_cps.json")
_RE_MOD = re.compile(r"^\s*M\s*0*(\d+)\b", re.I)
_RE_TURMA = re.compile(r"\sT0*(\d+)\s*$")


def _carregar() -> dict | None:
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return cfg if cfg.get("ativa") else None


def regulares_novos(r: dict, cfg: dict) -> int | None:
    """Regulares pela regra nova para uma linha do RDS, ou None se a linha fica como o Raul traz."""
    esp = str(r.get("especialidade") or "").strip()
    m = _RE_TURMA.search(str(r.get("turma") or ""))
    turma = m.group(1) if m else ""
    if esp in cfg["clinicas"]:
        c = cfg["clinicas"][esp]
        return int(c.get("por_turma", {}).get(turma, c["reg_dia"]))
    if esp == "Dermatologia":
        d = cfg["dermatologia"]
        mm = _RE_MOD.match(str(r.get("modulo") or ""))
        if not mm or int(mm.group(1)) in d["sem_regra_modulos"]:
            return None
        mod = mm.group(1)
        dur = d["duracao_excecao"].get(mod, {}).get(turma) or d["duracao_por_modulo"].get(mod)
        util = d["minutos_uteis_por_turma"].get(turma)
        if not dur or not util:
            return None
        return int(util // dur) * int(d["pac_por_horario"])
    return None


def aplicar(linhas: list[dict], warnings: list[str]) -> list[dict]:
    """Devolve as linhas com total_real ajustado nas de CPS (copia; nao altera o json original)."""
    cfg = _carregar()
    if cfg is None:
        return linhas
    ini = cfg.get("a_partir_de") or ""
    saida, n, antes, depois = [], 0, 0, 0
    for r in linhas:
        if r.get("unidade") != cfg["unidade"] or str(r.get("data_pratica") or "")[:10] < ini:
            saida.append(r)
            continue
        reg = regulares_novos(r, cfg)
        if reg is None:
            saida.append(r)
            continue
        novo = dict(r)
        novo["total_real"] = reg + int(r.get("buf_reais") or 0) + int(r.get("extras_cj") or 0)
        n += 1
        antes += int(r.get("total_real") or 0)
        depois += novo["total_real"]
        saida.append(novo)
    warnings.append(
        f"ATENCAO -- REGRA TEMPORARIA DE SLOTS CAMPINAS ATIVA (regras_slots_cps.json): {n} praticas de CPS ajustadas, "
        f"{antes} -> {depois} slots. Desligar quando o RDS do Raul for atualizado."
    )
    return saida
