# Tremulous

Tremulous is a free, open source first person shooter with real time strategy
elements. Two teams, humans and aliens, each build and defend a base while
trying to destroy the other's.

This repository is a fork of
[darklegion/tremulous](https://github.com/darklegion/tremulous), which is the
Tremulous game code on a current [ioquake3](https://github.com/ioquake/ioq3)
engine. The fork modernizes how the game looks, runs and is built and shipped,
without changing the gameplay or the network protocol.

## Getting the game

Every commit merged to `main` is published under
[Releases](../../releases) with packages for Windows, Linux and macOS:

| File | Platform |
| --- | --- |
| `*-windows-x86_64-installer.exe` | Windows installer |
| `*-windows-x86_64.zip` | Windows, unpack and run |
| `*-macos-universal.dmg` | macOS, Intel and Apple Silicon |
| `*-linux-x86_64.deb` | Debian and Ubuntu package |
| `*-linux-x86_64.tar.gz` | Linux, unpack and run |

These are complete games: they include the original game data, so there is
nothing else to download. `SHA256SUMS.txt` has the checksums.

Commits on the `development` branch are published the same way, marked as
prereleases, for testing changes before they reach `main`.

Notes:

- The macOS app is not code signed. Open it with right click > Open the first
  time.
- The Linux packages use the SDL2 library of the system
  (`sudo apt install libsdl2-2.0-0` on Debian and Ubuntu).
- A web build is published as well, but without the game data.

## What has changed since the fork

The fork point is upstream's `main` as of 28 August 2026. Everything below was
added on top of it.

### Display

- **Sharp text at any resolution.** Menu and HUD text is rendered from a
  TrueType font at the size it is drawn on screen, instead of being scaled up
  from bitmaps made for a 640x480 screen. The layout is unchanged. Rendering
  uses the bundled [stb_truetype](https://github.com/nothings/stb), so there
  is no new dependency. `r_scalableFonts 0` restores the bitmap fonts.
- **New default font.** [Saira Condensed](https://github.com/Omnibus-Type/Saira)
  (SIL Open Font License), chosen to match the width and character of the
  original font. Replace `assets/fonts/font.ttf` to use another typeface.
- **HiDPI.** On macOS Retina and scaled Wayland displays the game renders at
  the native pixel density (`r_allowHighDPI`, on by default).
- **Better default image quality.** 8x anisotropic filtering, and 4x
  anti-aliasing in the OpenGL 2 renderer.
- **Legible console.** The console text scales with the resolution
  (`con_scale 0`, the default; any other value sets the scale explicitly).

### Menus

- **Video options that matter today.** Renderer selection, borderless window,
  vertical sync, anti-aliasing and the anisotropic filtering level replace
  settings such as color depth, texture bit depth and vertex lighting.
- **Effects page** for the OpenGL 2 renderer: HDR, ambient occlusion, sun
  shadows and their resolution, normal and specular mapping.
- **Quality presets** Very High, High, Medium and Low, covering all of the
  above. High matches the engine defaults.
- **Desktop resolution** is always offered in the video mode list.
- **Gamepad page** in the controls: enable, analog movement and stick dead
  zone, which were previously only reachable from the console.

### Engine

- **SDL3.** The game uses SDL3 by default, through a port of the platform
  layer in `code/sdl3`. The SDL2 layer in `code/sdl` is untouched and still
  used where SDL3 is not available (see [Building](#building)).

  Differences under SDL3: fullscreen at the desktop resolution is a borderless
  window, toggling fullscreen restarts the renderer, and there is no hardware
  gamma, which makes the OpenGL 1 renderer darker in fullscreen than it was.
- **Updated bundled libraries**: SDL3 3.4.20, opus 1.6.1, zlib 1.4,
  curl 8.23.0 and OpenAL Soft 1.25.2.

### Fixes

- A crash when 32 messages were printed to the screen in quick succession,
  caused by reading past the end of an array. This is what made the game crash
  while loading a map with the released game data.
- Text width was measured from the wrong characters, which misplaced right
  aligned and centered text.
- The Mods and Quit entries of the main menu were on top of each other.
- Every weapon logged an error about a missing animation file when a map was
  loaded.

### Packaging

- **Assets are part of the build.** The menus, HUDs, configs and fonts in
  `assets/`, together with the QVM game modules, are packaged as
  `base/zz-tremulous-assets.pk3`. Previously nothing put them in to a build,
  and the game modules were loose files, which the engine does not load on a
  pure server, the default.
- **Game data can be bundled.** `misc/fetch-game-data.sh` downloads and
  verifies the original game data, and the `GAME_DATA_DIR` build option puts
  it in to the build and the installers.
- The Linux package installs to `/opt/tremulous`.

### Continuous integration

- **Builds** for Linux (64 and 32 bit, with SDL2 and SDL3), Windows (MSVC and
  MinGW), macOS, FreeBSD, OpenBSD and the web on every push and pull request.
- **Smoke test** on Linux: the dedicated server and the client are started
  under a virtual display, and a local game is started on a map with each
  renderer.
- **Releases** are published automatically for every push to `main`, and
  prereleases for every push to `development`.
- **Security and quality checks**: CodeQL, secret scanning with gitleaks,
  OSV-Scanner, dependency review, cppcheck, linting of the workflows and
  scripts, OpenSSF Scorecard, and a check of the bundled library versions
  against upstream. Dependabot keeps the GitHub Actions up to date.

## Building

The build needs CMake 3.25 or newer and a C compiler.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

The result is in `build/Release`. On Windows and macOS everything needed is
in the repository. On Linux, install the SDL development package first
(`sudo apt install libsdl2-dev` on Debian and Ubuntu). If SDL3 is installed
it is used; otherwise the build falls back to SDL2 with a warning.

To get a complete, playable build, fetch the game data and point the build at
it:

```sh
misc/fetch-game-data.sh game-data
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DGAME_DATA_DIR=game-data
cmake --build build
build/Release/tremulous
```

Options added by this fork:

| Option | Default | Meaning |
| --- | --- | --- |
| `USE_SDL3` | `ON` | Use SDL3 rather than SDL2 where it is available |
| `GAME_DATA_DIR` | empty | Directory with the game data pk3s to bundle |

The options inherited from ioquake3 are described in
[docs/ioq3-README.md](docs/ioq3-README.md).

### Maintenance scripts

| Script | Purpose |
| --- | --- |
| `misc/fetch-game-data.sh` | Download and verify the original game data |
| `misc/update-libs.sh` | Update the bundled libraries to the versions in `misc/lib-versions.sh` |
| `misc/check-lib-versions.sh` | Compare the bundled library versions with upstream releases |
| `misc/ci-smoke-test.sh` | Start the server and the client and check that they come up |

## Known limitations

- The newest released game data (GPP1, from 2009) is older than the code. The
  game runs with it, but content that was added to the code afterwards and
  never released as data is missing.
- The Windows and macOS packages are built and packaged by CI but not started
  there; only the Linux build is run automatically.
- Under SDL3, real fullscreen mode switching, audio capture for voice chat and
  gamepads have not been tested on real hardware.
- SDL2 stays at 2.32.8, as its bundled macOS library cannot be regenerated
  from the official release.

## License

The code is licensed under the GNU General Public License, version 2 or later
(see [GPL](GPL)), with the exceptions listed in [COPYING.txt](COPYING.txt).
The game's media is licensed under the Creative Commons
Attribution-ShareAlike 2.5 license (see [CC](CC)).

The default font, Saira Condensed, is under the SIL Open Font License; see
[assets/fonts/font-LICENSE.txt](assets/fonts/font-LICENSE.txt).

## Credits

Tremulous is by Darklegion Development and its contributors. The engine is
[ioquake3](https://github.com/ioquake/ioq3), based on the Quake III Arena
source code released by id Software.
