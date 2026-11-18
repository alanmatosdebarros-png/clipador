#!/bin/bash
# Gera o "Instalar Clipador.command" a partir do codigo desta pasta.
set -e
cd "$(dirname "$0")"
tar czf instalador/carga.tgz --exclude='__pycache__' --exclude='.git' --exclude='instalador' \
  --exclude='Instalar Clipador.command' --exclude='construir_instalador.sh' \
  --exclude='.gitignore' .
python3 - <<'PY'
import base64, pathlib
cab = pathlib.Path('instalador/cabeca.sh').read_text().split('\n')
i = next(k for k, l in enumerate(cab) if l.strip() == '__CARGA__')
texto = '\n'.join(cab[:i + 1]).replace('__LINHA__', str(i + 2)) + '\n'
b64 = base64.b64encode(pathlib.Path('instalador/carga.tgz').read_bytes()).decode()
saida = pathlib.Path('Instalar Clipador.command')
saida.write_text(texto + b64 + '\n')
saida.chmod(0o755)
print('gerado:', saida, round(saida.stat().st_size / 1024), 'KB')
PY
rm -f instalador/carga.tgz
