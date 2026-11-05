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

rem O icone do exe: o seu vence, o do repositorio e a rede de seguranca.
rem Sem nenhum dos dois o PyInstaller usa o proprio, e esta tudo bem.
set ICONE=
if exist "%~dp0assets\icone\padrao.ico"  set ICONE=--icon "%~dp0assets\icone\padrao.ico"
if exist "%~dp0assets\icone\vitrine.ico" set ICONE=--icon "%~dp0assets\icone\vitrine.ico"

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
    --add-data "%~dp0assets;assets" ^
    --add-data "%~dp0assets\glifos\LICENSE-bootstrap-icons.txt;." ^
    %ICONE% ^
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
echo   A pasta assets viaja inteira dentro do exe - badges, molduras,
echo   adesivos e icone. Ele funciona sozinho, sem pasta ao lado.
echo.
echo   Pra distribuir, mande Vitrine.exe e docs\LEIAME.txt. So isso.
echo.
echo   O que ELE CRIA ao lado de si mesmo: config.json, originais\,
echo   capas\, preview\, molduras\ e estado.json. Se mover o exe,
echo   leve essas pastas junto - sao os seus dados.
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
