"""Regrava as 4 constantes de dados (`var RAW`, `var RAWD`, `var RAWH`,
`var DAYCNT`) dentro de ../index.html, preservando todo o resto do arquivo
(HTML, CSS, lógica de gráficos/filtros) intocado.

Diferente do render_script.py do NPS-PACIENTE (que assume um bloco de
`const` isolado no topo do arquivo), aqui os `var` ficam no meio de um
<script> maior, cercados de outra lógica -- então cada constante é
localizada pela linha exata onde já está e substituída ali mesmo, nunca
inserida em lugar novo (evita quebrar a ordem de dependência com
CURSOS/MESES, que são calculados a partir desses arrays logo em seguida).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

NAMES = ("RAW", "RAWD", "RAWH", "DAYCNT")

_LAST_UPDATE_RE = re.compile(r'(<div[^>]*\bid="last-update"[^>]*>)[^<]*(</div>)')


def upsert_last_update(html_path: Path, label: str) -> None:
    text = html_path.read_text(encoding="utf-8", newline="")
    new_text, n = _LAST_UPDATE_RE.subn(rf"\g<1>{label}\g<2>", text, count=1)
    if n == 0:
        raise RuntimeError('Não encontrei \'<div id="last-update">\' no index.html.')
    html_path.write_text(new_text, encoding="utf-8", newline="")


def _upsert_var(lines: list[str], name: str, value) -> list[str]:
    pattern = re.compile(rf"^var {name}=.*;")
    new_value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    for i, line in enumerate(lines):
        if pattern.match(line):
            ending = line[len(line.rstrip("\r\n")):]
            lines[i] = f"var {name}={new_value};{ending}"
            return lines

    raise RuntimeError(
        f"Não encontrei a linha 'var {name}=...;' no index.html -- abortando para não "
        "corromper o arquivo. Verifique manualmente antes de rodar de novo."
    )


def upsert_all(html_path: Path, data: dict[str, list[dict]]) -> None:
    # newline="" evita reescrever \n -> \r\n no arquivo inteiro (Windows) --
    # sem isso o diff mostraria o arquivo inteiro como alterado a cada execução.
    lines = html_path.read_text(encoding="utf-8", newline="").splitlines(keepends=True)

    for name in NAMES:
        lines = _upsert_var(lines, name, data[name])

    html_path.write_text("".join(lines), encoding="utf-8", newline="")
