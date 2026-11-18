#!/bin/bash
# Prepara o Clipador dentro do Codespace. Roda sozinho na criacao.
set -u
echo ""
echo "  preparando o Clipador na nuvem"
echo ""

sudo apt-get update -qq
sudo apt-get install -y -qq ffmpeg tesseract-ocr tesseract-ocr-por tesseract-ocr-eng >/dev/null
echo "  ffmpeg:    $(ffmpeg -version 2>/dev/null | head -1 | cut -d' ' -f1-3)"
echo "  tesseract: $(tesseract --version 2>/dev/null | head -1)"

pip install --quiet --upgrade pip
pip install --quiet numpy Pillow yt-dlp pytesseract
echo "  basico instalado"

# transcricao por processador (nao existe Neural Engine aqui)
pip install --quiet faster-whisper || echo "  (faster-whisper nao entrou, os clipes saem sem legenda)"

mkdir -p /workspaces/clipador-dados/{clipes,bruto,dados,perfis,fontes,capas}
cp -n perfis/*.json /workspaces/clipador-dados/perfis/ 2>/dev/null

# fonte das legendas: usa a do sistema, ou a sua se voce soltar os .ttf
# na pasta clipador-dados/fontes pelo explorador de arquivos aqui do lado
sudo apt-get install -y -qq fonts-dejavu-core >/dev/null 2>&1

echo ""
echo "  pronto. A tela do Clipador abre sozinha na aba de visualizacao."
echo "  Se nao abrir: aba PORTS, porta 8777, clique no globo."
echo ""
