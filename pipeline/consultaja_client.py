"""Cliente para a API da ConsultaJá -- busca agendas e agendamentos e
consolida em um DataFrame único, pronto para salvar em dados-fonte/.

Ao contrário de indecx_client.py, este cliente parte de um script que já
funcionava contra a API real (endpoint, autenticação e paginação vieram de
um script rodado manualmente via Spyder) -- não é um template especulativo.

Ainda assim, só deve ser chamado manualmente (via fetch_consultaja.py).
Nenhuma automação não-supervisionada (agendador/cron) foi configurada: cada
resposta da API traz nome e celular de paciente, então cada execução deve
continuar sendo uma decisão de quem está rodando, não um job que roda
sozinho.
"""
from __future__ import annotations

import re
import time
from datetime import datetime

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import ConsultaJaConfig

BASE_URL = "https://api.consultaja.com"
PAGE_LIMIT = 100
MAX_PAGES = 500  # trava de segurança: nunca pagina indefinidamente por bug na API
REQUEST_TIMEOUT = (15, 90)  # (connect_timeout, read_timeout) em segundos

# Siglas de unidade (extraídas do nome da agenda) -> nome completo.
UNIDADE_MAP = {
    "CPS": "Campinas",
    "SP": "São Paulo",
    "BSB": "Brasília",
    "- SP": "São Paulo",
}

# Corrige nomes de curso abreviados pela ConsultaJá.
CURSO_MAP = {
    "DERMATO ONE": "Dermatologia One",
}

STATUS_MAP = {
    "SCHEDULED": "Agendado",
    "CONFIRMED": "Confirmado",
    "CANCELED": "Cancelado",
    "MISSED": "Faltou",
    "SHOWEDUP": "Compareceu",
    "ATTENDED": "Atendido",
}


class ConsultaJaConfigurationError(RuntimeError):
    """Falta CONSULTAJA_TOKEN no .env, ou o token foi rejeitado pela API."""


def _make_session() -> requests.Session:
    """Sessão com retry automático para erros de conexão e 5xx (backoff:
    1s, 2s, 4s, 8s entre tentativas).
    """
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _normalize_status(raw: str) -> str:
    if raw.startswith("RESCHEDULED_"):
        raw = raw[len("RESCHEDULED_"):]
    return STATUS_MAP.get(raw, raw)


def _parse_agenda_name(name: str) -> tuple[str, str, str]:
    """Extrai Curso, Turma e Unidade do nome da agenda.

    Regra: o token que casa /T\\d+/ é a Turma; tudo antes é o Curso; tudo
    depois é a Unidade. Ex.: "Dermato ONE T1 SP" -> Dermatologia One | T1 | São Paulo.
    """
    m = re.search(r"\bT(\d+)\b", name, re.IGNORECASE)
    if not m:
        return name.strip(), "", ""

    turma = m.group(1)
    curso = name[: m.start()].strip()
    unidade = name[m.end():].strip()

    unidade = UNIDADE_MAP.get(unidade.upper(), UNIDADE_MAP.get(unidade, unidade))
    curso = CURSO_MAP.get(curso.upper(), curso)

    return curso, turma, unidade


def _appointment_to_row(appt: dict, curso: str, turma: str, unidade: str) -> dict:
    """Converte um objeto Appointment da API para uma linha do DataFrame."""
    start = appt.get("start_datetime", "")
    end = appt.get("end_datetime", "")

    def fmt_date(dt_str: str) -> str:
        try:
            return datetime.fromisoformat(dt_str).strftime("%d/%m/%Y")
        except Exception:
            return dt_str

    def fmt_time(dt_str: str) -> str:
        try:
            return datetime.fromisoformat(dt_str).strftime("%H:%M")
        except Exception:
            return dt_str

    patient = appt.get("patient") or {}
    prof = appt.get("professional") or {}
    appt_type = appt.get("appointment_type") or {}
    appt_fmt = appt.get("appointment_format") or {}
    health_plan = appt.get("health_plan") or {}

    return {
        # identificadores internos, usados só para deduplicação (removidos antes de salvar)
        "_id": appt.get("id", ""),
        "_updated_at": appt.get("updated_at", ""),
        "Data": fmt_date(start),
        "Horário de início": fmt_time(start),
        "Horário de término": fmt_time(end),
        "Profissional": prof.get("name", ""),
        "Paciente": patient.get("name", ""),
        "Celular": patient.get("cellphone", ""),
        "Convênio": health_plan.get("name", ""),
        "Tipo de agendamento": appt_type.get("name", ""),
        "Formato": appt_fmt.get("name", ""),
        "Status": _normalize_status(appt.get("status", "")),
        "Curso": curso,
        "Turma": turma,
        "Unidade": unidade,
    }


