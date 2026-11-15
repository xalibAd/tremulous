#!/bin/bash

# Compare the versions of the bundled libraries in lib-versions.sh with the
# newest release tags upstream. The libraries are bundled as source or
# binaries rather than through a package manager, so nothing else notices
# when they fall behind. This only reports; it does not fail.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

. "${SCRIPT_DIR}/lib-versions.sh"

OUTDATED=0
SUMMARY="| Library | Bundled | Latest | |\n| --- | --- | --- | --- |\n"

# check <name> <bundled version> <repository> <sed expression turning a
#       release tag into a version; other tags must come out empty>
check()
{
    local NAME="$1" BUNDLED="$2" REPO="$3" EXPRESSION="$4"
    local LATEST STATUS

    LATEST=$(git ls-remote --tags --refs "https://github.com/${REPO}" 2>/dev/null |
        sed -e 's|.*refs/tags/||' | sed -n -E -e "${EXPRESSION}" | sort -V | tail -n1)

    if [ -z "${LATEST}" ]
    then
        STATUS="could not be checked"
        LATEST="?"
    elif [ "${LATEST}" = "${BUNDLED}" ]
    then
        STATUS="up to date"
    else
        STATUS="**outdated**"
        OUTDATED=$((OUTDATED + 1))
        echo "::warning title=Outdated bundled library::${NAME} ${BUNDLED} is bundled, ${LATEST} is available"
    fi

    printf '%-10s %-10s %-10s %s\n' "${NAME}" "${BUNDLED}" "${LATEST}" "${STATUS//\*/}"
    SUMMARY+="| ${NAME} | ${BUNDLED} | ${LATEST} | ${STATUS} |\n"
}

# SDL uses odd minor versions for development releases
check SDL2     "${SDL_VERSION}"      libsdl-org/SDL    's/^release-(2\.[0-9]*[02468]\.[0-9]+)$/\1/p'
check SDL3     "${SDL3_VERSION}"     libsdl-org/SDL    's/^release-(3\.[0-9]*[02468]\.[0-9]+)$/\1/p'
check libogg   "${OGG_VERSION}"      xiph/ogg          's/^v([0-9]+(\.[0-9]+)+)$/\1/p'
check vorbis   "${VORBIS_VERSION}"   xiph/vorbis       's/^v([0-9]+(\.[0-9]+)+)$/\1/p'
check opus     "${OPUS_VERSION}"     xiph/opus         's/^v([0-9]+(\.[0-9]+)+)$/\1/p'
check opusfile "${OPUSFILE_VERSION}" xiph/opusfile     's/^v([0-9]+(\.[0-9]+)+)$/\1/p'
check zlib     "${ZLIB_VERSION}"     madler/zlib       's/^v([0-9]+(\.[0-9]+)+)$/\1/p'
check curl     "${CURL_VERSION}"     curl/curl         's/^curl-([0-9]+)_([0-9]+)_([0-9]+)$/\1.\2.\3/p'
check openal   "${OPENAL_VERSION}"   kcat/openal-soft  's/^([0-9]+(\.[0-9]+)+)$/\1/p'

# libjpeg is released as tarballs only, so it cannot be checked this way
printf '%-10s %-10s %-10s %s\n' "libjpeg" "${JPEG_VERSION}" "?" "check https://www.ijg.org/ by hand"
SUMMARY+="| libjpeg | ${JPEG_VERSION} | ? | check https://www.ijg.org/ by hand |\n"

if [ -n "${GITHUB_STEP_SUMMARY}" ]
then
    {
        echo "### Bundled libraries: ${OUTDATED} outdated"
        echo
        echo -e "${SUMMARY}"
        echo "Update the versions in \`misc/lib-versions.sh\` and run \`misc/update-libs.sh\`."
    } >> "${GITHUB_STEP_SUMMARY}"
fi

exit 0
