# Tremulous on a current engine: plan

Goal: make Tremulous look like a game of the current decade by moving it to a
current engine and bringing its graphics, textures included, up to date.

This document is the plan for that work. It lives on its own branch, started
from the original fork, because it is a separate line of work from maintaining
the existing game.

## What this actually is

This is a remake, not a port. Three things follow from that and shape the
rest of the plan:

1. **The engine does not make the game look current; the assets and lighting
   do.** Tremulous's maps are a few thousand polygons with 256 pixel textures
   and baked lightmaps. Loaded as they are in to any modern engine they look
   exactly as they do today. Most of the effort is art.
2. **Almost none of the existing code carries over.** The game logic is about
   80,000 lines of C written against the Quake 3 virtual machine interface.
   On another engine the rules have to be reimplemented; what carries over is
   the design, the numbers and the assets.
3. **It is a large project.** [Unvanquished](https://unvanquished.net) is the
   reference: a Tremulous fork that set out to do this, with a modernized
   engine and all new assets, and has been in development by a team since
   2011. Planning for less than person-years of work would be dishonest.

## Engine choice

| | Unreal Engine 5 | Godot 4 | Dæmon (Unvanquished) |
| --- | --- | --- | --- |
| Visual ceiling | Highest: Nanite, Lumen | Good: SDFGI, volumetrics | Moderate |
| Multiplayer FPS support | Built in: replication, movement prediction | Has to be built | Built in, Quake lineage |
| Engine license | Proprietary EULA, royalty above a revenue threshold | MIT | BSD/GPL |
| Can reuse the GPL game code | **No** | Yes | Yes, already does |
| Project stays fully open source | Game code only, not the engine | Yes | Yes |
| Editor runs headless for CI | Heavy | Yes | n/a |

The decisive row is licensing. Tremulous's code is under the GPL, and the
Unreal Engine EULA does not allow engine code to be combined with code under a
license that would require the engine's source to be distributed under it.
On Unreal the game rules therefore have to be reimplemented from the design
without deriving from the existing source, and released under a different
license; a translation of the C code is not an option. The media is under
CC BY-SA 2.5 and can be used with either engine, with attribution and with
derived assets under the same license.

**Recommendation: Godot 4**, because it keeps the whole project open source,
which has been a requirement so far, and lets the rules be ported from the
existing code rather than reconstructed. Its visual ceiling is below Unreal's
but well within "current decade" for a game of this scope, and the limiting
factor will be art capacity either way. Unreal is the better choice only if
the highest visual fidelity outweighs open source and the reuse of existing
logic. **This decision is the project owner's**, and it is the one thing that
has to be settled before Phase 1.

Phase 0 below is deliberately engine neutral so that it is not wasted
whichever way that goes.

## Phases

### Phase 0: asset and data pipeline (started)

Get everything out of the original formats and in to ones that current
engines and tools read, reproducibly, from the original game data.

- Maps: Quake 3 BSP to glTF 2.0, with materials, textures, lightmap
  coordinates and curved surfaces tessellated; entities (spawns, default
  base layouts, lights, triggers) to JSON.
- Models: MD3 to glTF, with animations.
- Textures: to PNG, with shader scripts resolved to a base texture.
- Game rules as data: classes, weapons, buildables and upgrades with all of
  their numbers, from the config files and `tremulous.h`, to JSON tables.

Exit: every map and model in the released data converts without errors, and
the output loads in the target engine and in Blender.

Status: the map converter is written and converts all eight maps of the
released data; see [tools/README.md](tools/README.md). Models and the rules
tables are next. Loading the output in an engine and in Blender has not been
tried yet.

### Phase 1: vertical slice

One map (ATCS), one human (rifle), one alien (dretch), playable locally.

- Project skeleton in the chosen engine, importing Phase 0 output.
- Movement parity: Quake-style ground and air movement, and wallwalking,
  which is the hardest part and has no equivalent in stock engines.
- Shooting, biting, damage, death and respawn at a spawn point.

Exit: movement and combat feel right to people who play Tremulous.

### Phase 2: the game

Everything that makes it Tremulous, driven by the Phase 0 data tables.

- Building: build points, power and creep, placement rules, all structures.
- Stages, evolving, the armoury, credits and evolution points.
- All classes, weapons and upgrades.
- Win conditions, teams, spectating, votes.

### Phase 3: networking

Dedicated server, client prediction and lag compensation, server browser.
On Unreal much of this comes with the engine; on Godot it is a workstream of
its own and should start as a spike during Phase 1.

### Phase 4: art

This is what delivers the goal, and it runs in parallel from Phase 1 on.

| Tier | Method | Result |
| --- | --- | --- |
| 0 | Original assets, converted | Playable, looks like 2006 |
| 1 | Upscaled textures, generated normal/roughness maps, real time GI, volumetric fog, modern post processing | Clearly better lighting, same shapes |
| 2 | Maps re-detailed on top of the original layout: trim sheets, modular kits, decals, props; models remade at current polygon counts with PBR materials and skeletal animation | Looks current |

Tier 1 can largely be automated and is the first target. Tier 2 is manual or
AI-assisted art for 8 maps, 8 alien classes, the human with its armour and
weapons, and about 15 structures; it needs artists, and it decides whether the
goal is met. Assets made with generative tools need a license check before
they are published under CC BY-SA.

### Phase 5: interface, audio, release

Menus and HUD, sound, bots if wanted, packaging and CI for the new project.

## Risks

- **Art capacity.** Without people to do Tier 2 the result is a Tier 1
  relight of the 2006 game. This is the largest risk.
- **Engine license**, as above, if Unreal is chosen.
- **Wallwalking and movement feel.** Players will reject the remake if this
  is off.
- **Netcode** on Godot.
- **Scope.** The existing game keeps working throughout; the remake should
  not be allowed to stall its maintenance.

## Repository layout

```
remake/
  PLAN.md        this document
  tools/         the Phase 0 pipeline
  out/           generated output, not committed
```

The engine project gets its own directory under `remake/` once the engine is
chosen.

## What can be done from here

The automated environment this is being developed in has no GPU and no engine
editor. The pipeline, the data tables, and logic that can be unit tested can
be built and checked there. Anything that has to be seen or felt, which is
movement, lighting and art, needs a person at a workstation.
