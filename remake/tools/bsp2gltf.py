#!/usr/bin/env python3
"""Convert a Quake 3 BSP map from the original game data to glTF 2.0.

Writes, to the output directory:

  <map>.gltf / <map>.bin   the world geometry, one primitive per material
  textures/...             the textures the materials use, as PNG
  <map>_lightmap.png       the baked lightmaps, packed in to one atlas
  <map>_entities.json      the map's entities: spawns, structures, lights...

The geometry has two sets of texture coordinates: TEXCOORD_0 for the material
and TEXCOORD_1 in to the lightmap atlas. Curved surfaces are tessellated.
Coordinates are converted to glTF's: metres, Y up, right handed.

Usage: bsp2gltf.py --data <directory with pk3s> --map atcs --out <directory>
"""

import argparse
import json
import os
import struct

import numpy as np
from PIL import Image

from q3fs import GameFiles

# One Quake unit is about an inch; a human player is 56 units tall
DEFAULT_SCALE = 0.0254

LUMP_ENTITIES, LUMP_SHADERS, LUMP_MODELS = 0, 1, 7
LUMP_VERTEXES, LUMP_MESHVERTS, LUMP_FACES, LUMP_LIGHTMAPS = 10, 11, 13, 14

FACE_POLYGON, FACE_PATCH, FACE_MESH, FACE_BILLBOARD = 1, 2, 3, 4

LIGHTMAP_SIZE = 128

VERTEX_DTYPE = np.dtype([
    ("position", "<f4", 3), ("texcoord", "<f4", 2), ("lmcoord", "<f4", 2),
    ("normal", "<f4", 3), ("color", "u1", 4)])

FACE_DTYPE = np.dtype([
    ("shader", "<i4"), ("effect", "<i4"), ("type", "<i4"),
    ("vertex", "<i4"), ("n_vertexes", "<i4"),
    ("meshvert", "<i4"), ("n_meshverts", "<i4"),
    ("lm_index", "<i4"), ("lm_start", "<i4", 2), ("lm_size", "<i4", 2),
    ("lm_origin", "<f4", 3), ("lm_vecs", "<f4", (2, 3)), ("normal", "<f4", 3),
    ("size", "<i4", 2)])

SHADER_DTYPE = np.dtype([("name", "S64"), ("flags", "<i4"), ("contents", "<i4")])

MODEL_DTYPE = np.dtype([
    ("mins", "<f4", 3), ("maxs", "<f4", 3), ("face", "<i4"), ("n_faces", "<i4"),
    ("brush", "<i4"), ("n_brushes", "<i4")])


class Bsp:
    def __init__(self, data):
        magic, version = struct.unpack_from("<4si", data, 0)
        if magic != b"IBSP" or version != 46:
            raise ValueError("not a Quake 3 BSP (magic %r, version %d)" % (magic, version))

        lumps = [struct.unpack_from("<ii", data, 8 + i * 8) for i in range(17)]

        def lump(index, dtype=None):
            offset, length = lumps[index]
            raw = data[offset:offset + length]
            return raw if dtype is None else np.frombuffer(raw, dtype=dtype)

        self.entities = lump(LUMP_ENTITIES).split(b"\0")[0].decode("latin-1")
        self.shaders = [s["name"].split(b"\0")[0].decode("latin-1").lower().replace("\\", "/")
                        for s in lump(LUMP_SHADERS, SHADER_DTYPE)]
        self.models = lump(LUMP_MODELS, MODEL_DTYPE)
        self.vertexes = lump(LUMP_VERTEXES, VERTEX_DTYPE)
        self.meshverts = lump(LUMP_MESHVERTS, np.dtype("<i4"))
        self.faces = lump(LUMP_FACES, FACE_DTYPE)
        self.lightmaps = lump(LUMP_LIGHTMAPS, np.dtype("u1")).reshape(-1, LIGHTMAP_SIZE, LIGHTMAP_SIZE, 3)


def parse_entities(text):
    """The entity lump is a list of { "key" "value" ... } blocks."""
    entities = []
    current = None
    tokens = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == "{":
            current = {}
        elif c == "}":
            if current is not None:
                entities.append(current)
            current = None
        elif c == '"':
            end = text.index('"', i + 1)
            tokens.append(text[i + 1:end])
            i = end
            if len(tokens) == 2 and current is not None:
                current[tokens[0]] = tokens[1]
                tokens = []
        i += 1
    return entities


