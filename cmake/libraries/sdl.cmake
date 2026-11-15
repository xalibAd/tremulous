if(NOT BUILD_CLIENT)
    return()
endif()

if(EMSCRIPTEN)
    # Emscripten provides its own self contained SDL setup
    list(APPEND CLIENT_COMPILE_OPTIONS -sUSE_SDL=2)
    list(APPEND CLIENT_LINK_OPTIONS -sUSE_SDL=2)
    return()
endif()

include(utils/arch)

if(WIN32 OR APPLE)
    # On Windows and macOS we have internal SDL binaries we can use
    set(HAVE_INTERNAL_SDL true)
endif()

if(USE_SDL3)
    set(INTERNAL_SDL3_DIR ${SOURCE_DIR}/thirdparty/SDL3-${SDL3_VERSION})

    if(USE_INTERNAL_SDL AND HAVE_INTERNAL_SDL)
        set(SDL3_INCLUDE_DIRS ${INTERNAL_SDL3_DIR}/include)

        if(WIN32)
            if(ARCH STREQUAL "x86_64")
                set(LIB_DIR ${SOURCE_DIR}/thirdparty/libs/win64)
            elseif(ARCH STREQUAL "x86")
                set(LIB_DIR ${SOURCE_DIR}/thirdparty/libs/win32)
            else()
                message(FATAL_ERROR "Unknown ARCH")
            endif()

            if(MINGW)
                set(SDL3_LIBRARIES ${LIB_DIR}/libSDL3.dll.a)
            elseif(MSVC)
                set(SDL3_LIBRARIES ${LIB_DIR}/SDL3.lib)
            endif()

            list(APPEND CLIENT_DEPLOY_LIBRARIES ${LIB_DIR}/SDL3.dll)
        elseif(APPLE)
            set(SDL3_LIBRARIES ${SOURCE_DIR}/thirdparty/libs/macos/libSDL3.0.dylib)
            list(APPEND CLIENT_DEPLOY_LIBRARIES ${SDL3_LIBRARIES})

            # The library is the one from the official SDL3 framework, which
            # expects to be found in a framework bundle. As it is deployed
            # next to the executable instead, point the binaries that link
            # to it there. This has to happen before they are code signed.
            list(PREPEND POST_CONFIGURE_FUNCTIONS fix_sdl3_install_name)

            function(fix_sdl3_install_name)
                foreach(TARGET IN ITEMS
                        ${CLIENT_BINARY} ${RENDERER_GL1_BINARY} ${RENDERER_GL2_BINARY})
                    if(NOT TARGET ${TARGET})
                        continue()
                    endif()

                    add_custom_command(TARGET ${TARGET} POST_BUILD
                        COMMAND install_name_tool -change
                            @rpath/SDL3.framework/Versions/A/SDL3
                            @executable_path/libSDL3.0.dylib
                            "$<TARGET_FILE:${TARGET}>"
                        COMMENT "Fixing SDL3 install name: $<TARGET_FILE_NAME:${TARGET}>")
                endforeach()
            endfunction()
        else()
            message(FATAL_ERROR "HAVE_INTERNAL_SDL set incorrectly; file a bug")
        endif()

        set(SDL3_FOUND true)
    else()
        find_package(SDL3 CONFIG QUIET)

        if(SDL3_FOUND)
            set(SDL3_LIBRARIES SDL3::SDL3)
        else()
            message(WARNING "SDL3 was not found, falling back to SDL2. "
                "Install SDL3, or set USE_SDL3 to OFF to silence this.")
        endif()
    endif()

    if(SDL3_FOUND)
        set(SDL_SOURCE_DIR ${SOURCE_DIR}/sdl3)

        list(APPEND CLIENT_DEFINITIONS USE_SDL3)
        list(APPEND RENDERER_DEFINITIONS USE_SDL3)
        list(APPEND CLIENT_LIBRARIES ${SDL3_LIBRARIES})
        list(APPEND CLIENT_INCLUDE_DIRS ${SDL3_INCLUDE_DIRS})
        list(APPEND RENDERER_LIBRARIES ${SDL3_LIBRARIES})
        list(APPEND RENDERER_INCLUDE_DIRS ${SDL3_INCLUDE_DIRS})
        return()
    endif()
endif()

set(INTERNAL_SDL_DIR ${SOURCE_DIR}/thirdparty/SDL2-${SDL_VERSION})

if(USE_INTERNAL_SDL AND HAVE_INTERNAL_SDL)
    set(SDL2_INCLUDE_DIRS ${INTERNAL_SDL_DIR}/include)
    list(APPEND CLIENT_DEFINITIONS USE_INTERNAL_SDL_HEADERS)
    list(APPEND RENDERER_DEFINITIONS USE_INTERNAL_SDL_HEADERS)

    if(WIN32)
        if(ARCH STREQUAL "x86_64")
            set(LIB_DIR ${SOURCE_DIR}/thirdparty/libs/win64)
        elseif(ARCH STREQUAL "x86")
            set(LIB_DIR ${SOURCE_DIR}/thirdparty/libs/win32)
        else()
            message(FATAL_ERROR "Unknown ARCH")
        endif()

        if(MINGW)
            set(SDL2_LIBRARIES
                ${LIB_DIR}/libSDL2main.a
                ${LIB_DIR}/libSDL2.dll.a)
        elseif(MSVC)
            set(SDL2_LIBRARIES
                ${LIB_DIR}/SDL2main.lib
                ${LIB_DIR}/SDL2.lib)
        endif()

        list(APPEND CLIENT_DEPLOY_LIBRARIES ${LIB_DIR}/SDL2.dll)
    elseif(APPLE)
        set(SDL2_LIBRARIES
            ${SOURCE_DIR}/thirdparty/libs/macos/libSDL2main.a
            ${SOURCE_DIR}/thirdparty/libs/macos/libSDL2-2.0.0.dylib)
        list(APPEND CLIENT_DEPLOY_LIBRARIES
            ${SOURCE_DIR}/thirdparty/libs/macos/libSDL2-2.0.0.dylib)
    else()
        message(FATAL_ERROR "HAVE_INTERNAL_SDL set incorrectly; file a bug")
    endif()
else()
    find_package(SDL2 REQUIRED)
endif()

list(APPEND CLIENT_LIBRARIES ${SDL2_LIBRARIES})
list(APPEND CLIENT_INCLUDE_DIRS ${SDL2_INCLUDE_DIRS})
list(APPEND CLIENT_COMPILE_OPTIONS ${SDL2_CFLAGS_OTHER})
list(APPEND RENDERER_LIBRARIES ${SDL2_LIBRARIES})
list(APPEND RENDERER_INCLUDE_DIRS ${SDL2_INCLUDE_DIRS})
list(APPEND RENDERER_COMPILE_OPTIONS ${SDL2_CFLAGS_OTHER})
