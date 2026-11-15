# Package the game assets kept in this repository (menus, HUDs, configs,
# fonts and so on) and the QVM game modules as a pk3, so that builds and
# installers carry the versions that match the code. The name sorts after
# the pk3s of the original game data, which gives these files precedence.
#
# The QVMs have to be in a pk3 to be usable at all on a pure server, which is
# the default: there the engine only loads game modules from the pk3s that
# the server lists.

set(ASSETS_DIR ${CMAKE_SOURCE_DIR}/assets)
set(ASSETS_PK3_NAME zz-${CLIENT_NAME}-assets.pk3)
set(ASSETS_PK3_DIR ${CMAKE_BINARY_DIR}/$<CONFIG>/${BASEGAME})
set(ASSETS_PK3 ${ASSETS_PK3_DIR}/${ASSETS_PK3_NAME})
set(ASSETS_STAGING_DIR ${CMAKE_BINARY_DIR}/assets.dir/$<CONFIG>)

file(GLOB_RECURSE ASSETS_FILES CONFIGURE_DEPENDS ${ASSETS_DIR}/*)

if(BUILD_GAME_QVMS)
    set(ASSETS_QVM_TARGETS
        ${CGAME_MODULE_QVM_BASEGAME} ${GAME_MODULE_QVM_BASEGAME} ${UI_MODULE_QVM_BASEGAME})
    set(ASSETS_QVM_FILES
        ${ASSETS_PK3_DIR}/vm/${CGAME_MODULE}.qvm
        ${ASSETS_PK3_DIR}/vm/${GAME_MODULE}.qvm
        ${ASSETS_PK3_DIR}/vm/${UI_MODULE}.qvm)
    set(ASSETS_COPY_QVMS
        COMMAND ${CMAKE_COMMAND} -E make_directory ${ASSETS_STAGING_DIR}/vm
        COMMAND ${CMAKE_COMMAND} -E copy ${ASSETS_QVM_FILES} ${ASSETS_STAGING_DIR}/vm)
endif()

add_custom_command(
    OUTPUT ${ASSETS_PK3}
    COMMAND ${CMAKE_COMMAND} -E rm -rf ${ASSETS_STAGING_DIR}
    COMMAND ${CMAKE_COMMAND} -E copy_directory ${ASSETS_DIR} ${ASSETS_STAGING_DIR}
    ${ASSETS_COPY_QVMS}
    COMMAND ${CMAKE_COMMAND} -E make_directory ${ASSETS_PK3_DIR}
    COMMAND ${CMAKE_COMMAND} -E chdir ${ASSETS_STAGING_DIR}
        ${CMAKE_COMMAND} -E tar cf ${ASSETS_PK3} --format=zip -- .
    DEPENDS ${ASSETS_FILES} ${ASSETS_QVM_FILES} ${ASSETS_QVM_TARGETS}
    COMMENT "Packaging ${BASEGAME}/${ASSETS_PK3_NAME}")

add_custom_target(assets_pk3 ALL DEPENDS ${ASSETS_PK3})

install(FILES ${ASSETS_PK3} DESTINATION ${BASEGAME})

# The original game data is not part of this repository. If a directory with
# its pk3s is given, as fetched by misc/fetch-game-data.sh, they are put in
# the build and in the installers, which makes those complete games.
set(GAME_DATA_DIR "" CACHE PATH "Directory with the game data pk3s to bundle")

if(GAME_DATA_DIR)
    # A relative path is taken to be relative to the top of the source tree
    get_filename_component(GAME_DATA_DIR_ABSOLUTE "${GAME_DATA_DIR}"
        ABSOLUTE BASE_DIR "${CMAKE_SOURCE_DIR}")
    file(GLOB GAME_DATA_FILES ${GAME_DATA_DIR_ABSOLUTE}/*.pk3)

    if(NOT GAME_DATA_FILES)
        message(FATAL_ERROR "No pk3s found in GAME_DATA_DIR (${GAME_DATA_DIR})")
    endif()

    set(GAME_DATA_STAMP ${CMAKE_BINARY_DIR}/assets.dir/$<CONFIG>.game-data.stamp)

    add_custom_command(
        OUTPUT ${GAME_DATA_STAMP}
        COMMAND ${CMAKE_COMMAND} -E make_directory ${ASSETS_PK3_DIR} ${CMAKE_BINARY_DIR}/assets.dir
        COMMAND ${CMAKE_COMMAND} -E copy_if_different ${GAME_DATA_FILES} ${ASSETS_PK3_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${GAME_DATA_STAMP}
        DEPENDS ${GAME_DATA_FILES}
        COMMENT "Copying the game data to ${BASEGAME}")

    add_custom_target(game_data ALL DEPENDS ${GAME_DATA_STAMP})

    install(FILES ${GAME_DATA_FILES} DESTINATION ${BASEGAME})
endif()
