#!/usr/bin/env bash
# Gera o executável Linux (dist/vitrine) e o pacote de release.
#
# O PyInstaller não faz cross-compile: isto precisa rodar no Linux.
#
# ATENÇÃO À GLIBC. O binário sai exigindo a glibc da máquina onde foi
# compilado, e glibc só é compatível pra frente: feito numa nova, não
# roda numa antiga. Compilar no Ubuntu 24.04 produz um piso de 2.38, que
# deixa de fora Ubuntu 22.04, Debian 12 e Mint 21. Para alcançar mais
# gente, compile numa base mais velha — é o que o .github/workflows faz,
# usando ubuntu-22.04. O script avisa qual piso ele produziu.
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")" && pwd)"
cd "$RAIZ"

echo "==============================================================="
echo "  Vitrine - executável Linux"
echo "==============================================================="
echo

# PYTHON=python3.12 ./build_linux.sh  - útil em máquina com vários
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null || { echo "$PY não encontrado."; exit 1; }
"$PY" -c 'import tkinter' 2>/dev/null || {
    echo "Falta o tkinter. Instale:"
    echo "  Debian/Ubuntu : sudo apt install python3-tk"
    echo "  Arch/SteamOS  : o pacote 'tk'"
    echo "  Fedora        : sudo dnf install python3-tkinter"
    echo
    echo "Se o tkinter estiver em outro Python desta máquina:"
    echo "  PYTHON=python3.12 ./build_linux.sh"
    exit 1
}

echo "[1/4] Dependências..."
"$PY" -m pip install --upgrade --quiet pip 2>/dev/null || true
"$PY" -m pip install --quiet pyinstaller pillow 2>/dev/null \
  || "$PY" -m pip install --quiet --break-system-packages pyinstaller pillow

echo "[2/4] Compilando..."
rm -rf build_tmp dist
"$PY" -m PyInstaller \
    --onefile --noconfirm --windowed \
    --name vitrine \
    --distpath dist \
    --workpath build_tmp \
    --specpath build_tmp \
    --collect-submodules passos \
    --collect-submodules tools \
    --add-data "$RAIZ/assets:assets" \
    --hidden-import PIL._tkinter_finder \
    app.py

echo "[3/4] Montando o pacote..."
PACOTE="dist/vitrine-linux-x86_64"
rm -rf "$PACOTE"; mkdir -p "$PACOTE"
cp dist/vitrine "$PACOTE/"
cp docs/LEIAME-linux.txt "$PACOTE/LEIAME.txt" 2>/dev/null || true
cp assets/icone/vitrine.png "$PACOTE/vitrine.png"
cp vitrine.desktop "$PACOTE/" 2>/dev/null || true
cp instalar_atalho.sh "$PACOTE/" 2>/dev/null || true
chmod +x "$PACOTE/vitrine" "$PACOTE/instalar_atalho.sh" 2>/dev/null || true
tar -czf "dist/vitrine-linux-x86_64.tar.gz" -C dist "vitrine-linux-x86_64"

echo "[4/4] Medindo o piso de glibc..."
# O bootloader exige pouco; quem manda são as bibliotecas embutidas
# (libpython, libtcl, libtk). Por isso o pacote é aberto e medido inteiro
# em vez de olhar só o binário de fora.
PISO=$("$PY" - <<'PY' 2>/dev/null || echo "?"
import pathlib, re, subprocess, sys, tempfile
from PyInstaller.archive.readers import CArchiveReader

maior = (0, 0)
with tempfile.TemporaryDirectory() as tmp:
    arq = CArchiveReader("dist/vitrine")
    for nome in arq.toc:
        if not (nome.endswith(".so") or ".so." in nome):
            continue
        try:
            dados = arq.extract(nome)
        except Exception:
            continue
        if isinstance(dados, tuple):
            dados = dados[1]
        alvo = pathlib.Path(tmp) / pathlib.Path(nome).name
        alvo.write_bytes(dados)
        saida = subprocess.run(["objdump", "-T", str(alvo)],
                               capture_output=True, text=True).stdout
        for m in re.finditer(r"GLIBC_(\d+)\.(\d+)", saida):
            v = (int(m.group(1)), int(m.group(2)))
            if v > maior:
                maior = v
print(f"{maior[0]}.{maior[1]}" if maior != (0, 0) else "?")
PY
)
echo
echo "==============================================================="
echo "  PRONTO"
echo
echo "  dist/vitrine                        o executável"
echo "  dist/vitrine-linux-x86_64.tar.gz    o pacote de release"
echo
echo "  Este binário exige glibc >= ${PISO}"
echo "  Ele roda em qualquer sistema de glibc igual ou mais nova."
echo "  Para ver a da máquina onde ele vai rodar:  ldd --version"
echo "==============================================================="
