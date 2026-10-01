#!/usr/bin/env bash
# Install Sanguine: puts `sanguine` on your PATH and adds a launcher entry.
#
#   ./install.sh              install or update
#   ./install.sh --uninstall  remove the command and launcher (keeps your save)
#
# The game runs fully offline. The only thing that may need a network is pip, and only if
# Textual is not already installed system-wide (Arch: `sudo pacman -S python-textual`).
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP="$APPS/sanguine.desktop"
say() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

if [[ ${1:-} == --uninstall ]]; then
  say "removing sanguine (your save in ~/.local/share/sanguine is kept)"
  pipx uninstall sanguine 2>/dev/null || true
  rm -f "$DESKTOP"
  command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true
  exit 0
fi

command -v python3 >/dev/null || die "python3 is required"
command -v pipx >/dev/null || die "pipx is required (sudo pacman -S python-pipx)"

# Reuse system Textual when present, so install needs no network.
FLAGS=()
if python3 -c 'import textual' 2>/dev/null; then
  FLAGS+=(--system-site-packages)
  say "using system Textual $(python3 -c 'import textual; print(textual.__version__)')"
else
  say "Textual not found system-wide; pipx will download it"
fi

say "installing the sanguine command"
# Uninstall first: with pipx's uv backend, --force will not replace an existing environment.
pipx uninstall sanguine >/dev/null 2>&1 || true
pipx install "${FLAGS[@]}" "$SRC" >/dev/null || die "pipx install failed"

BIN="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "$HOME/.local/bin")"
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) say "note: $BIN is not on your PATH; run 'pipx ensurepath' and restart your shell" ;;
esac

# Launcher: Omarchy's floating TUI window (TUI.float is floated by the default window rules).
if command -v omarchy-launch-tui >/dev/null; then
  LAUNCH="omarchy-launch-tui --app-id=TUI.float sanguine"
else
  LAUNCH="xdg-terminal-exec sanguine"
fi
mkdir -p "$APPS"
sed "s|@LAUNCH@|$LAUNCH|" "$SRC/packaging/sanguine.desktop" > "$DESKTOP"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true

command -v sanguine >/dev/null || die "installed, but 'sanguine' is not on PATH ($BIN)"
say "done: $(sanguine --version)"
echo "  run:       sanguine"
echo "  launcher:  search 'Sanguine' in the Omarchy menu (Super+Space)"
echo "  bar:       sanguine --waybar   (see README)"
