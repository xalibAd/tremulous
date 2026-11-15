#!/bin/sh

# Start the dedicated server and the client from a build directory and check
# that they come up and shut down cleanly. Without the game data, which is
# not part of the repository, this only gets as far as the main menu; that
# is enough to exercise startup, the renderer, the assets pk3, the UI module
# and font rendering. If the build has the game data and a map is given,
# the client also starts a local game on that map.
#
# Usage: ci-smoke-test.sh <directory containing the binaries> [renderer] [map]

set -e

BIN_DIR="$(cd "$1" && pwd)"
RENDERER="${2:-opengl2}"
MAP="$3"
HOME_DIR="$(mktemp -d)"
LOG="${HOME_DIR}/client.log"

EXPECTED_OUTPUT="zz-tremulous-assets.pk3|RE_RegisterFont: rasterized|ui/menus.txt"

if [ -n "${MAP}" ]
then
    START_MAP="+devmap ${MAP} +wait 100"
    EXPECTED_OUTPUT="${EXPECTED_OUTPUT}|entered the game"
else
    # The default config normally comes with the game data
    mkdir -p "${HOME_DIR}/base"
    echo "// placeholder" > "${HOME_DIR}/base/default.cfg"
fi

echo "--- Dedicated server"
timeout 60 "${BIN_DIR}/tremded" \
    +set fs_homepath "${HOME_DIR}" +set dedicated 1 +set net_enabled 0 \
    +wait 20 +quit

echo "--- Client (${RENDERER}${MAP:+, map ${MAP}})"
SDL_AUDIODRIVER=dummy timeout 180 xvfb-run -a -s "-screen 0 1280x720x24" \
    "${BIN_DIR}/tremulous" \
    +set fs_homepath "${HOME_DIR}" +set cl_renderer "${RENDERER}" \
    +set r_fullscreen 0 +set s_useOpenAL 0 +set net_enabled 0 \
    +set developer 1 +wait 60 ${START_MAP} +quit > "${LOG}" 2>&1 || {
        tail -n 60 "${LOG}"
        echo "The client did not exit cleanly"
        exit 1
    }

echo "${EXPECTED_OUTPUT}" | tr '|' '\n' | while read -r EXPECTED
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
