#!/bin/bash
# MiRG Chart Editor installer for macOS. Paste into Terminal:
#   curl -fsSL https://raw.githubusercontent.com/andrewjfiore/mirg-chart-editor/main/install.sh | bash
# Files fetched with curl carry no download quarantine, so macOS opens the app without the "Not Opened" warning.
# Running it again updates the app and keeps its Python setup, models and your work.
set -e
DIR="${MIRG_DIR:-$HOME/MiRG Chart Editor}"
TMP="$(mktemp -d)"
echo "Downloading MiRG Chart Editor into: $DIR"
curl -fsSL https://github.com/andrewjfiore/mirg-chart-editor/archive/refs/heads/main.zip -o "$TMP/mirg.zip"
unzip -q "$TMP/mirg.zip" -d "$TMP"
mkdir -p "$DIR"
cp -R "$TMP/mirg-chart-editor-main/." "$DIR/"
chmod +x "$DIR/Start MiRG (Mac).command"
echo "Installed. Next time, double-click \"Start MiRG (Mac).command\" in that folder."
exec "$DIR/Start MiRG (Mac).command"
