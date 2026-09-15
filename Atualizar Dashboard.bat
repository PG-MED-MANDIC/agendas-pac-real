@echo off
setlocal
cd /d "%~dp0pipeline"

where python >nul 2>nul
if errorlevel 1 (
    echo Python nao encontrado no PATH. Instale o Python ou ative o ambiente virtual
    echo do pipeline antes de rodar este atalho ^(ver pipeline\README.md^).
    pause
    exit /b 1
)

python atualizar_tudo.py
set EXITCODE=%ERRORLEVEL%

echo.
echo ============================================================
if %EXITCODE%==0 (
    echo Atualizacao concluida. Revise o resumo acima, depois rode:
    echo   git status
    echo   git add index.html
    echo   git commit -m "Atualiza dados do dashboard"
    echo   git push
) else (
    echo A atualizacao encontrou um problema -- veja as mensagens acima
    echo antes de decidir se precisa rodar de novo.
)
echo ============================================================
pause
exit /b %EXITCODE%
