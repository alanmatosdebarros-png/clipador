#!/bin/bash
# =====================================================================
#  Clipador  ::  instalador de um arquivo so
#
#  Se o macOS reclamar que nao pode verificar o arquivo:
#  clique com o botao direito neste arquivo e escolha Abrir.
# =====================================================================

set -u
CASA="$HOME/Clipador"
RAIZ="$CASA/app"
VENV="$CASA/venv"
LINHA_CARGA=__LINHA__

clear
echo ""
echo "   Clipador"
echo "   instalando em $CASA"
echo ""

mkdir -p "$CASA/clipes" "$CASA/bruto" "$CASA/dados" "$CASA/perfis" "$CASA/fontes" "$CASA/capas"
xattr -dr com.apple.quarantine "$0" 2>/dev/null

# ------------------------------------------------------------- python
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    v=$("$c" -c 'import sys;print(sys.version_info[0]*100+sys.version_info[1])' 2>/dev/null)
    if [ -n "${v:-}" ] && [ "$v" -ge 310 ]; then PY="$c"; break; fi
    [ -z "$PY" ] && PY="$c"
  fi
done
if [ -z "$PY" ]; then
  echo "   Falta o Python no seu Mac."
  echo "   Abra o Terminal, cole isto, de enter, espere terminar:"
  echo ""
  echo "       xcode-select --install"
  echo ""
  echo "   Depois clique neste instalador de novo."
  echo ""
  read -n 1 -s -r -p "   (enter pra fechar)"; exit 1
fi
echo "   python: $($PY --version 2>&1)"

# ------------------------------------------------- descompacta o proprio
echo "   abrindo os arquivos do app"
rm -rf "$RAIZ"; mkdir -p "$RAIZ"
tail -n +$LINHA_CARGA "$0" | "$PY" -c '
import sys, base64, io, tarfile
bruto = base64.b64decode(sys.stdin.buffer.read())
t = tarfile.open(fileobj=io.BytesIO(bruto), mode="r:gz")
try:
    t.extractall(sys.argv[1], filter="data")
except TypeError:
    t.extractall(sys.argv[1])
' "$RAIZ" || { echo "   nao consegui abrir os arquivos"; read -n 1 -s -r -p "   (enter)"; exit 1; }
[ -f "$RAIZ/clipador.py" ] || { echo "   arquivo incompleto, baixe de novo"; read -n 1 -s -r -p "   (enter)"; exit 1; }

# ------------------------------------------------------------ bibliotecas
if [ ! -d "$VENV" ]; then "$PY" -m venv "$VENV"; fi
PIP="$VENV/bin/pip"
PYV="$VENV/bin/python"
"$PIP" install --quiet --upgrade pip wheel >/dev/null 2>&1

echo "   instalando o basico (pode demorar uns minutos)"
"$PIP" install --quiet numpy Pillow yt-dlp || {
  echo "   nao consegui instalar o basico. Confere a internet e tenta de novo."
  read -n 1 -s -r -p "   (enter pra fechar)"; exit 1; }

if [ "$(uname -m)" = "arm64" ]; then
  echo "   chip da Apple: ligando transcricao no proprio chip"
  "$PIP" install --quiet mlx-whisper 2>/dev/null || echo "   (transcricao no chip nao entrou, segue sem ela)"
  echo "   ligando a leitura de tela da Apple"
  "$PIP" install --quiet pyobjc-framework-Vision pyobjc-framework-Quartz 2>/dev/null \
    || echo "   (leitura de tela nao entrou, segue sem ela)"
else
  echo "   Mac Intel: transcricao por processador"
  "$PIP" install --quiet faster-whisper 2>/dev/null || echo "   (transcricao nao entrou)"
fi

# ---------------------------------------------------------------- ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1 && [ ! -x /opt/homebrew/bin/ffmpeg ] && [ ! -x /usr/local/bin/ffmpeg ]; then
  if command -v brew >/dev/null 2>&1; then
    echo "   instalando o ffmpeg pelo Homebrew"
    brew install ffmpeg >/dev/null 2>&1 || true
  fi
fi
if ! command -v ffmpeg >/dev/null 2>&1 && [ ! -x /opt/homebrew/bin/ffmpeg ] && [ ! -x /usr/local/bin/ffmpeg ]; then
  echo "   baixando um ffmpeg so pro app"
  "$PIP" install --quiet static-ffmpeg >/dev/null 2>&1
  "$PYV" -c "from static_ffmpeg import run; print(run.get_or_fetch_platform_executables_else_raise()[0])" >/dev/null 2>&1 \
    || echo "   (nao deu. Instale o Homebrew em brew.sh e rode: brew install ffmpeg)"
