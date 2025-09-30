#!/usr/bin/env bash
set -euo pipefail

RESTORE_VENV="./venv-photofix-restore"
DIFFUSE_VENV="./venv-photofix-diffuse"
INP="${1:?usage: ./orchestrate.sh path/to/photo.jpg}"
OUTDIR="${2:-outputs}"

source "$RESTORE_VENV/bin/activate"
python scripts/restore_generate.py "$INP" "$OUTDIR"
deactivate

source "$DIFFUSE_VENV/bin/activate"
python scripts/diffuse_colorize.py "$OUTDIR/01_upscaled.png" "$OUTDIR"
deactivate

source "$RESTORE_VENV/bin/activate"
python scripts/contact_sheet.py "$OUTDIR" "$OUTDIR/contact_sheet.jpg"
deactivate

echo "Done -> $OUTDIR/contact_sheet.jpg"
