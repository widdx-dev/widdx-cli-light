#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# WIDDX Nexus — Installer
# ═══════════════════════════════════════════════════════════════

BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { printf "${CYAN}  ⊙${NC} %s\n" "$*"; }
ok()    { printf "${GREEN}  ✓${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}  ⚠${NC} %s\n" "$*"; }
fail()  { printf "${RED}  ✗${NC} %s\n" "$*"; exit 1; }

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${WIDDX_VENV:-$HOME/.widdx/venv}"
BIN_DIR="${WIDDX_BIN:-$HOME/.local/bin}"
CONFIG_DIR="${WIDDX_CONFIG:-$HOME/.config/widdx}"

echo ""
printf "${BOLD}╔════════════════════════════════════════╗${NC}\n"
printf "${BOLD}║     WIDDX Nexus — Installation         ║${NC}\n"
printf "${BOLD}╚════════════════════════════════════════╝${NC}\n"
echo ""

# ── 1. Check Python ──
info "Checking Python..."
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PY_VER="$($cmd --version 2>&1 | grep -oP '\d+\.\d+')"
        PY_MAJOR="${PY_VER%.*}"
        if [ "$PY_MAJOR" -ge 3 ] && [ "${PY_VER#*.}" -ge 10 ] 2>/dev/null; then
            PYTHON="$cmd"
            break
        fi
    fi
done
[ -z "$PYTHON" ] && fail "Python >=3.10 required (not found). Install it first."
ok "Found $($PYTHON --version)"

# ── 2. Create venv ──
info "Setting up virtual environment..."
mkdir -p "$(dirname "$VENV_DIR")"
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    $PYTHON -m venv "$VENV_DIR"
    ok "Virtual environment created at $VENV_DIR"
else
    ok "Virtual environment already exists"
fi

source "$VENV_DIR/bin/activate"

# ── 3. Upgrade pip ──
info "Upgrading pip..."
$PYTHON -m pip install --quiet --upgrade pip
ok "pip upgraded"

# ── 4. Install WIDDX ──
info "Installing WIDDX Nexus..."
cd "$PROJECT_DIR"
$PYTHON -m pip install --quiet -e ".[api]" 2>&1 | grep -v 'already satisfied' || true
ok "WIDDX Nexus installed"

# ── 5. Create symlinks ──
info "Creating CLI wrappers..."
mkdir -p "$BIN_DIR"
WRAPPER='#!/usr/bin/env bash
VENV="'"$VENV_DIR"'"
export WIDDX_ROOT="'"$PROJECT_DIR"'"
source "$VENV/bin/activate" 2>/dev/null
exec '"$PYTHON"' -c "from core.cli import run; run()" "$@"
'
echo "$WRAPPER" > "$BIN_DIR/widdx"
chmod +x "$BIN_DIR/widdx"

WRAPPER_TUI='#!/usr/bin/env bash
VENV="'"$VENV_DIR"'"
export WIDDX_ROOT="'"$PROJECT_DIR"'"
source "$VENV/bin/activate" 2>/dev/null
exec '"$PYTHON"' -c "from tui.app import run_tui; run_tui()" "$@"
'
echo "$WRAPPER_TUI" > "$BIN_DIR/widdx-tui"
chmod +x "$BIN_DIR/widdx-tui"

WRAPPER_WEB='#!/usr/bin/env bash
VENV="'"$VENV_DIR"'"
export WIDDX_ROOT="'"$PROJECT_DIR"'"
source "$VENV/bin/activate" 2>/dev/null
exec '"$PYTHON"' -m scripts.web_app "$@"
'
echo "$WRAPPER_WEB" > "$BIN_DIR/widdx-web"
chmod +x "$BIN_DIR/widdx-web"

WRAPPER_API='#!/usr/bin/env bash
VENV="'"$VENV_DIR"'"
export WIDDX_ROOT="'"$PROJECT_DIR"'"
source "$VENV/bin/activate" 2>/dev/null
exec '"$PYTHON"' -m scripts.api_server "$@"
'
echo "$WRAPPER_API" > "$BIN_DIR/widdx-api"
chmod +x "$BIN_DIR/widdx-api"

ok "Wrappers created in $BIN_DIR"

# ── 6. Shell completion ──
info "Setting up shell completion..."

SHELL_RC=""
case "$SHELL" in
    *zsh) SHELL_RC="$HOME/.zshrc" ;;
    *bash) SHELL_RC="$HOME/.bashrc" ;;
esac

if [ -n "$SHELL_RC" ]; then
    LINE="export PATH=\"\$PATH:$BIN_DIR\""
    if ! grep -qF "$LINE" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# WIDDX" >> "$SHELL_RC"
        echo "$LINE" >> "$SHELL_RC"
        ok "Added $BIN_DIR to PATH in $SHELL_RC"
    else
        ok "$BIN_DIR already in PATH"
    fi
else
    warn "Unknown shell ($SHELL). Add $BIN_DIR to your PATH manually."
fi

# ── 7. Create default config ──
info "Creating default config..."
mkdir -p "$CONFIG_DIR"
CONFIG_FILE="$CONFIG_DIR/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" << 'PYEOF'
{
    "provider": "opencode",
    "model": "opencode-zen",
    "api_key": "",
    "temperature": 0.7,
    "max_tokens": 4096,
    "theme": "dark",
    "language": "auto"
}
PYEOF
    ok "Default config created at $CONFIG_FILE"
    warn "⚠  Edit $CONFIG_FILE and set your API key if using a paid provider"
    warn "    Default provider is 'opencode' (free, no API key needed)"
else
    ok "Config already exists"
fi

# ── 8. Verify ──
info "Verifying installation..."
if "$BIN_DIR/widdx" --help 2>/dev/null | head -5; then
    ok "WIDDX CLI works!"
else
    warn "CLI test produced no output (expected if running interactively)"
fi

echo ""
printf "${BOLD}╔════════════════════════════════════════╗${NC}\n"
printf "${BOLD}║        Installation Complete!          ║${NC}\n"
printf "${BOLD}╚════════════════════════════════════════╝${NC}\n"
echo ""
printf "  ${GREEN}▶${NC} %-20s ${CYAN}%s${NC}\n" "CLI:"      "widdx"
printf "  ${GREEN}▶${NC} %-20s ${CYAN}%s${NC}\n" "TUI:"      "widdx-tui"
printf "  ${GREEN}▶${NC} %-20s ${CYAN}%s${NC}\n" "Web UI:"   "widdx-web"
printf "  ${GREEN}▶${NC} %-20s ${CYAN}%s${NC}\n" "API:"      "widdx-api"
echo ""
printf "  ${YELLOW}⚡${NC} First run: ${BOLD}widdx${NC}\n"
printf "  ${YELLOW}⚡${NC} Config:    ${BOLD}%s${NC}\n" "$CONFIG_FILE"
printf "  ${YELLOW}⚡${NC} Restart your terminal or run: ${BOLD}source %s${NC}\n" "$SHELL_RC"
echo ""

# Optional extras
printf "${BOLD}Optional extras:${NC}\n"
printf "  ${CYAN}pip install -e \"%s[dev]\"${NC}       — development tools\n" "$PROJECT_DIR"
printf "  ${CYAN}pip install -e \"%s[gguf]\"${NC}      — local GGUF models\n" "$PROJECT_DIR"
printf "  ${CYAN}pip install -e \"%s[voice]\"${NC}      — voice (TTS)\n" "$PROJECT_DIR"
printf "  ${CYAN}pip install -e \"%s[all]\"${NC}        — everything\n" "$PROJECT_DIR"
echo ""