def to_gltf_space(points, scale):
    """Quake is Z up; glTF is Y up. This is a rotation, so handedness and
    triangle winding are unaffected."""
    points = np.asarray(points, dtype=np.float32)
    out = np.empty_like(points)
    out[..., 0] = points[..., 0] * scale
    out[..., 1] = points[..., 2] * scale
    out[..., 2] = -points[..., 1] * scale
    return out


def tessellate_patch(controls, width, height, level):
    """A patch is a grid of biquadratic Bezier patches that share edges, each
    3x3 control points. Returns its vertices and triangle indices."""
    fields = ("position", "texcoord", "lmcoord", "normal", "color")
    grid = {f: controls[f].astype(np.float64).reshape(height, width, -1) for f in fields}

    patches_x, patches_y = (width - 1) // 2, (height - 1) // 2
    cols, rows = patches_x * level + 1, patches_y * level + 1

    def basis(t):
        return np.array([(1 - t) ** 2, 2 * t * (1 - t), t ** 2])

    out = {f: np.zeros((rows, cols, grid[f].shape[2])) for f in fields}

    for py in range(patches_y):
        for px in range(patches_x):
            for j in range(level + 1):
                bv = basis(j / level)
                for i in range(level + 1):
                    bu = basis(i / level)
                    weights = np.outer(bv, bu)
                    for f in fields:
                        block = grid[f][py * 2:py * 2 + 3, px * 2:px * 2 + 3]
                        out[f][py * level + j, px * level + i] = np.tensordot(weights, block, axes=2)

    vertexes = np.zeros(rows * cols, dtype=VERTEX_DTYPE)
    for f in fields:
        values = out[f].reshape(rows * cols, -1)
        if f == "normal":
            lengths = np.linalg.norm(values, axis=1, keepdims=True)
            values = values / np.where(lengths > 1e-8, lengths, 1.0)
        elif f == "color":
            values = np.clip(np.rint(values), 0, 255)
        vertexes[f] = values

    indices = []
    for j in range(rows - 1):
        for i in range(cols - 1):
            a = j * cols + i
            b, c, d = a + 1, a + cols, a + cols + 1
            indices += [a, c, b, b, c, d]

    return vertexes, np.array(indices, dtype=np.int64)


class Material:
    def __init__(self, name):
        self.name = name
        self.image = None       # path in the game files
        self.alpha_mode = "OPAQUE"
        self.double_sided = False
        self.emissive = False
        self.skip = False
        self.sky = False


def resolve_material(name, files):
    material = Material(name)
    shader = files.shaders.get(name)

    if shader is None:
        # No script: the shader name is the texture
        material.image = files.find_image(name)
        return material

    parms = shader["surfaceparms"]
    material.sky = shader["sky"] or "sky" in parms
    # Things that exist for the compiler or the game, not to be seen
    material.skip = "nodraw" in parms or material.sky
    material.double_sided = shader["cull"] in ("none", "disable", "twosided")
    material.emissive = shader["surface_light"] > 0

    # The base texture is the first stage that is a real image
    for stage in shader["stages"]:
        image = stage.get("map", "")
        if image.startswith("$") or image.startswith("*"):
            continue
        path = files.find_image(image)
        if path is None:
            continue
        material.image = path
        blend = stage.get("blend", "")
        if stage.get("alpha_test"):
            material.alpha_mode = "MASK"
        elif blend in ("blend", "gl_src_alpha gl_one_minus_src_alpha"):
            material.alpha_mode = "BLEND"
        elif blend in ("add", "gl_one gl_one", "gl_src_alpha gl_one"):
            material.alpha_mode = "BLEND"
            material.emissive = True
        break

    if material.image is None and shader["editor_image"]:
        material.image = files.find_image(shader["editor_image"])
    if material.image is None:
        material.image = files.find_image(name)

    return material


def build_lightmap_atlas(lightmaps):
    count = max(len(lightmaps), 1)
    columns = int(np.ceil(np.sqrt(count)))
    rows = int(np.ceil(count / columns))
    atlas = np.zeros((rows * LIGHTMAP_SIZE, columns * LIGHTMAP_SIZE, 3), dtype=np.uint8)
    for i, lightmap in enumerate(lightmaps):
        y, x = divmod(i, columns)
        atlas[y * LIGHTMAP_SIZE:(y + 1) * LIGHTMAP_SIZE, x * LIGHTMAP_SIZE:(x + 1) * LIGHTMAP_SIZE] = lightmap
    return atlas, columns, rows


