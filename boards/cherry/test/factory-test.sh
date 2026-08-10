#!/usr/bin/env bash
set -Eeuo pipefail
[[ -n ${1:-} ]] || { echo "usage: $0 <factory-image.bin>"; exit 2; }
command -v iceprog >/dev/null || { echo "iceprog not found"; exit 2; }
command -v lsusb >/dev/null || { echo "lsusb not found"; exit 2; }
[[ -s "$1" ]] || { echo "image missing: $1"; exit 2; }
: "${CHERRY_USB_ID:?set CHERRY_USB_ID=vvvv:pppp}"
args=(); [[ -n ${ICEPROG_DEVICE:-} ]] && args=(-d "$ICEPROG_DEVICE")
iceprog "${args[@]}" -I "${ICEPROG_INTERFACE:-A}" -k "$1"
end=$((SECONDS+${CHERRY_USB_TIMEOUT:-15}))
while ((SECONDS<end)); do lsusb -d "$CHERRY_USB_ID" | grep -q . && { echo "PASS: Cherry USB enumerated"; exit 0; }; sleep .25; done
echo "FAIL: Cherry USB did not enumerate" >&2; exit 1

