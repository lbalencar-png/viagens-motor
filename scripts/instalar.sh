#!/bin/bash
# Instala o viagens-motor para uso: venv fixo, atalhos em ~/.local/bin e, opcionalmente,
# registro no app do Claude e verificação diária pelo launchd.
# Uso: scripts/instalar.sh [--config CAMINHO] [--registrar-claude-desktop] [--agendar] [--atualizar-lock]
# Sem --config, usa VIAGENS_MOTOR_CONFIG do ambiente (é assim que o autorreparo funciona).
# O ambiente é refeito a partir do requirements.lock versionado; só --atualizar-lock o regenera.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DADOS="$HOME/.local/share/viagens-motor"
VENV="$DADOS/venv"
BIN="$HOME/.local/bin"
CONFIG="${VIAGENS_MOTOR_CONFIG:-}"
ATUALIZAR_LOCK=0
REGISTRAR=0
AGENDAR=0
while [ $# -gt 0 ]; do
  case "$1" in
    --config) CONFIG="$2"; shift 2 ;;
    --registrar-claude-desktop) REGISTRAR=1; shift ;;
    --agendar) AGENDAR=1; shift ;;
    --atualizar-lock) ATUALIZAR_LOCK=1; shift ;;
    *) echo "opção desconhecida: $1" >&2; exit 2 ;;
  esac
done
export UV_CACHE_DIR="$DADOS/uv-cache"
mkdir -p "$DADOS" "$BIN"

if [ "$ATUALIZAR_LOCK" = 1 ]; then
  (cd "$REPO" && uv pip compile -q pyproject.toml -o requirements.lock --python-version 3.12)
fi
[ -f "$REPO/requirements.lock" ] || { echo "requirements.lock ausente; rode com --atualizar-lock" >&2; exit 1; }
# Um venv não é relocável (os atalhos guardam o caminho absoluto), então o novo é montado no
# lugar definitivo; o antigo fica de lado e só é apagado depois de o novo importar.
rm -rf "$VENV.antigo"
[ -d "$VENV" ] && mv "$VENV" "$VENV.antigo"
restaurar() { rm -rf "$VENV"; [ -d "$VENV.antigo" ] && mv "$VENV.antigo" "$VENV"; echo "instalação falhou; ambiente anterior mantido" >&2; }
trap restaurar ERR
uv venv -q "$VENV" -p 3.12
uv pip install -q -p "$VENV" -r "$REPO/requirements.lock"
uv pip install -q -p "$VENV" --no-deps "$REPO"
"$VENV/bin/python" -c "import viagens_motor"
trap - ERR
rm -rf "$VENV.antigo"
cp "$REPO/scripts/saude.py" "$DADOS/saude.py"

ENV_LINHA=""
if [ -n "$CONFIG" ]; then ENV_LINHA="export VIAGENS_MOTOR_CONFIG=\"$CONFIG\""; fi
cat > "$BIN/viagens-motor.tmp" <<EOF
#!/bin/sh
$ENV_LINHA
exec "$VENV/bin/viagens-motor" "\$@"
EOF
cat > "$BIN/viagens-motor-mcp.tmp" <<EOF
#!/bin/sh
$ENV_LINHA
exec "$VENV/bin/viagens-motor-mcp" "\$@"
EOF
cat > "$BIN/viagens-motor-saude.tmp" <<EOF
#!/bin/sh
$ENV_LINHA
if ! "$VENV/bin/python" -c "import viagens_motor" 2>/dev/null; then
  echo "\$(date '+%Y-%m-%dT%H:%M:%S') venv quebrado; reinstalando" >> "\$HOME/Library/Logs/viagens-motor-saude.log"
  /bin/bash "$REPO/scripts/instalar.sh" >> "\$HOME/Library/Logs/viagens-motor-saude.log" 2>&1
fi
exec "$VENV/bin/python" "$DADOS/saude.py" "\$@"
EOF
for n in viagens-motor viagens-motor-mcp viagens-motor-saude; do chmod +x "$BIN/$n.tmp"; mv "$BIN/$n.tmp" "$BIN/$n"; done

if [ "$REGISTRAR" = 1 ]; then
  C="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
  if [ -f "$C" ]; then
    cp "$C" "$C.bak-$(date +%Y%m%d-%H%M)-viagens-motor"
  else
    mkdir -p "$(dirname "$C")"
    printf '{"mcpServers": {}}\n' > "$C"
  fi
  /usr/bin/python3 - "$C" "$BIN/viagens-motor-mcp" <<'PY'
import json, sys
p, cmd = sys.argv[1], sys.argv[2]
d = json.load(open(p))
d.setdefault("mcpServers", {})["viagens-motor"] = {"command": cmd}
json.dump(d, open(p, "w"), indent=2, ensure_ascii=False)
PY
fi

if [ "$AGENDAR" = 1 ]; then
  P="$HOME/Library/LaunchAgents/com.bm.viagens-motor-saude.plist"
  cat > "$P" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
 <key>Label</key><string>com.bm.viagens-motor-saude</string>
 <key>ProgramArguments</key><array><string>/bin/sh</string><string>$BIN/viagens-motor-saude</string></array>
 <key>EnvironmentVariables</key><dict><key>PATH</key><string>$BIN:/opt/homebrew/bin:/usr/bin:/bin</string></dict>
 <key>StartCalendarInterval</key><dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>35</integer></dict>
 <key>RunAtLoad</key><true/>
 <key>StandardOutPath</key><string>$HOME/Library/Logs/viagens-motor-saude.out</string>
 <key>StandardErrorPath</key><string>$HOME/Library/Logs/viagens-motor-saude.out</string>
</dict></plist>
EOF
  launchctl bootout "gui/$(id -u)" "$P" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$P"
fi
echo "instalado em $VENV"
