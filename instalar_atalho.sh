#!/usr/bin/env bash
# Põe a Vitrine no menu de aplicativos, com o ícone.
#
# Não precisa de root e não escreve em /usr — o que importa no SteamOS,
# cujo sistema é somente leitura. Tudo vai pra dentro do seu ~/.local,
# que é gravável inclusive no Steam Deck.
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
BIN="$AQUI/vitrine"

[ -x "$BIN" ] || { echo "não achei o executável em $BIN"; exit 1; }

APPS="$HOME/.local/share/applications"
ICONES="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$APPS" "$ICONES"

cp "$AQUI/vitrine.png" "$ICONES/vitrine.png"

# o Exec aponta pro binário onde ele está agora: se você mover a pasta,
# rode este script de novo
sed "s|^Exec=.*|Exec=\"$BIN\"|" "$AQUI/vitrine.desktop" \
    > "$APPS/vitrine.desktop"
chmod +x "$APPS/vitrine.desktop"

# sem isto o menu só percebe o atalho no próximo login
command -v update-desktop-database >/dev/null \
    && update-desktop-database "$APPS" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null \
    && gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "Pronto. A Vitrine está no menu de aplicativos."
echo
echo "No Steam Deck, pra ela aparecer no Modo Jogo:"
echo "  Steam (Modo Área de Trabalho) > Jogos > Adicionar um jogo"
echo "  que não seja da Steam > Procurar > escolha:"
echo "  $BIN"
