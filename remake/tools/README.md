# Remake pipeline tools

Phase 0 of [the plan](../PLAN.md): get the original game's content in to
formats that current engines and tools read. The tools read the original game
data directly from its pk3 files and need Python 3 with numpy and Pillow.

The game data is not in this repository; any Tremulous 1.1.0 installation's
`base` directory works as `--data`.

| Tool | Status | What it does |
| --- | --- | --- |
| `bsp2gltf.py` | Working on all 8 maps | Maps to glTF 2.0, textures to PNG, lightmap atlas, entities to JSON |
| `preview.py` | Working | Renders a converted map from the map's spectator camera, to compare with the game |
| `q3fs.py` | Library | Reads pk3 archives and shader scripts |

Not written yet: MD3 models to glTF, and the game rules (classes, weapons,
buildables) to JSON tables.

## Usage

```sh
# Convert every map, or name some with --map
python3 remake/tools/bsp2gltf.py --data /path/to/tremulous/base --out remake/out

# Check a conversion by eye
python3 remake/tools/preview.py remake/out/atcs atcs.png
```

## What the map conversion does and does not carry over

Carried over: the world geometry with curved surfaces tessellated, material
textures and their coordinates, a second set of coordinates in to the packed
lightmap, vertex colors, blending and culling hints, and all entities with
their positions converted. Positions are in metres with Y up.

Not carried over: the sky (the engine should provide its own; the names of
the sky shaders are in the glTF's `extras`), animated and multi-stage shader
effects (only the base texture is used), doors and other moving brush models,
fog volumes, and collision brushes. The lightmap is exported for reference;
a remake should relight the maps rather than use it.

## How the conversion was checked

`preview.py` is an independent, minimal software rasterizer that reads only
the converter's output. Its picture of ATCS from the map's spectator camera
was compared with a screenshot of the game at the same camera: geometry,
texture mapping, lightmap mapping and triangle winding match.
