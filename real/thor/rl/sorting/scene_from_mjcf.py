"""The sorting scene for Isaac Lab, read from the MuJoCo scene (sim/sorting/sorting.xml, made by sim/sorting/build.py),
so both simulators hold the same robot and the same table, tray, boxes and balls to the millimetre.

- robot_usd(): the robot as USD for Isaac Lab, converted from robot_mjcf() by Isaac Lab's MJCF importer. Run this file
  once after sim/sorting/build.py changes (python rl/sorting/scene_from_mjcf.py, in the Isaac Lab environment); the
  task loads the USD.
- robot_mjcf(): the robot alone (torso, column and head as fixed parts, the arm, the Zimmer with its fingers) as an
  MJCF file of its own, for Isaac Lab's MJCF importer. Both are put under one root body at the arm base frame.
- static_boxes(): every fixed box of the table, the tray and the two boxes: name, centre, half sizes, colour.
- balls(): the balls' start centres, radius, mass, colour.

Frame: the arm controller's base frame (m, z up, y forward), as in the MuJoCo scene.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]                 # lumi-wave
SCENE = ROOT / "sim" / "sorting" / "sorting.xml"
OUT = Path(__file__).resolve().parent / "assets"
ROBOT_BODIES = ("torso", "arm_base")
GRIPPER_BODIES = ("gripper", "jaw_l", "jaw_r")


def _floats(s, n=None):
    v = [float(x) for x in s.split()]
    return v if n is None else (v + [0.0] * n)[:n]


def _rgba(root, geom):
    """A geom's colour: its own rgba, else its material's."""
    if geom.get("rgba"):
        return _floats(geom.get("rgba"), 4)
    mat = geom.get("material")
    for m in root.find("asset").iter("material"):
        if m.get("name") == mat and m.get("rgba"):
            return _floats(m.get("rgba"), 4)
    return [0.8, 0.8, 0.8, 1.0]


def robot_mjcf():
    """Write assets/lumi_robot.xml (the robot without the table, tray, boxes, balls, floor, lights and cameras) and
    return its path. Mesh and texture paths are made absolute so the file works from anywhere."""
    tree = ET.parse(SCENE)
    root = tree.getroot()
    root.set("model", "lumi_robot")
    for el in root.find("asset"):
        if el.get("file"):
            el.set("file", str((SCENE.parent / el.get("file")).resolve()))
    for tex in root.find("asset").findall("texture"):
        if tex.get("type") == "skybox" or tex.get("builtin"):
            root.find("asset").remove(tex)
    for mat in root.find("asset").findall("material"):
        if mat.get("texture") in ("sky", "grid"):
            del mat.attrib["texture"]
    wb = root.find("worldbody")
    lumi = ET.Element("body", {"name": "lumi", "pos": "0 0 0"})
    for el in list(wb):
        wb.remove(el)
        if el.tag == "body" and el.get("name") in ROBOT_BODIES:
            lumi.append(el)
    wb.append(lumi)
    # The Zimmer's body and the fingers are drawn in MuJoCo by their collision boxes; USD keeps collision shapes
    # invisible, so each gets a visual twin (same box, same material, no collision)
    for body in lumi.iter("body"):
        if body.get("name") not in GRIPPER_BODIES:
            continue
        for g in list(body.findall("geom")):
            if g.get("class") in ("grip", "pad"):
                twin = ET.Element("geom", {k: v for k, v in g.attrib.items() if k not in ("name", "class")})
                twin.attrib.update({"contype": "0", "conaffinity": "0", "group": "2", "density": "0"})
                body.insert(list(body).index(g) + 1, twin)
    vis = root.find("visual")
    if vis is not None:
        root.remove(vis)
    OUT.mkdir(exist_ok=True)
    path = OUT / "lumi_robot.xml"
    text = ET.tostring(root, encoding="unicode")
    if not path.exists() or path.read_text() != text:       # rewritten only when the scene changed
        path.write_text(text)
    return path


USD = OUT / "usd" / "lumi_robot" / "lumi_robot.usda"


def robot_usd(convert=False):
    """The robot's USD file; with convert=True made (again) from the MJCF first."""
    if convert:
        import shutil
        from isaaclab.sim.converters import MjcfConverter, MjcfConverterCfg
        shutil.rmtree(OUT / "usd", ignore_errors=True)       # else the importer writes beside the old one
        MjcfConverter(MjcfConverterCfg(asset_path=str(robot_mjcf()), usd_dir=str(OUT / "usd"), fix_base=True,
                                       self_collision=False, force_usd_conversion=True))
    if not USD.exists():
        raise FileNotFoundError(f"{USD} is missing: run python rl/sorting/scene_from_mjcf.py in the Isaac Lab "
                                "environment first")
    return USD


def static_boxes():
    """[(name, centre xyz, half sizes xyz, rgba, collides)] for every box geom fixed in the world (table, legs, tray,
    boxes, the colour labels)."""
    root = ET.parse(SCENE).getroot()
    out = []
    for i, g in enumerate(root.find("worldbody").findall("geom")):
        if g.get("type") != "box":
            continue
        collides = not (g.get("contype") == "0" and g.get("conaffinity") == "0")
        out.append((g.get("name") or f"part_{i}", _floats(g.get("pos"), 3), _floats(g.get("size"), 3),
                    _rgba(root, g), collides))
    return out


def balls():
    """[(name, centre xyz, radius, mass, rgba)] for the balls of the MuJoCo scene."""
    root = ET.parse(SCENE).getroot()
    out = []
    for b in root.find("worldbody").findall("body"):
        if not b.get("name", "").startswith("ball_"):
            continue
        g = b.find("geom")
        out.append((b.get("name"), _floats(b.get("pos"), 3), _floats(g.get("size"))[0], float(g.get("mass")),
                    _rgba(root, g)))
    return out


if __name__ == "__main__":
    print(robot_usd(convert=True))
    for s in static_boxes():
        print(s[0], [round(v, 4) for v in s[1]], [round(v, 4) for v in s[2]], s[4])
    for b in balls():
        print(b[0], b[1], b[2], b[3], b[4])
