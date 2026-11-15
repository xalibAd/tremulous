#!/bin/bash

# Download the original Tremulous game data (maps, models, textures, sounds)
# and put its pk3s in a directory. The data is not kept in this repository;
# it is the unmodified content of the official 1.1.0 release and of the GPP1
# update, distributed under the Creative Commons license in the CC file.
#
# Pass the directory to CMake as GAME_DATA_DIR to have the data bundled with
# the build and the installers, or copy the pk3s to the base directory of an
# existing build.
#
# Usage: fetch-game-data.sh <destination directory>

set -e

DEST="$1"

if [ -z "${DEST}" ]
then
    echo "Usage: $0 <destination directory>"
    exit 1
fi

BASE_URL="https://downloads.sourceforge.net/project/tremulous/tremulous"

# <path below BASE_URL> <sha256>
ARCHIVES="
1.1/tremulous-1.1.0.zip c7bb66f55abc88932edee16c253e5d37f90dded2ce29cf6cb15ad4f78e378987
gpp/tremulous-gpp1.zip 983e1d551b62d9c68b190699fbcef510ca6953d12bf182441d8198d4c72604bd
"

mkdir -p "${DEST}"
DEST="$(cd "${DEST}" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

echo "${ARCHIVES}" | while read -r ARCHIVE_PATH SHA256
do
    [ -z "${ARCHIVE_PATH}" ] && continue

    FILE="${WORK}/$(basename "${ARCHIVE_PATH}")"

    echo "Downloading ${ARCHIVE_PATH}"
    curl -sSfL --retry 5 --retry-delay 5 -o "${FILE}" "${BASE_URL}/${ARCHIVE_PATH}"

    if ! echo "${SHA256}  ${FILE}" | sha256sum -c - > /dev/null
    then
        echo "${ARCHIVE_PATH} does not have the expected checksum"
        exit 1
    fi

    # Everything but the old game modules; the ones that match this code are
    # built from it
    unzip -q -o -j "${FILE}" "*.pk3" -x "*/vms-*.pk3" -d "${DEST}"
done

echo "Game data in ${DEST}:"
ls -l "${DEST}"/*.pk3
