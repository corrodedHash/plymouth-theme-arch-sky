#!/usr/bin/env bash
# Install the arch-sky Plymouth theme.
#
# Usage:
#   sudo ./install.sh                 # install and rebuild the initramfs
#   sudo ./install.sh --no-rebuild    # install only
#   sudo ./install.sh --no-uki-splash # also drop the static UKI splash image
#
# The static UKI splash is the Arch bitmap that systemd-stub shows while the
# 180+ MB unified kernel image is loaded and verified.  It has no timeout: it
# stays on screen until the kernel takes over.  Passing --no-uki-splash removes
# the "--splash ..." option from /etc/mkinitcpio.d/linux.preset so Plymouth's
# animated splash is the only splash art.

set -euo pipefail

THEME_NAME="arch-sky"
THEME_ROOT="/usr/share/plymouth/themes/${THEME_NAME}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REBUILD=1
DROP_UKI_SPLASH=0

for arg in "$@"; do
    case "$arg" in
        --no-rebuild) REBUILD=0 ;;
        --no-uki-splash) DROP_UKI_SPLASH=1 ;;
        -h|--help)
            sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            exit 2
            ;;
    esac
done

if [[ ${EUID} -ne 0 ]]; then
    echo "Run this with sudo." >&2
    exit 1
fi

if [[ ! -f "${SCRIPT_DIR}/arch-sky.script" || ! -d "${SCRIPT_DIR}/assets" ]]; then
    echo "Theme files are missing next to this script (${SCRIPT_DIR})." >&2
    exit 1
fi

if ! command -v plymouth-set-default-theme >/dev/null; then
    echo "plymouth-set-default-theme not found; is plymouth installed?" >&2
    exit 1
fi

echo "==> Installing ${THEME_NAME} into ${THEME_ROOT}"
install -d -m 755 "${THEME_ROOT}"
install -m 644 "${SCRIPT_DIR}/arch-sky.plymouth" "${THEME_ROOT}/arch-sky.plymouth"
install -m 644 "${SCRIPT_DIR}/arch-sky.script" "${THEME_ROOT}/arch-sky.script"
install -m 644 "${SCRIPT_DIR}"/assets/*.png "${THEME_ROOT}/"

if [[ -f /etc/plymouth/plymouthd.conf && ! -f /etc/plymouth/plymouthd.conf.bak-arch-sky ]]; then
    cp -a /etc/plymouth/plymouthd.conf /etc/plymouth/plymouthd.conf.bak-arch-sky
    echo "==> Backed up /etc/plymouth/plymouthd.conf"
fi

if [[ ${DROP_UKI_SPLASH} -eq 1 ]]; then
    preset="/etc/mkinitcpio.d/linux.preset"
    if [[ -f ${preset} ]]; then
        if ! grep -q -- '--splash' "${preset}"; then
            echo "==> ${preset} has no --splash option; nothing to remove"
        else
            if [[ ! -f ${preset}.bak-arch-sky ]]; then
                cp -a "${preset}" "${preset}.bak-arch-sky"
            fi
            sed -i -E 's@[[:space:]]*--splash[[:space:]]+[^"[:space:]]+@@g' "${preset}"
            echo "==> Removed the static UKI splash from ${preset}"
            echo "    (backup: ${preset}.bak-arch-sky)"
        fi
    else
        echo "==> ${preset} not found; skipping UKI splash change"
    fi
fi

if [[ ${REBUILD} -eq 1 ]]; then
    echo "==> Selecting ${THEME_NAME} and rebuilding the initramfs"
    plymouth-set-default-theme -R "${THEME_NAME}"
else
    plymouth-set-default-theme "${THEME_NAME}"
    echo "==> Theme selected. Rebuild the initramfs before rebooting:"
    echo "    sudo mkinitcpio -P"
fi

echo
echo "==> Done. Current theme: $(plymouth-set-default-theme)"

if command -v lsinitcpio >/dev/null && [[ -f /boot/EFI/Linux/arch-linux.efi ]]; then
    if lsinitcpio /boot/EFI/Linux/arch-linux.efi 2>/dev/null | grep -q "themes/${THEME_NAME}/arch-sky.script"; then
        echo "==> Verified: the theme is inside the default UKI"
    else
        echo "!!  Warning: ${THEME_NAME} was not found inside the default UKI" >&2
    fi
fi

cat <<EOF

Rollback:
  sudo plymouth-set-default-theme -R script
  # the old daemon config is at /etc/plymouth/plymouthd.conf.bak-arch-sky

To restore the static UKI splash:
  sudo cp -a /etc/mkinitcpio.d/linux.preset.bak-arch-sky /etc/mkinitcpio.d/linux.preset
  sudo mkinitcpio -P

Preview the theme's layout:
  ${SCRIPT_DIR}/preview.png
EOF
