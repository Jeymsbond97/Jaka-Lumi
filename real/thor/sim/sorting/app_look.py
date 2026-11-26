"""The Lumi app's 3D model as the simulation's look: the same shell, black trim, visor, red bands, green shoulder ring,
JAKA lettering, cutshion logo, cameras and lamp the app draws (Lumi-app tools/lumi-model, its uncompressed
out/lumi.glb copied to assets/lumi_app.glb). Only the look: the arm's joints stay the fitted kinematics and the
collision shapes stay as build.py makes them.

parts() cuts the model into one mesh per link and material, in that link's URDF frame (metres), written once to
assets/app_cache/ (not in git; remade when the .glb changes), and returns what build.py needs to place them.
"""
import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
GLB = HERE / "assets" / "lumi_app.glb"
CACHE = HERE / "assets" / "app_cache"
CACHE_VERSION = "2"     # bump when the way parts are cut changes, so the cache is remade
URDF_FROM_GLTF = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)   # glTF is y up, the URDF z up

LINKS = ("base_link", "wheel_l", "wheel_r", "link_1", "link_2", "link_3", "link_4",
         "link_a1", "link_a2", "link_a3", "link_a4", "link_a5", "link_a6", "link_at")
# MuJoCo draws rgba as given; glTF base colours are linear: shown here in sRGB, with the app's gloss
FINISH = {"Shell": (0.5, 0.7), "Metal": (0.8, 0.8), "Visor": (0.9, 0.9), "Sensor": (0.8, 0.9), "Logo": (0.3, 0.5),
          "BrandLogo": (0.2, 0.4), "Red": (0.4, 0.6), "Green": (0.5, 0.7), "Lamp": (0.2, 0.3)}


def _srgb(c):
    return [float(min(1.0, max(0.0, v)) ** (1 / 2.2)) for v in c[:3]] + [float(c[3]) if len(c) > 3 else 1.0]


def parts():
    """[{link, material, file, rgba, specular, shininess, texture}] for every coloured part of the app's model."""
    stamp = hashlib.md5(GLB.read_bytes() + CACHE_VERSION.encode()).hexdigest()
    index = CACHE / "parts.json"
    if index.exists():
        saved = json.loads(index.read_text())
        if saved.get("glb_md5") == stamp:
            return saved["parts"]
    import trimesh                                       # only needed when the cache is made
    CACHE.mkdir(parents=True, exist_ok=True)
    scene = trimesh.load(str(GLB), force="scene")
    graph = scene.graph
    parent = {e[1]: e[0] for e in graph.to_edgelist()}

    def link_of(node):
        while node in parent:
            node = parent[node]
            if node in LINKS:
                return node
        return None

    groups = {}                                          # (link, material) -> [(vertices, faces, uv)]
    texture = None
    for node in graph.nodes_geometry:
        link = link_of(node)
        if link is None:
            continue
        T_node, gname = graph[node][0], graph[node][1]
        T_link = graph[link][0]
        geom = scene.geometry[gname]
        M = np.linalg.inv(T_link) @ T_node               # the part in its link's glTF frame
        v = (np.c_[geom.vertices, np.ones(len(geom.vertices))] @ M.T)[:, :3] @ URDF_FROM_GLTF.T
        mat = geom.visual.material
        name = mat.name
        uv = getattr(geom.visual, "uv", None) if name == "BrandLogo" else None
        if name == "BrandLogo" and getattr(mat, "baseColorTexture", None) is not None:
            texture = mat.baseColorTexture
        rgba = list(getattr(mat, "baseColorFactor", None) if getattr(mat, "baseColorFactor", None) is not None else [255] * 4)
        rgba = [c / 255.0 if max(rgba) > 1 else c for c in rgba]
        groups.setdefault((link, name, tuple(np.round(rgba, 4))), []).append((v, geom.faces, uv))

    out = []
    for (link, name, rgba), pieces in sorted(groups.items()):
        path = CACHE / f"{link}__{name}.obj"
        lines, base = [], 0
        for v, f, uv in pieces:
            lines += [f"v {x:.6f} {y:.6f} {z:.6f}" for x, y, z in v]
            if uv is not None:
                lines += [f"vt {a:.6f} {b:.6f}" for a, b in uv]
                lines += [f"f {a + base + 1}/{a + base + 1} {b + base + 1}/{b + base + 1} {c + base + 1}/{c + base + 1}" for a, b, c in f]
            else:
                lines += [f"f {a + base + 1} {b + base + 1} {c + base + 1}" for a, b, c in f]
            base += len(v)
        path.write_text("\n".join(lines) + "\n")
        spec, shine = FINISH.get(name, (0.3, 0.5))
        part = {"link": link, "material": name, "file": str(path.relative_to(HERE)), "rgba": _srgb(list(rgba)),
                "specular": spec, "shininess": shine, "texture": None}
        if name == "BrandLogo" and texture is not None:
            tex = CACHE / "brand_logo.png"
            img = texture.convert("RGBA")                # MuJoCo draws transparent pixels black: put the logo
            from PIL import Image                        # on the shell's white as the app does
            white = Image.new("RGBA", img.size, (242, 244, 245, 255))
            white.alpha_composite(img)
            white.convert("RGB").save(tex)
            part["texture"] = str(tex.relative_to(HERE))
            part["rgba"] = [1, 1, 1, 1]
        out.append(part)
    index.write_text(json.dumps({"glb_md5": stamp, "parts": out}, indent=1))
    return out


if __name__ == "__main__":
    for p in parts():
        print(p["link"], p["material"], p["file"], [round(c, 2) for c in p["rgba"]], p["texture"])
