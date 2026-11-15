# Package the game assets kept in this repository (menus, HUDs, configs,
# fonts and so on) as a pk3, so that builds and installers carry the versions
# that match the code. The name sorts after the pk3s of the original game
# data, which gives these files precedence over the ones in there.

set(ASSETS_DIR ${CMAKE_SOURCE_DIR}/assets)
set(ASSETS_PK3_NAME zz-${CLIENT_NAME}-assets.pk3)
set(ASSETS_PK3_DIR ${CMAKE_BINARY_DIR}/$<CONFIG>/${BASEGAME})
set(ASSETS_PK3 ${ASSETS_PK3_DIR}/${ASSETS_PK3_NAME})

file(GLOB ASSETS_TOP_LEVEL RELATIVE ${ASSETS_DIR} ${ASSETS_DIR}/*)
file(GLOB_RECURSE ASSETS_FILES CONFIGURE_DEPENDS ${ASSETS_DIR}/*)

add_custom_command(
    OUTPUT ${ASSETS_PK3}
    COMMAND ${CMAKE_COMMAND} -E make_directory ${ASSETS_PK3_DIR}
    COMMAND ${CMAKE_COMMAND} -E tar cf ${ASSETS_PK3} --format=zip -- ${ASSETS_TOP_LEVEL}
    WORKING_DIRECTORY ${ASSETS_DIR}
    DEPENDS ${ASSETS_FILES}
    COMMENT "Packaging ${BASEGAME}/${ASSETS_PK3_NAME}")

add_custom_target(assets_pk3 ALL DEPENDS ${ASSETS_PK3})

install(FILES ${ASSETS_PK3} DESTINATION ${BASEGAME})
