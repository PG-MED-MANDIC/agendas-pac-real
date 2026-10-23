"""Agrega o DataFrame de agendamentos (ConsultaJá) nos 4 arrays embutidos em
../index.html: RAW (mês+dia), RAWD (dia), RAWH (hora), DAYCNT (dias
distintos por mês+semana). Ver pipeline/README.md para o significado de
cada campo.

Só usa as colunas Data/Horário de início/Status/Unidade/Curso/Turma --
Paciente/Celular/Profissional/Convênio (que a API também traz) nunca entram
no agregado.

RAW (2026-09-18, decisão do usuário): passou a ser por dia real ("d"), não
mais por "semana do mês" em faixas fixas de 7 dias -- a semana de calendário
(segunda a domingo) agora é calculada no próprio index.html a partir de "d"
(ver getMondayKey() lá), inclusive semanas "cortadas" entre 2 meses. RAWH e
DAYCNT continuam usando a faixa fixa antiga ("w", Sem1=01-07...Sem5=29-31)
-- elas alimentam só o simulador de recepcionistas (aba "Simulação"), que já
tinha um problema pré-existente e separado (o seletor daquela aba é rotulado
por dia da semana -- Segunda..Domingo -- mas filtra por esse "w" antigo, que
não é dia da semana; não foi tocado nesta mudança, ver PROGRESSO.md).
"""
from __future__ import annotations

import pandas as pd

REALIZADO_STATUSES = {"Compareceu", "Atendido"}
FALTA_STATUSES = {"Faltou"}
CANCELADO_STATUSES = {"Cancelado"}
AGENDADO_STATUSES = {"Agendado", "Confirmado"}

_COLUMNS = ["Data", "Horário de início", "Status", "Unidade", "Curso", "Turma"]


def _week_of_month(day: int) -> int:
    return min((day - 1) // 7 + 1, 5)


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    prep = df[_COLUMNS].copy()
    data = pd.to_datetime(prep["Data"], format="%d/%m/%Y")

    prep["u"] = prep["Unidade"]
    prep["c"] = prep["Curso"]
    prep["t"] = prep["Turma"].astype(str)  # Excel infere int quando a coluna só tem dígitos;
    # o dashboard espera string (ex.: "1"), como no formato original
    prep["m"] = data.dt.strftime("%Y-%m")
    prep["d"] = data.dt.strftime("%Y-%m-%d")
    prep["w"] = data.dt.day.map(_week_of_month)
    prep["h"] = pd.to_datetime(prep["Horário de início"], format="%H:%M", errors="coerce").dt.hour

    prep["r"] = prep["Status"].isin(REALIZADO_STATUSES)
    prep["f"] = prep["Status"].isin(FALTA_STATUSES)
    prep["x"] = prep["Status"].isin(CANCELADO_STATUSES)
    prep["a"] = prep["Status"].isin(AGENDADO_STATUSES)
    return prep


def build_raw(df: pd.DataFrame) -> list[dict]:
    prep = _prepare(df)
    grouped = (
        prep.groupby(["u", "m", "d", "c", "t"])[["r", "f", "x", "a"]]
        .sum()
        .reset_index()
        .sort_values(["u", "m", "d", "c", "t"])
    )
    return grouped.to_dict(orient="records")


def build_rawd(df: pd.DataFrame) -> list[dict]:
    prep = _prepare(df)
    grouped = (
        prep.groupby(["u", "d", "c", "t"])[["r", "f", "x", "a"]]
        .sum()
        .reset_index()
        .sort_values(["u", "d", "c", "t"])
    )
    return grouped.to_dict(orient="records")


def build_rawh(df: pd.DataFrame) -> list[dict]:
    """n = consultas ocorridas (realizado + falta) por hora -- cancelado e
    agendado/pendente não entram (confirmado com o texto da UI do card
    "Pacientes e Recepcionistas Necessários por Hora").
    """
    prep = _prepare(df)
    ocorridas = prep[(prep["r"] | prep["f"]) & prep["h"].notna()].copy()
    ocorridas["h"] = ocorridas["h"].astype(int)
    grouped = (
        ocorridas.groupby(["u", "m", "w", "h"])
        .size()
        .reset_index(name="n")
        .sort_values(["u", "m", "w", "h"])
    )
    return grouped.to_dict(orient="records")


def build_rawhd(df: pd.DataFrame) -> list[dict]:
    """Por unidade + DIA real ("d") + hora ("h"): n = consultas concluídas
    (Compareceu/Atendido); f = faltas; x = cancelados; a = agendados/confirmados
    ainda sem resultado. Alimenta o Solver da Recepção: só "n" entra nos cálculos
    de recepcionistas; f/x/a aparecem na visão "Dados reais".
    """
    prep = _prepare(df)
    com_hora = prep[prep["h"].notna()].copy()
    com_hora["h"] = com_hora["h"].astype(int)
    grouped = (
        com_hora.groupby(["u", "d", "h"])
        .agg(n=("r", "sum"), f=("f", "sum"), x=("x", "sum"), a=("a", "sum"))
        .reset_index()
        .sort_values(["u", "d", "h"])
    )
    for c in ("n", "f", "x", "a"):
        grouped[c] = grouped[c].astype(int)
    grouped = grouped[(grouped["n"] + grouped["f"] + grouped["x"] + grouped["a"]) > 0]
    return grouped.to_dict(orient="records")


def build_daysd(df: pd.DataFrame) -> list[dict]:
    """Dias (unidade + data) com pelo menos 1 consulta concluída -- o divisor das
    médias do Solver (dias sem nenhum paciente concluído, inclusive futuros, não entram).
    """
    prep = _prepare(df)
    grouped = prep[prep["r"]][["u", "d"]].drop_duplicates().sort_values(["u", "d"])
    return grouped.to_dict(orient="records")


def build_futhd(df: pd.DataFrame, a_partir_de: str) -> list[dict]:
    """Agendados/confirmados por unidade + dia + hora de `a_partir_de` (AAAA-MM-DD)
    em diante. Alimenta o "Planejar equipe" (só contagens, nenhum dado de paciente).
    """
    prep = _prepare(df)
    fut = prep[prep["a"] & prep["h"].notna() & (prep["d"] >= a_partir_de)].copy()
    fut["h"] = fut["h"].astype(int)
    grouped = (
        fut.groupby(["u", "d", "h"])
        .size()
        .reset_index(name="n")
        .sort_values(["u", "d", "h"])
    )
    return grouped.to_dict(orient="records")


def build_daycnt(df: pd.DataFrame) -> list[dict]:
    prep = _prepare(df)
    grouped = (
        prep.groupby(["u", "m", "w"])["d"]
        .nunique()
        .reset_index(name="d")
        .sort_values(["u", "m", "w"])
    )
    return grouped.to_dict(orient="records")
