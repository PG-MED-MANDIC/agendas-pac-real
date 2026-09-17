"""Configuração do pipeline: caminhos e credenciais da ConsultaJá.

Mesma conta/token já usados no pipeline do NPS-PACIENTE -- este dashboard
(Triagem) usa só a API da ConsultaJá, não usa Indecx. Credenciais nunca
ficam hardcoded aqui -- vêm de pipeline/.env (fora do controle de versão).

DADOS_FONTE_DIR aponta pra fora deste repositório, pra dados-fonte/ na raiz
do workspace (pasta NPS-PACIENTE, que contém este repositório como
subpasta) -- é a MESMA pasta que o pipeline do NPS-PACIENTE usa. Proposital:
os dois pipelines usam a mesma conta/token da ConsultaJá, então
atualizar_tudo.py reaproveita a planilha do dia se ela já tiver sido
baixada por qualquer um dos dois, em vez de baixar de novo (ver
CONTEXTO-GITHUB.md na raiz do workspace). Só funciona com essa disposição
de pastas -- se este repositório for movido pra fora de NPS-PACIENTE,
ajuste este caminho.
"""
from __future__ import annotations

import calendar
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PIPELINE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PIPELINE_DIR.parent
INDEX_HTML_PATH = PROJECT_DIR / "index.html"
DADOS_FONTE_DIR = PROJECT_DIR.parent / "dados-fonte"

# Mesmo arquivo usado pelo pipeline de agendas_pgmed (capacidade planejada
# das práticas) -- baixado manualmente do SharePoint, nunca por este
# pipeline. Usado só pela aba "Slots x Realizado" (ver transform_slots.py).
CHECKLIST_XLSX_PATH = DADOS_FONTE_DIR / "checklist-captacao.xlsx"


@dataclass(frozen=True)
class ConsultaJaConfig:
    token: str | None
    start_date: str | None
    end_date: str | None

    @property
    def is_configured(self) -> bool:
        return bool(self.token)


def default_consultaja_end_date(today: date | None = None) -> str:
    """Fim do mês, 2 meses à frente de hoje (mesma lógica do NPS-PACIENTE) --
    recalculado a cada execução, não precisa editar CONSULTAJA_END_DATE
    manualmente quando o mês vira.
    """
    today = today or date.today()
    month_index = today.month - 1 + 2  # 0-based, +2 meses
    year = today.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day).isoformat()


def load_consultaja_config() -> ConsultaJaConfig:
    return ConsultaJaConfig(
        token=os.getenv("CONSULTAJA_TOKEN") or None,
        start_date=os.getenv("CONSULTAJA_START_DATE") or None,
        end_date=os.getenv("CONSULTAJA_END_DATE") or default_consultaja_end_date(),
    )
