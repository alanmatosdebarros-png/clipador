#!/bin/bash
# Instalador do Clipador. Clique duplo neste arquivo.
# Na primeira vez o macOS pode reclamar: clique com o botao direito > Abrir.

set -u
cd "$(dirname "$0")"
RAIZ="$(pwd)"
CASA="$HOME/Clipador"
VENV="$CASA/venv"

echo ""
echo "  Clipador"
echo "  instalando em $CASA"
echo ""

mkdir -p "$CASA" "$CASA/clipes" "$CASA/bruto" "$CASA/dados" "$CASA/perfis" "$CASA/fontes" "$CASA/capas"
xattr -dr com.apple.quarantine "$RAIZ" 2>/dev/null

# ---------------------------------------------------------------- python
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    v=$("$c" -c 'import sys;print(sys.version_info[0]*100+sys.version_info[1])' 2>/dev/null)
    if [ -n "${v:-}" ] && [ "$v" -ge 310 ]; then PY="$c"; break; fi
    [ -z "$PY" ] && PY="$c"
  fi
done
if [ -z "$PY" ]; then
  echo "  Nao achei o Python. Abra o Terminal e rode:  xcode-select --install"
  echo "  Depois clique neste instalador de novo."
  read -n 1 -s -r -p "  (enter pra fechar)"; exit 1
fi
echo "  python: $($PY --version 2>&1)"

if [ ! -d "$VENV" ]; then "$PY" -m venv "$VENV"; fi
PIP="$VENV/bin/pip"
PYV="$VENV/bin/python"
"$PIP" install --quiet --upgrade pip wheel >/dev/null 2>&1

echo "  instalando o basico (numpy, Pillow, yt-dlp)"
"$PIP" install --quiet numpy Pillow yt-dlp || {
  echo "  nao consegui instalar o basico. Confere a internet e tenta de novo."
  read -n 1 -s -r -p "  (enter pra fechar)"; exit 1
}

# -------------------------------------------------- chip da Apple: extras
ARCO="$(uname -m)"
if [ "$ARCO" = "arm64" ]; then
  echo "  chip da Apple detectado, instalando transcricao no proprio chip"
  "$PIP" install --quiet mlx-whisper || echo "  (mlx-whisper nao entrou, segue sem ele)"
  echo "  instalando a leitura de tela da Apple (Vision)"
  "$PIP" install --quiet pyobjc-framework-Vision pyobjc-framework-Quartz || echo "  (Vision nao entrou, segue sem ele)"
else
  echo "  Mac Intel: usando transcricao por processador"
  "$PIP" install --quiet faster-whisper || echo "  (faster-whisper nao entrou, segue sem legenda)"
fi

# --------------------------------------------------------------- ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "  procurando o ffmpeg"
  if command -v brew >/dev/null 2>&1; then
    brew install ffmpeg || true
  fi
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  "$PIP" install --quiet static-ffmpeg >/dev/null 2>&1 && "$VENV/bin/static_ffmpeg" -version >/dev/null 2>&1
fi
if command -v ffmpeg >/dev/null 2>&1; then
  echo "  ffmpeg: $(command -v ffmpeg)"
else
  echo "  AVISO: sem ffmpeg. Instale o Homebrew em brew.sh e rode: brew install ffmpeg"
fi

# ---------------------------------------------------------------- fontes
for f in Montserrat-ExtraBold.ttf Montserrat-Black.ttf Montserrat-Bold.ttf; do
  for origem in "$HOME/Downloads/$f" "$RAIZ/fontes/$f"; do
    [ -f "$origem" ] && cp -n "$origem" "$CASA/fontes/" 2>/dev/null
  done
done
if ls "$CASA/fontes/"*.ttf >/dev/null 2>&1; then
  echo "  fonte: Montserrat encontrada"
else
  echo "  fonte: usando a do sistema (jogue as Montserrat em $CASA/fontes se quiser a sua)"
fi

cp -n "$RAIZ/perfis/"*.json "$CASA/perfis/" 2>/dev/null

# ------------------------------------------------------------------- app
APP="/Applications/Clipador.app"
[ -w /Applications ] || APP="$HOME/Applications/Clipador.app"
mkdir -p "$(dirname "$APP")"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Clipador</string>
  <key>CFBundleDisplayName</key><string>Clipador</string>
  <key>CFBundleIdentifier</key><string>br.alan.clipador</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>Clipador</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>LSUIElement</key><false/>
</dict></plist>
PLIST

cat > "$APP/Contents/MacOS/Clipador" <<LANC
#!/bin/bash
cd "$RAIZ"
exec "$VENV/bin/python" "$RAIZ/clipador.py"
LANC
chmod +x "$APP/Contents/MacOS/Clipador"
xattr -dr com.apple.quarantine "$APP" 2>/dev/null

echo ""
echo "  pronto."
echo "  o Clipador esta em $APP"
echo "  abra pelo Launchpad ou pela pasta Aplicativos."
echo ""
"$PYV" - <<'CHECA'
import sys, subprocess, shutil
print("  conferindo:")
for m in ("numpy", "PIL", "yt_dlp"):
    try:
        __import__(m); print(f"    {m}: ok")
    except Exception:
        print(f"    {m}: FALTANDO")
for m, rotulo in (("mlx_whisper", "transcricao no chip"), ("Vision", "leitura de tela")):
    try:
        __import__(m); print(f"    {rotulo}: ok")
    except Exception:
        print(f"    {rotulo}: nao instalado (opcional)")
print("    ffmpeg:", shutil.which("ffmpeg") or "FALTANDO")
CHECA
echo ""
read -n 1 -s -r -p "  (enter pra fechar)"
echo ""
