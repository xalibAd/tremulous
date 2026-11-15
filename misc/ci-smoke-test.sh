#!/bin/sh

# Start the dedicated server and the client from a build directory and check
# that they come up and shut down cleanly. This runs without the game data,
# which is not part of the repository, so it only gets as far as the main
# menu; that is enough to exercise startup, the renderer, the assets pk3,
# the UI module and font rendering.
#
# Usage: ci-smoke-test.sh <directory containing the binaries> [renderer]

set -e

BIN_DIR="$(cd "$1" && pwd)"
RENDERER="${2:-opengl2}"
HOME_DIR="$(mktemp -d)"
LOG="${HOME_DIR}/client.log"

# The default config normally comes with the game data
mkdir -p "${HOME_DIR}/base"
echo "// placeholder" > "${HOME_DIR}/base/default.cfg"

echo "--- Dedicated server"
timeout 60 "${BIN_DIR}/tremded" \
    +set fs_homepath "${HOME_DIR}" +set dedicated 1 +set net_enabled 0 \
    +wait 20 +quit

echo "--- Client (${RENDERER})"
SDL_AUDIODRIVER=dummy timeout 180 xvfb-run -a -s "-screen 0 1280x720x24" \
    "${BIN_DIR}/tremulous" \
    +set fs_homepath "${HOME_DIR}" +set cl_renderer "${RENDERER}" \
    +set r_fullscreen 0 +set s_useOpenAL 0 +set net_enabled 0 \
    +set developer 1 +wait 60 +quit > "${LOG}" 2>&1 || {
        tail -n 60 "${LOG}"
        echo "The client did not exit cleanly"
        exit 1
    }

for EXPECTED in "zz-tremulous-assets.pk3" "RE_RegisterFont: rasterized" "ui/menus.txt"
do
    if ! grep -q "${EXPECTED}" "${LOG}"
    then
        tail -n 60 "${LOG}"
        echo "Expected '${EXPECTED}' in the client's output"
        exit 1
    fi
done

echo "--- OK"
rm -rf "${HOME_DIR}"