class ConsultaJaClient:
    def __init__(self, cfg: ConsultaJaConfig, *, timeout: tuple[float, float] = REQUEST_TIMEOUT):
        if not cfg.is_configured:
            raise ConsultaJaConfigurationError(
                "CONSULTAJA_TOKEN não configurado. Copie pipeline/.env.example "
                "para pipeline/.env e preencha com o token fornecido pela ConsultaJá."
            )
        self._cfg = cfg
        self._timeout = timeout
        self._session = _make_session()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._cfg.token}",
            "Content-Type": "application/json",
        }

    def _paginate(self, url: str, params: dict) -> list:
        """Percorre todas as páginas de um endpoint paginado e retorna a lista completa.

        A API usa cursor baseado em start_datetime|created_at para
        /v1/appointments -- reagendamentos podem deslocar registros entre
        páginas durante a extração, causando duplicatas ou omissões. A
        mitigação é a deduplicação por _id feita em fetch_all().
        """
        results: list = []
        cursor = None
        page = 0
        while True:
            p = {**params, "limit": PAGE_LIMIT}
            if cursor:
                p["cursor"] = cursor

            resp = self._session.get(url, headers=self._headers(), params=p, timeout=self._timeout)
            if resp.status_code == 401:
                raise ConsultaJaConfigurationError("Token inválido ou expirado (401). Verifique CONSULTAJA_TOKEN.")
            resp.raise_for_status()

            body = resp.json()
            results += body.get("data", [])
            page += 1
            cursor = body.get("next_cursor")
            if not cursor or page >= MAX_PAGES:
                break
            time.sleep(0.2)
        return results

    def fetch_agendas(self) -> list:
        return self._paginate(f"{BASE_URL}/v1/agendas", {})

    def fetch_appointments(self, agenda_id: str, *, start_date: str | None, end_date: str | None) -> list:
        params: dict = {"agenda_id": agenda_id, "updated_since": "2000-01-01T00:00:00-03:00"}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self._paginate(f"{BASE_URL}/v1/appointments", params)

    def fetch_all(self, *, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
        """Busca todas as agendas habilitadas + seus agendamentos e devolve
        um DataFrame consolidado, deduplicado por _id (mantendo o registro
        com _updated_at mais recente) e ordenado por data/horário.
        """
        agendas = self.fetch_agendas()
        if not agendas:
            raise RuntimeError("Nenhuma agenda habilitada encontrada. Verifique as permissões do token.")

        start = start_date or self._cfg.start_date
        end = end_date or self._cfg.end_date

        rows: list[dict] = []
        erros: list[str] = []
        for agenda in agendas:
            agenda_id = agenda["id"]
            agenda_name = agenda.get("name", "")
            curso, turma, unidade = _parse_agenda_name(agenda_name)
            try:
                appointments = self.fetch_appointments(agenda_id, start_date=start, end_date=end)
            except Exception as e:
                erros.append(f"{agenda_name}: {e}")
                continue
            for appt in appointments:
                rows.append(_appointment_to_row(appt, curso, turma, unidade))

        if erros:
            print(f"Aviso: {len(erros)} agenda(s) ignorada(s) por erro de conexão:")
            for msg in erros:
                print(f"  - {msg}")

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df.sort_values("_updated_at", ascending=False, inplace=True)
        df.drop_duplicates(subset="_id", keep="first", inplace=True)
        df["_sort"] = pd.to_datetime(
            df["Data"] + " " + df["Horário de início"], format="%d/%m/%Y %H:%M", errors="coerce"
        )
        df.sort_values("_sort", inplace=True)
        df.drop(columns=["_id", "_updated_at", "_sort"], inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df