def convert(files, map_name, out_dir, scale=DEFAULT_SCALE, patch_level=6):
    bsp = Bsp(files.read("maps/%s.bsp" % map_name))
    os.makedirs(out_dir, exist_ok=True)

    atlas, atlas_columns, atlas_rows = build_lightmap_atlas(bsp.lightmaps)
    Image.fromarray(atlas).save(os.path.join(out_dir, "%s_lightmap.png" % map_name))

    materials = [resolve_material(name, files) for name in bsp.shaders]

    # Only the world (model 0); the other models are doors and the like,
    # which the entities refer to
    world = bsp.models[0]
    groups = {}     # shader index -> (list of vertex arrays, list of index arrays, vertex count)
    stats = {"faces": 0, "patches": 0, "skipped": 0}

    for face in bsp.faces[world["face"]:world["face"] + world["n_faces"]]:
        material = materials[face["shader"]]
        if material.skip or face["type"] == FACE_BILLBOARD:
            stats["skipped"] += 1
            continue

        vertexes = bsp.vertexes[face["vertex"]:face["vertex"] + face["n_vertexes"]]

        if face["type"] in (FACE_POLYGON, FACE_MESH):
            indices = bsp.meshverts[face["meshvert"]:face["meshvert"] + face["n_meshverts"]].astype(np.int64)
        elif face["type"] == FACE_PATCH:
            width, height = int(face["size"][0]), int(face["size"][1])
            vertexes, indices = tessellate_patch(vertexes, width, height, patch_level)
            stats["patches"] += 1
        else:
            stats["skipped"] += 1
            continue

        if len(indices) == 0:
            continue

        vertexes = vertexes.copy()

        # Lightmap coordinates are within the face's own 128x128 page; move
        # them in to the atlas
        if face["lm_index"] >= 0:
            page_y, page_x = divmod(int(face["lm_index"]), atlas_columns)
            vertexes["lmcoord"][:, 0] = (vertexes["lmcoord"][:, 0] + page_x) / atlas_columns
            vertexes["lmcoord"][:, 1] = (vertexes["lmcoord"][:, 1] + page_y) / atlas_rows

        group = groups.setdefault(int(face["shader"]), [[], [], 0])
        group[0].append(vertexes)
        group[1].append(indices + group[2])
        group[2] += len(vertexes)
        stats["faces"] += 1

    # Quake 3 treats clockwise triangles as front facing, glTF counter
    # clockwise. Check against the stored normals rather than assume.
    def needs_flip():
        agree = total = 0
        for vertex_lists, index_lists, _ in groups.values():
            v = np.concatenate(vertex_lists)
            tri = np.concatenate(index_lists).reshape(-1, 3)
            p = v["position"].astype(np.float64)
            geometric = np.cross(p[tri[:, 1]] - p[tri[:, 0]], p[tri[:, 2]] - p[tri[:, 0]])
            stored = v["normal"][tri[:, 0]].astype(np.float64)
            dots = np.einsum("ij,ij->i", geometric, stored)
            agree += int((dots > 0).sum())
            total += int((dots != 0).sum())
        return total > 0 and agree < total / 2

    flip = needs_flip()

    # Assemble the glTF
    binary = bytearray()
    gltf = {
        "asset": {"version": "2.0", "generator": "tremulous remake bsp2gltf"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": map_name}],
        "meshes": [{"name": map_name, "primitives": []}],
        "buffers": [], "bufferViews": [], "accessors": [],
        "materials": [], "textures": [], "images": [],
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}],
        "extras": {
            "source": "maps/%s.bsp" % map_name,
            "unitsPerMetre": 1.0 / scale,
            "lightmap": "%s_lightmap.png" % map_name,
            "lightmapTexcoord": 1,
            "sky": sorted(m.name for m in materials if m.sky),
        },
    }

    def add_view(array, target):
        while len(binary) % 4:
            binary.append(0)
        offset = len(binary)
        binary.extend(array.tobytes())
        gltf["bufferViews"].append({"buffer": 0, "byteOffset": offset, "byteLength": array.nbytes, "target": target})
        return len(gltf["bufferViews"]) - 1

    def add_accessor(array, kind, component, target, normalized=False, bounds=False):
        accessor = {"bufferView": add_view(array, target), "componentType": component,
                    "count": len(array), "type": kind}
        if normalized:
            accessor["normalized"] = True
        if bounds:
            accessor["min"] = [float(x) for x in array.min(axis=0)]
            accessor["max"] = [float(x) for x in array.max(axis=0)]
        gltf["accessors"].append(accessor)
        return len(gltf["accessors"]) - 1

    image_indices = {}
    missing_images = []

    def texture_for(path):
        if path not in image_indices:
            relative = os.path.splitext(path)[0] + ".png"
            target = os.path.join(out_dir, relative)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            files.load_image(path).save(target)
            gltf["images"].append({"uri": relative.replace(os.sep, "/")})
            gltf["textures"].append({"source": len(gltf["images"]) - 1, "sampler": 0})
            image_indices[path] = len(gltf["textures"]) - 1
        return image_indices[path]

    for shader_index in sorted(groups):
        vertex_lists, index_lists, _ = groups[shader_index]
        material = materials[shader_index]
        vertexes = np.concatenate(vertex_lists)
        indices = np.concatenate(index_lists).astype(np.uint32)
        if flip:
            indices = indices.reshape(-1, 3)[:, ::-1].reshape(-1)

        normals = to_gltf_space(vertexes["normal"], 1.0)
        lengths = np.linalg.norm(normals, axis=1, keepdims=True)
        normals = np.where(lengths > 1e-8, normals / np.where(lengths > 1e-8, lengths, 1.0),
                           np.array([0.0, 1.0, 0.0], dtype=np.float32)).astype(np.float32)

        attributes = {
            "POSITION": add_accessor(to_gltf_space(vertexes["position"], scale), "VEC3", 5126, 34962, bounds=True),
            "NORMAL": add_accessor(normals, "VEC3", 5126, 34962),
            "TEXCOORD_0": add_accessor(np.ascontiguousarray(vertexes["texcoord"]), "VEC2", 5126, 34962),
            "TEXCOORD_1": add_accessor(np.ascontiguousarray(vertexes["lmcoord"]), "VEC2", 5126, 34962),
            "COLOR_0": add_accessor(np.ascontiguousarray(vertexes["color"]), "VEC4", 5121, 34962, normalized=True),
        }

        entry = {"name": material.name,
                 "pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 1.0},
                 "extras": {"q3shader": material.name}}
        if material.image:
            texture = {"index": texture_for(material.image)}
            entry["pbrMetallicRoughness"]["baseColorTexture"] = texture
            if material.emissive:
                entry["emissiveTexture"] = texture
                entry["emissiveFactor"] = [1.0, 1.0, 1.0]
        else:
            missing_images.append(material.name)
        if material.alpha_mode != "OPAQUE":
            entry["alphaMode"] = material.alpha_mode
        if material.double_sided:
            entry["doubleSided"] = True
        gltf["materials"].append(entry)

        gltf["meshes"][0]["primitives"].append({
            "attributes": attributes,
            "indices": add_accessor(indices, "SCALAR", 5125, 34963),
            "material": len(gltf["materials"]) - 1,
            "mode": 4,
        })

    gltf["buffers"].append({"uri": "%s.bin" % map_name, "byteLength": len(binary)})

    for key in ("textures", "images"):
        if not gltf[key]:
            del gltf[key]

    with open(os.path.join(out_dir, "%s.bin" % map_name), "wb") as f:
        f.write(binary)
    with open(os.path.join(out_dir, "%s.gltf" % map_name), "w") as f:
        json.dump(gltf, f, indent=1)

    # Entities, with positions in both coordinate systems
    entities = parse_entities(bsp.entities)
    for entity in entities:
        if "origin" in entity:
            try:
                origin = [float(x) for x in entity["origin"].split()]
                entity["origin_gltf"] = [round(float(x), 5) for x in to_gltf_space(origin, scale)]
            except ValueError:
                pass
    with open(os.path.join(out_dir, "%s_entities.json" % map_name), "w") as f:
        json.dump(entities, f, indent=1)

    triangles = sum(gltf["accessors"][p["indices"]]["count"] for p in gltf["meshes"][0]["primitives"]) // 3
    return {
        "map": map_name, "faces": stats["faces"], "patches": stats["patches"], "skipped": stats["skipped"],
        "triangles": triangles, "materials": len(gltf["materials"]), "textures": len(image_indices),
        "missing_textures": missing_images, "lightmap_pages": len(bsp.lightmaps),
        "entities": len(entities), "winding_flipped": bool(flip),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", required=True, help="directory with the game's pk3 files")
    parser.add_argument("--map", action="append", help="map name, e.g. atcs; default is every map")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--scale", type=float, default=DEFAULT_SCALE, help="metres per Quake unit")
    parser.add_argument("--patch-level", type=int, default=6, help="subdivisions per curved patch")
    args = parser.parse_args()

    files = GameFiles(args.data)
    maps = args.map or [os.path.splitext(os.path.basename(p))[0] for p in files.list("maps/", ".bsp")]

    for name in maps:
        result = convert(files, name, os.path.join(args.out, name), args.scale, args.patch_level)
        missing = result.pop("missing_textures")
        print(json.dumps(result))
        if missing:
            print("  no texture found for: %s" % ", ".join(missing))


if __name__ == "__main__":
    main()
