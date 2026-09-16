"""Orquestra a atualização do dashboard Triagem: obtém a base de
agendamentos da ConsultaJá (mesma conta usada no pipeline do NPS-PACIENTE)
e regrava RAW/RAWD/RAWH/DAYCNT em ../index.html. Um comando só:

    python pipeline/atualizar_tudo.py

Antes de chamar a API, reaproveita a planilha do dia se ela já tiver sido
baixada -- por este pipeline ou pelo pipeline do NPS-PACIENTE (repositório
vizinho, mesma pasta dados-fonte/ compartilhada, ver config.py) -- assim as
duas atualizações não baixam a mesma base duas vezes. Se quiser forçar um
download novo, apague a planilha do dia em dados-fonte/ antes de rodar.

Não faz git add/commit/push -- isso continua manual de propósito (ver
README.md), pra sempre ter uma revisão humana antes de publicar no
repositório público. O resumo (console e pipeline/atualizacoes.log) só
contém contagens agregadas -- nunca nome, celular ou qualquer dado
identificável de paciente.
"""
from __future__ import annotations

import sys
import traceback
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from config import DADOS_FONTE_DIR, INDEX_HTML_PATH, PIPELINE_DIR
from consultaja_client import ConsultaJaConfigurationError
from fetch_consultaja import fetch_and_save
from render_index import upsert_all, upsert_last_update
from transform_triagem import build_daycnt, build_raw, build_rawd, build_rawh

LOG_PATH = PIPELINE_DIR / "atualizacoes.log"


def _log(lines: list[str]) -> None:
    text = "\n".join(lines) + "\n"
    print(text)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
        f.write(text)


def _planilha_de_hoje() -> Path | None:
    path = DADOS_FONTE_DIR / f"Base_Consulta_Ja{date.today():%y_%m_%d}.xlsx"
    return path if path.exists() else None


def main() -> int:
    report: list[str] = []

    report.append("PASSO 1/2 -- obter a base de agendamentos da ConsultaJá")
    existing = _planilha_de_hoje()
    if existing is not None:
        output_path = existing
        report.append(
            f"  Reaproveitando planilha já baixada hoje: "
            f"{output_path.relative_to(DADOS_FONTE_DIR.parent)} "
            "(evita baixar a mesma base de novo)."
        )
    else:
        try:
            output_path = fetch_and_save()
        except (ConsultaJaConfigurationError, RuntimeError) as e:
            report.append(f"  FALHOU: {e}")
            _log(report)
            return 1
        except Exception:
            report.append("  FALHOU: erro inesperado ao buscar na API. Detalhes:")
            report.append(traceback.format_exc())
            _log(report)
            return 1

        if output_path is None:
            report.append("  Nenhum agendamento encontrado -- index.html não foi alterado.")
            _log(report)
            return 0
        report.append(
            f"  OK -- planilha salva em {output_path.relative_to(DADOS_FONTE_DIR.parent)} "
            "(compartilhada com o pipeline do NPS-PACIENTE)."
        )

    report.append("\nPASSO 2/2 -- recalcular RAW/RAWD/RAWH/DAYCNT")
    try:
        df = pd.read_excel(output_path)
        data = {
            "RAW": build_raw(df),
            "RAWD": build_rawd(df),
            "RAWH": build_rawh(df),
            "DAYCNT": build_daycnt(df),
        }
        upsert_all(INDEX_HTML_PATH, data)
        upsert_last_update(INDEX_HTML_PATH, f"{datetime.now():%d/%m/%Y %H:%M}")
    except Exception:
        report.append("  FALHOU: erro ao processar/gravar os dados. Detalhes:")
        report.append(traceback.format_exc())
        _log(report)
        return 1

    report.append(
        f"  OK -- {len(data['RAW'])} combinações mês/curso/turma · "
        f"{len(data['RAWD'])} combinações dia/curso/turma · "
        f"{len(data['RAWH'])} combinações de hora · "
        f"{len(data['DAYCNT'])} combinações mês/semana."
    )
    report.append(
        "\nTudo certo. Próximos passos (revise antes de publicar):\n"
        "  git status\n"
        "  git diff -- index.html\n"
        "  git add index.html\n"
        '  git commit -m "Atualiza dados do dashboard"\n'
        "  git push"
    )
    _log(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
