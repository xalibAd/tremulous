"""Read-only view of a Quake 3 style game directory: a set of pk3 archives
searched in the engine's order, plus the shader scripts found in them."""

import io
import os
import re
import zipfile

from PIL import Image

IMAGE_EXTENSIONS = (".tga", ".jpg", ".jpeg", ".png")


class GameFiles:
    def __init__(self, directory):
        # The engine gives pk3s that sort later precedence
        names = sorted(n for n in os.listdir(directory) if n.lower().endswith(".pk3"))
        if not names:
            raise FileNotFoundError("no pk3 files in %s" % directory)

        self.archives = [zipfile.ZipFile(os.path.join(directory, n)) for n in names]
        self.index = {}
        for archive in self.archives:
            for name in archive.namelist():
                if not name.endswith("/"):
                    self.index[name.lower()] = (archive, name)

        self._shaders = None

    def exists(self, path):
        return path.lower() in self.index

    def read(self, path):
        archive, name = self.index[path.lower()]
        return archive.read(name)

    def list(self, prefix="", suffix=""):
        prefix, suffix = prefix.lower(), suffix.lower()
        return sorted(n for n in self.index if n.startswith(prefix) and n.endswith(suffix))

    def find_image(self, name):
        """Resolve a texture name, with or without an extension, to a path."""
        name = name.lower().replace("\\", "/")
        base = os.path.splitext(name)[0]
        for candidate in [name] + [base + ext for ext in IMAGE_EXTENSIONS]:
            if candidate in self.index:
                return candidate
        return None

    def load_image(self, path):
        return Image.open(io.BytesIO(self.read(path)))

    @property
    def shaders(self):
        if self._shaders is None:
            self._shaders = {}
            for path in self.list("scripts/", ".shader"):
                text = self.read(path).decode("latin-1")
                for name, shader in parse_shader_script(text).items():
                    self._shaders[name] = shader
        return self._shaders


def parse_shader_script(text):
    """Parse a .shader script in to {name: shader}. Only what is needed to
    turn a shader in to a material is kept: the surface parameters, culling,
    and for each stage its texture and blend mode. Shader scripts are line
    oriented, so this goes line by line."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    shaders = {}
    name = None
    shader = None
    stage = None
    depth = 0

    for raw in text.splitlines():
        line = raw.split("//")[0].strip()
        if not line:
            continue

        # Braces may share a line with other tokens
        parts = re.findall(r"\{|\}|[^{}]+", line)
        for part in parts:
            part = part.strip()
            if not part:
                continue

            if part == "{":
                depth += 1
                if depth == 1:
                    shader = {"surfaceparms": set(), "cull": "front", "stages": [],
                              "editor_image": None, "sky": False, "surface_light": 0.0}
                elif depth == 2:
                    stage = {}
                continue

            if part == "}":
                if depth == 2 and stage is not None:
                    shader["stages"].append(stage)
                    stage = None
                elif depth == 1 and name is not None:
                    shaders[name] = shader
                    name, shader = None, None
                depth = max(depth - 1, 0)
                continue

            words = part.split()
            key = words[0].lower()
            args = [w.strip('"') for w in words[1:]]

            if depth == 0:
                name = words[0].strip('"').lower().replace("\\", "/")
            elif depth == 1:
                if key == "surfaceparm" and args:
                    shader["surfaceparms"].add(args[0].lower())
                elif key == "cull" and args:
                    shader["cull"] = args[0].lower()
                elif key == "qer_editorimage" and args:
                    shader["editor_image"] = args[0]
                elif key == "skyparms":
                    shader["sky"] = True
                elif key == "q3map_surfacelight" and args:
                    try:
                        shader["surface_light"] = float(args[0])
                    except ValueError:
                        pass
            elif depth == 2 and stage is not None:
                if key in ("map", "clampmap") and args:
                    stage["map"] = args[0]
                elif key == "animmap" and len(args) > 1:
                    stage["map"] = args[1]
                elif key == "blendfunc" and args:
                    stage["blend"] = " ".join(a.lower() for a in args)
                elif key == "alphafunc" and args:
                    stage["alpha_test"] = args[0].lower()

    return shaders

