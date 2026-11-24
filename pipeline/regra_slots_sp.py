"""REGRA TEMPORARIA de slots para Sao Paulo (SP) -- ver REGRA_TEMPORARIA_SLOTS_SAO_PAULO.md.

Independente das regras de Campinas e Brasilia. Por cima da view do RDS (checklist_real.json):
muda so os slots REGULARES; buffer e extras do Raul seguem somando. Linhas sem regra no HTML
(Derm One, Endo exceto T5, Psiquiatria T4/T6, Derm M1/M20) ficam como o Raul traz.
Desligar: "ativa": false em regras_slots_sp.json. Quando o Raul atualizar a view, apagar este modulo.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("regras_slots_sp.json")
_RE_MOD = re.compile(r"^\s*M\s*0*(\d+)\b", re.I)


def _n(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def _carregar() -> dict | None:
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not cfg.get("ativa"):
        return None
    cfg["_B"] = {_n(t) for t in cfg.get("turmas_janela_B_10h_20h", [])}
    return cfg


def regulares_novos(r: dict, cfg: dict) -> int | None:
    """Regulares pela regra nova, ou None se a linha fica como o Raul traz."""
    esp = str(r.get("especialidade") or "").strip()
    turma = _n(r.get("turma"))
    jan_b = turma in cfg["_B"]
    if esp == "Dermatologia":
        if "cirurgica" in turma:
            esp = "Dermatologia Cirurgica"
        else:
            d = cfg["dermatologia"]
            if any(_n(x) in turma for x in d["curso_exclui"]):
                return None
            mm = _RE_MOD.match(str(r.get("modulo") or ""))
            if not mm or int(mm.group(1)) in d["sem_regra_modulos"]:
                return None
            dur = d["duracao_por_modulo"].get(mm.group(1))
            if not dur:
                return None
            mins = d["minutos_uteis_B" if jan_b else "minutos_uteis_A"]
            return (mins // dur) * int(d["pac_por_horario"])
    for c in cfg["clinicas"]:
        if c["especialidade"] != esp:
            continue
        if "turmas" in c and turma not in {_n(t) for t in c["turmas"]}:
            continue
        if "curso_contem" in c and _n(c["curso_contem"]) not in turma:
            continue
        if "reg_dia_fixo" in c:
            return int(c["reg_dia_fixo"])
        return int(c["pac"]) * int(c["horarios_B" if jan_b else "horarios_A"])
    return None


def aplicar(linhas: list[dict], warnings: list[str]) -> list[dict]:
    """Devolve as linhas com total_real ajustado nas de SP (copia; nao altera o json original)."""
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
        f"ATENCAO -- REGRA TEMPORARIA DE SLOTS SAO PAULO ATIVA (regras_slots_sp.json): {n} praticas de SP ajustadas, "
        f"{antes} -> {depois} slots. Desligar quando o RDS do Raul for atualizado."
    )
    return saida
