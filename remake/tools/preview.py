#!/usr/bin/env python3
"""Render a converted map to an image, to check the conversion by eye.

This is a small software rasterizer, not a renderer to judge looks by. It
reads only the files bsp2gltf.py wrote, draws the material texture multiplied
by the lightmap with back faces culled, and places the camera at the map's
intermission camera, which is the view the game shows spectators. A correct
conversion therefore reproduces the in-game view.

Usage: preview.py <converted map directory> <output.png> [--size 960x540]
"""

import argparse
import json
import math
import os

import numpy as np
from PIL import Image

COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
DTYPES = {5121: np.uint8, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}


def load(directory):
    name = os.path.basename(os.path.normpath(directory))
    with open(os.path.join(directory, name + ".gltf")) as f:
        gltf = json.load(f)
    with open(os.path.join(directory, gltf["buffers"][0]["uri"]), "rb") as f:
        binary = f.read()

    def accessor(index):
        a = gltf["accessors"][index]
        view = gltf["bufferViews"][a["bufferView"]]
        n = COMPONENTS[a["type"]]
        data = np.frombuffer(binary, dtype=DTYPES[a["componentType"]], count=a["count"] * n,
                             offset=view["byteOffset"] + a.get("byteOffset", 0))
        return data.reshape(a["count"], n) if n > 1 else data

    primitives = []
    for primitive in gltf["meshes"][0]["primitives"]:
        material = gltf["materials"][primitive["material"]]
        texture = None
        base = material["pbrMetallicRoughness"].get("baseColorTexture")
        if base is not None:
            uri = gltf["images"][gltf["textures"][base["index"]]["source"]]["uri"]
            texture = np.asarray(Image.open(os.path.join(directory, uri)).convert("RGB"), dtype=np.float32) / 255.0
        attributes = primitive["attributes"]
        primitives.append({
            "position": accessor(attributes["POSITION"]),
            "uv": accessor(attributes["TEXCOORD_0"]),
            "lm": accessor(attributes["TEXCOORD_1"]),
            "indices": accessor(primitive["indices"]).reshape(-1, 3),
            "texture": texture,
            "blend": material.get("alphaMode", "OPAQUE") == "BLEND",
            "double_sided": material.get("doubleSided", False),
        })

    lightmap = np.asarray(Image.open(os.path.join(directory, gltf["extras"]["lightmap"])).convert("RGB"),
                          dtype=np.float32) / 255.0
    with open(os.path.join(directory, name + "_entities.json")) as f:
        entities = json.load(f)
    return primitives, lightmap, entities


def camera_from_entities(entities):
    for classname in ("info_player_intermission", "info_human_intermission", "info_alien_intermission"):
        for entity in entities:
            if entity.get("classname") == classname and "origin_gltf" in entity:
                angles = [float(x) for x in entity.get("angles", "0 %s 0" % entity.get("angle", "0")).split()]
                pitch, yaw = math.radians(angles[0]), math.radians(angles[1])
                # Quake forward vector, then in to glTF space (x, z, -y)
                forward = np.array([math.cos(pitch) * math.cos(yaw), -math.sin(pitch),
                                    -math.cos(pitch) * math.sin(yaw)])
                return np.array(entity["origin_gltf"], dtype=np.float64), forward
    raise ValueError("the map has no intermission camera")


def render(primitives, lightmap, eye, forward, width, height, fov_y=73.74):
    forward = forward / np.linalg.norm(forward)
    right = np.cross(forward, [0.0, 1.0, 0.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)

    focal = (height / 2) / math.tan(math.radians(fov_y) / 2)
    near = 0.05

    color = np.zeros((height, width, 3), dtype=np.float32)
    depth = np.full((height, width), np.inf, dtype=np.float32)

    def sample(image, uv, wrap):
        h, w = image.shape[:2]
        if wrap:
            u, v = uv[:, 0] % 1.0, uv[:, 1] % 1.0
        else:
            u, v = np.clip(uv[:, 0], 0, 1), np.clip(uv[:, 1], 0, 1)
        x = np.minimum((u * w).astype(np.int64), w - 1)
        y = np.minimum((v * h).astype(np.int64), h - 1)
        return image[y, x]

    # Opaque surfaces first, then blended ones without writing depth
    for primitive in sorted(primitives, key=lambda p: p["blend"]):
        relative = primitive["position"].astype(np.float64) - eye
        view = np.stack([relative @ right, relative @ up, relative @ forward], axis=1)

        for tri in primitive["indices"]:
            p = view[tri]
            # Triangles that cross the near plane are dropped rather than
            # clipped, which is good enough for a check
            if (p[:, 2] <= near).any():
                continue

            sx = width / 2 + p[:, 0] / p[:, 2] * focal
            sy = height / 2 - p[:, 1] / p[:, 2] * focal

            area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0])
            # Counter clockwise in a Y up view is clockwise on a Y down screen
            if area == 0 or (area > 0 and not primitive["double_sided"]):
                continue

            x0, x1 = max(int(math.floor(sx.min())), 0), min(int(math.ceil(sx.max())), width - 1)
            y0, y1 = max(int(math.floor(sy.min())), 0), min(int(math.ceil(sy.max())), height - 1)
            if x0 > x1 or y0 > y1:
                continue

            xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            w0 = ((sx[1] - xs) * (sy[2] - ys) - (sx[2] - xs) * (sy[1] - ys)) / area
            w1 = ((sx[2] - xs) * (sy[0] - ys) - (sx[0] - xs) * (sy[2] - ys)) / area
            w2 = 1.0 - w0 - w1
            inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            if not inside.any():
                continue

            # Perspective correct interpolation
            inv = np.stack([w0, w1, w2], axis=-1)[inside] / p[:, 2]
            z = 1.0 / inv.sum(axis=1)
            weights = inv * z[:, None]

            py, px = ys[inside].astype(np.int64), xs[inside].astype(np.int64)
            visible = z < depth[py, px]
            if not visible.any():
                continue
            py, px, z, weights = py[visible], px[visible], z[visible], weights[visible]

            if primitive["texture"] is not None:
                texel = sample(primitive["texture"], weights @ primitive["uv"][tri], True)
            else:
                texel = np.full((len(z), 3), 0.5, dtype=np.float32)

            if primitive["blend"]:
                color[py, px] = np.minimum(color[py, px] + texel * 0.5, 1.0)
            else:
                # The engine doubles lightmaps (overbright)
                light = sample(lightmap, weights @ primitive["lm"][tri], False) * 2.0
                color[py, px] = np.minimum(texel * light, 1.0)
                depth[py, px] = z

    return Image.fromarray((color * 255).astype(np.uint8))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("directory")
    parser.add_argument("output")
    parser.add_argument("--size", default="960x540")
    args = parser.parse_args()

    width, height = (int(x) for x in args.size.split("x"))
    primitives, lightmap, entities = load(args.directory)
    eye, forward = camera_from_entities(entities)
    render(primitives, lightmap, eye, forward, width, height).save(args.output)


if __name__ == "__main__":
    main()