fi

# ---------------------------------------------------------------- fontes
for f in Montserrat-ExtraBold.ttf Montserrat-Black.ttf Montserrat-Bold.ttf; do
  for o in "$HOME/Downloads/$f" "$HOME/Desktop/$f"; do
    [ -f "$o" ] && cp -n "$o" "$CASA/fontes/" 2>/dev/null
  done
done
cp -n "$RAIZ/perfis/"*.json "$CASA/perfis/" 2>/dev/null

# ------------------------------------------------------------------- app
APP="/Applications/Clipador.app"
mkdir -p /Applications 2>/dev/null
touch /Applications/.clipador_teste 2>/dev/null && rm -f /Applications/.clipador_teste || APP="$HOME/Applications/Clipador.app"
mkdir -p "$(dirname "$APP")"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<'PLIST'
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
  <key>CFBundleIconFile</key><string>icone.icns</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
</dict></plist>
PLIST

cat > "$APP/Contents/MacOS/Clipador" <<LANC
#!/bin/bash
export PATH="$VENV/bin:/opt/homebrew/bin:/usr/local/bin:\$PATH"
cd "$RAIZ"
exec "$VENV/bin/python" "$RAIZ/clipador.py"
LANC
chmod +x "$APP/Contents/MacOS/Clipador"

"$PYV" - "$APP/Contents/Resources" <<'ICONE' 2>/dev/null
import sys, os, subprocess, tempfile
try:
    from PIL import Image, ImageDraw
except Exception:
    sys.exit(0)

def desenhar(n):
    e, = (4,)
    N = n * e
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    m = N * 0.075
    d.rounded_rectangle([m, m, N - m, N - m], N * 0.225, fill=(13, 13, 18, 255))
    lf = N * 0.265
    af = lf * 16 / 9
    x0, y0 = (N - lf) / 2, (N - af) / 2
    d.rounded_rectangle([x0, y0, x0 + lf, y0 + af], N * 0.045,
                        outline=(124, 92, 255, 255), width=max(2, int(N * 0.028)))
    cx, cy, r = N / 2, N / 2, N * 0.072
    d.polygon([(cx - r * 0.72, cy - r), (cx - r * 0.72, cy + r), (cx + r * 0.95, cy)],
              fill=(54, 232, 255, 255))
    for lado in (-1, 1):
        xx = cx + lado * N * 0.325
        d.rounded_rectangle([xx - N * 0.016, cy - N * 0.13, xx + N * 0.016, cy + N * 0.13],
                            N * 0.016, fill=(60, 60, 76, 255))
    return im.resize((n, n), Image.LANCZOS)

destino = sys.argv[1]
conj = os.path.join(tempfile.mkdtemp(), "i.iconset")
os.makedirs(conj, exist_ok=True)
for n in (16, 32, 64, 128, 256, 512, 1024):
    im = desenhar(n)
    im.save(os.path.join(conj, f"icon_{n}x{n}.png"))
    im.save(os.path.join(conj, f"icon_{n // 2}x{n // 2}@2x.png"))
try:
    subprocess.run(["iconutil", "-c", "icns", conj, "-o",
                    os.path.join(destino, "icone.icns")], capture_output=True, timeout=60)
except Exception:
    pass
ICONE

xattr -dr com.apple.quarantine "$APP" 2>/dev/null
touch "$APP"

echo ""
echo "   conferindo:"
"$PYV" - <<'CHECA'
import shutil, os
venv = os.path.expanduser("~/Clipador/venv/bin")
for m, r in (("numpy", "numpy"), ("PIL", "Pillow"), ("yt_dlp", "yt-dlp")):
    try:
        __import__(m); print(f"      {r}: ok")
    except Exception:
        print(f"      {r}: FALTANDO")
for m, r in (("mlx_whisper", "transcricao no chip"), ("Vision", "leitura de tela")):
    try:
        __import__(m); print(f"      {r}: ok")
    except Exception:
        print(f"      {r}: nao instalado (o app funciona sem)")
f = shutil.which("ffmpeg") or (os.path.join(venv, "ffmpeg") if os.path.exists(os.path.join(venv, "ffmpeg")) else None)
print("      ffmpeg:", f or "FALTANDO")
CHECA

echo ""
echo "   pronto. O Clipador esta em $APP"
echo "   ele abre agora e vai aparecer no Launchpad daqui pra frente."
echo ""
sleep 1
open "$APP" 2>/dev/null
read -n 1 -s -r -p "   (enter pra fechar esta janela)"
echo ""
exit 0
__CARGA__
