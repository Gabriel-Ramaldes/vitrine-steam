@echo off
setlocal
cd /d "%~dp0"
title Vitrine - gerar executavel

echo ===============================================================
echo   Gera Vitrine.exe nesta pasta.
echo   Precisa ser feito no Windows: PyInstaller nao faz cross-compile.
echo ===============================================================
echo.

where python >nul 2>&1
if errorlevel 1 goto sempython

echo [1/3] Instalando dependencias...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install pyinstaller pillow
if errorlevel 1 goto falhapip

echo.
echo [2/3] Compilando... isto leva alguns minutos.
echo.
rem --collect-submodules: as etapas e os geradores sao importados em
rem tempo de execucao, entao a analise estatica do PyInstaller nao os ve.
rem --windowed: sem janela de console atras da interface.
python -m PyInstaller ^
    --onefile ^
    --noconfirm ^
    --windowed ^
    --name Vitrine ^
    --distpath "%~dp0." ^
    --workpath "%~dp0build_tmp" ^
    --specpath "%~dp0build_tmp" ^
    --collect-submodules passos ^
    --collect-submodules tools ^
    --hidden-import PIL._tkinter_finder ^
    "%~dp0app.py"
if errorlevel 1 goto falhabuild

echo.
echo [3/3] Limpando arquivos temporarios...
if exist "%~dp0build_tmp" rmdir /s /q "%~dp0build_tmp"

echo.
if not exist "%~dp0Vitrine.exe" goto semexe
echo ===============================================================
echo   PRONTO: Vitrine.exe criado nesta pasta.
echo   O Python deixa de ser necessario para rodar.
echo.
echo   IMPORTANTE: o exe le badges\, molduras\, adesivos\, capas\,
echo   originais\ e config.json da pasta ONDE ELE ESTIVER. Se voce
echo   mover o exe, leve essas pastas junto.
echo ===============================================================
echo.
pause
exit /b 0

:semexe
echo  Algo deu errado: Vitrine.exe nao foi criado.
echo.
pause
exit /b 1

:sempython
echo  Python nao encontrado no PATH.
echo  Instale de python.org marcando "Add Python to PATH"
echo  e tambem "tcl/tk and IDLE".
echo.
pause
exit /b 1

:falhapip
echo.
echo  Falhou ao instalar as dependencias. Veja o erro acima.
echo.
pause
exit /b 1

:falhabuild
echo.
echo  A compilacao falhou. Erro comum: o antivirus bloqueia o
echo  PyInstaller, ou Vitrine.exe esta aberto. Feche e tente de novo.
echo.
pause
exit /b 1
