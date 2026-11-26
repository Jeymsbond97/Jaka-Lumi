"""Build the colour sorting scene (sorting.xml): Lumi's arm with the Zimmer gripper and its straight fingers, the
torso and head it must keep clear of, the table, the tray of balls and the two boxes.

Everything is placed in the arm controller's base frame (Cobo pi, the frame of moveL and kine_forward), in metres,
z up, Lumi's front along +y. That is the frame the robot's own code and its calibrations use, so poses, camera
readings and taught points carry over without conversion.

- Arm joints: the fitted kinematics (data/arm_kinematics.json, robot/kinematics.py): each joint's frame
  and zero corrected to the controller's own answers (0.2 mm). A joint's qpos is the controller's angle in radians.
- Look: the Lumi app's own 3D model (app_look.py: shell, trim, visor, red bands, green ring, JAKA lettering,
  cutshion logo, cameras, lamp), each part in its link's frame; the arm's parts placed with the app's link chain
  (Lumi-app src/lib/armFrame.ts, fitted to the controller within ~1 mm).
- Arm collision: JAKA's MiniCobo STEP meshes (sim/sorting/assets/minicobo, the arm in the app model).
- Torso, lift, head, base: the vendor URDF meshes, placed from the arm through the URDF chain at the sorting pose
  (lift LIFT_M, waist WAIST_RAD, head straight).
- Torso camera: the hand-eye calibration (data/camera_extrinsics.json), fovy from the factory intrinsics.
- Gripper and fingers: measured by the owner 2026-11-25 (docs/gripper, docs/10_GRIPPER.md); lengths read from photos
  are +-5 mm and the fingers' direction around the flange is a guess (see GRIP_YAW_DEG) until the grasp point is
  taught on the robot.

    .venv-sim/bin/python sim/sorting/build.py      # writes sim/sorting/sorting.xml
"""
import json
import math
import re
from pathlib import Path

import mujoco
import numpy as np

import app_look

HERE = Path(__file__).resolve().parent
SIM = HERE.parent
REPO = SIM.parent
KIN_FILE = REPO / "data/arm_kinematics.json"
CAM_FILE = REPO / "data/camera_extrinsics.json"
OUT = HERE / "sorting.xml"

# ---------- the robot's pose during sorting ----------
LIFT_M = 0.0            # the lift at its lowest (as the owner keeps it, 2026-11-25): the table is nearest the hand and
                        # the torso camera sees nearest to Lumi
WAIST_RAD = 0.0         # waist at the front; only turns the base under the table here (approximate)
HEAD_PITCH_RAD = 0.0    # head straight

# ---------- the app's arm chain (Lumi-app src/lib/armFrame.ts): glTF axes, each link turns about its y ----------
APP_CHAIN = [((0, 0, 0), (0, 0, 0, 1)),
             ((0, 0.156, 0.0165), (0.5, 0.5, 0.5, 0.5)),
             ((0.21, -0.029, 0), (0, 0, 0, 1)),
             ((0.1303, 0.0185, 0), (-0.5, -0.5, -0.5, 0.5)),
             ((0, 0.0802, -0.0187), (0.5, -0.5, -0.5, 0.5)),
             ((-0.1233, 0.01805, 0), (0.5, -0.5, 0.5, 0.5))]
APP_MOUNT_R = np.array([[0, 1, 0], [0, 0, -1], [-1, 0, 0]], float)   # model arm frame -> controller frame
APP_MOUNT_T = np.array([30.4, -0.4, 0.1]) / 1000.0
GLTF_FROM_URDF = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)   # a URDF (z up) vector in glTF axes (y up)

# ---------- gripper (gripper frame G: origin at the flange's centre, z along the flange's axis away from the arm, x
# the way the Zimmer body hangs off the flange (across the axis), y the way the jaws move), metres. As on the robot
# (owner's photos 2026-11-25): the adapter plate sits on the flange face, the Zimmer body hangs from it across the
# flange's axis, and the fingers run out ALONG the flange's axis from below the body ----------
GRIP_YAW_DEG = -43.3      # x_G in the flange frame: the old C-hooks' grasp point lay this way (tcp_offset_flange
                          # 85.6, -80.6, 175 mm: 117 mm across the axis, 175 mm along it). A GUESS until the grasp
                          # point is taught with a ball
FLANGE_TO_TOP = 0.032     # the adapter's top edge this far across the axis on the other side (the flange's radius)
ADAPTER_T = 0.008         # adapter plate thickness along the axis
BODY_LEN = 0.100          # adapter top edge to the Zimmer's lower face, across the axis (owner's tape)
BODY_DEPTH = 0.070        # Zimmer body along the axis, adapter included (owner's tape)
BODY_HALF_Y = 0.032       # half its width along the jaws
JAW_STROKE = 0.013        # per jaw (datasheet; measured 61 open / 35 closed inner gap)
GAP_CLOSED = 0.035        # inner gap between the gripping faces, closed (owner's tape)
FINGER_T = 0.0075         # finger thickness along the jaws, pad included
PAD_T = 0.003             # the rubber pad's share of it (guess)
ARM_X = (0.123, 0.138)    # the finger arm across the axis: top and lower edge (lower edge 170 mm below the adapter top)
ARM_Z = (0.000, 0.180)    # the finger arm along the axis: from the mount plate's back edge to the tip (~180 mm)
PAD_Z = (0.130, 0.180)    # the pads at the tip end, ~50 mm
BLOCK_X = (BODY_LEN - FLANGE_TO_TOP, BODY_LEN - FLANGE_TO_TOP + 0.030)   # steel mount blocks below the body
BLOCK_Z = (0.015, 0.065)
TCP = (0.5 * sum(ARM_X), 0.0, 0.5 * sum(PAD_Z))   # grasp point: between the pad centres (to be taught)
GRIP_FORCE = 90.0         # N, switch level 1
FINGER_MASS = 0.06        # kg per finger, a guess (to weigh)

# ---------- scene (controller frame, m) ----------
TABLE_HEIGHT = 0.75                             # the owner's 75 cm table (the 68 cm one leaves too little that the torso
                                                # camera sees and the hand reaches)
ARM_BASE_AT_LIFT0 = 1.008                       # arm base above the floor at lift 0: the cups' table, -403 mm at lift 75
                                                # (tasks/fetch.py), taken as the owner's 68 cm one. TO MEASURE: touch the
                                                # 75 cm table with the finger tips and read the flange
FLOOR_Z = -(ARM_BASE_AT_LIFT0 + LIFT_M)
TABLE_Z = FLOOR_Z + TABLE_HEIGHT
TRAY_C = (0.030, 0.470)                         # tray centre: the torso camera sees it (y >= ~0.40 on this table) and
                                                # the hand reaches it with the fingers straight down up to y 0.50, tilted
                                                # up to 45 deg further out (reach maps and the owner's free-drive
                                                # recording, 2026-11-25)
TRAY_OUT = (0.280, 0.190, 0.025)                # outer size; long side across Lumi's front
TRAY_WALL, TRAY_FLOOR = 0.005, 0.004
BOX_OUT = (0.180, 0.260, 0.080)                 # S_Half box without its lid, short side facing the tray
BOX_WALL = 0.003
BOX_GAP = 0.050                                 # between the tray and each box: room for the fingers
BALL_R, BALL_MASS = 0.02125, 0.008              # foam golf practice ball 42.5 mm, 8 g
BALL_GRID = (0.090, 0.075)                      # ball spacing along x and y: the hand reaches the table with its jaws
                                                # turned about 45 deg, so the fingers need room on the diagonals too
COLOURS = {"red": "0.86 0.12 0.12 1", "yellow": "0.97 0.80 0.10 1"}
BOXES = {"red": -1, "yellow": +1}               # which side of the tray (along x) each colour's box stands


def quat_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def rot(axis, a):
    c, s = math.cos(a), math.sin(a)
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def hmat(R, t):
    T = np.eye(4)
    T[:3, :3], T[:3, 3] = R, t
    return T


def mj_quat(R):
    q = np.zeros(4)
    mujoco.mju_mat2Quat(q, np.asarray(R, float).flatten())
    return q


def fmt(v, n=6):
    return " ".join(f"{x:.{n}f}".rstrip("0").rstrip(".") if abs(x) > 1e-12 else "0" for x in v)


def pose_attr(T):
    return f'pos="{fmt(T[:3, 3])}" quat="{fmt(mj_quat(T[:3, :3]), 8)}"'


# ---------- arm ----------
def fitted():
    d = json.loads(KIN_FILE.read_text())
    mm = lambda A: hmat(np.array(A)[:3, :3], np.array(A)[:3, 3] / 1000.0)
    return mm(d["base"]), [mm(F) for F in d["joints"]], d["offsets_rad"]


def fit_chain(q, model):
    """Each link's frame in the controller frame (m) after its joint, as robot/kinematics.py chain()."""
    base, frames, offsets = model
    T, out = base, []
    for F, a, off in zip(frames, q, offsets):
        T = T @ F @ hmat(rot("z", a + off), np.zeros(3))
        out.append(T)
    return out


def app_chain(q):
    """Each link's frame in the controller frame (m) as the app draws it, in URDF link axes (the STL's own)."""
    R, p, out = np.eye(3), np.zeros(3), []
    for (t, qq), a in zip(APP_CHAIN, q):
        p = p + R @ np.array(t)
        R = R @ quat_mat(qq) @ rot("y", a)
        out.append(hmat(APP_MOUNT_R @ R @ GLTF_FROM_URDF, APP_MOUNT_R @ p + APP_MOUNT_T))
    return out


def mesh_offsets(model):
    """Each MiniCobo mesh's place in its fitted link body: constant, averaged over random poses; worst spread kept."""
    rng = np.random.default_rng(0)
    rows = []
    for _ in range(40):
        q = rng.uniform(-math.pi, math.pi, 6)
        rows.append([np.linalg.inv(f) @ a for f, a in zip(fit_chain(q, model), app_chain(q))])
    out, spread = [], []
    for i in range(6):
        Ms = np.array([r[i] for r in rows])
        t = Ms[:, :3, 3].mean(axis=0)
        U, _, Vt = np.linalg.svd(Ms[:, :3, :3].mean(axis=0))
        out.append(hmat(U @ Vt, t))
        spread.append(1000 * np.linalg.norm(Ms[:, :3, 3] - t, axis=1).max())
    return out, spread


# ---------- torso from the old full model ----------
def torso():
    """{body: 4x4 in link_2's frame} of base_link, link_1 ... link_4 at the sorting pose, and their geoms."""
    m = mujoco.MjModel.from_xml_path(str(SIM / "lumi.xml"))
    d = mujoco.MjData(m)
    for name, v in (("l_1", LIFT_M), ("l_2", WAIST_RAD), ("l_3", 0.0), ("l_4", HEAD_PITCH_RAD)):
        d.qpos[m.jnt_qposadr[m.joint(name).id]] = v
    mujoco.mj_kinematics(m, d)
    W = lambda b: hmat(d.xmat[m.body(b).id].reshape(3, 3), d.xpos[m.body(b).id])
    inv2 = np.linalg.inv(W("link_2"))
    names = ["base_link", "wheel_l", "wheel_r", "link_1", "link_2", "link_3", "link_4"]
    meshfile = dict(re.findall(r'<mesh name="(\w+)" file="([\w.]+\.STL)"', (SIM / "lumi.xml").read_text()))
    geoms = []
    for b in names:
        Tb = inv2 @ W(b)
        bid = m.body(b).id
        for g in range(m.ngeom):
            if m.geom_bodyid[g] != bid:
                continue
            Tg = Tb @ hmat(quat_mat(np.roll(m.geom_quat[g], -1)), m.geom_pos[g])
            if m.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH:
                mesh = m.mesh(m.geom_dataid[g]).name
                if mesh in meshfile:
                    # the file is in the body's frame: MuJoCo's own recentring (in geom_pos) must not be kept
                    geoms.append(("mesh", mesh, Tb, None, "black" if "wheel" in b else "white"))
            elif m.geom_group[g] == 3 and m.geom_type[g] in (mujoco.mjtGeom.mjGEOM_BOX, mujoco.mjtGeom.mjGEOM_CYLINDER):
                geoms.append(("box" if m.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX else "cylinder", None, Tg,
                              m.geom_size[g].copy(), None))
    return geoms, meshfile


def link2_in_controller(model):
    """link_2's frame in the controller frame, the way the Lumi app joins the arm to the column: the arm's first link
    (at joint 1 = 0) where the app's chain puts it, and link_2 behind it by the URDF's joint_l_a1 origin. The fitted
    base frame carries a ~6 deg tilt that belongs to the arm's zero angles, not to the mount: placing the column from it
    left the column leaning against the shoulder (owner, 2026-11-26)."""
    m = mujoco.MjModel.from_xml_path(str(SIM / "lumi.xml"))
    d = mujoco.MjData(m)
    mujoco.mj_kinematics(m, d)
    W = lambda b: hmat(d.xmat[m.body(b).id].reshape(3, 3), d.xpos[m.body(b).id])
    a1_in_2 = np.linalg.inv(W("link_2")) @ W("link_a1")           # joint_l_a1's origin, at zero angle
    a1_in_ctrl = app_chain([0.0] * 6)[0]
    return a1_in_ctrl @ np.linalg.inv(a1_in_2)


# ---------- writing ----------
def box_geom(name, c, half, rgba, extra=""):
    return f'<geom name="{name}" type="box" pos="{fmt(c)}" size="{fmt(half)}" rgba="{rgba}" {extra}/>'


def open_box(prefix, centre, out, wall, floor, rgba):
    """An open box: floor and four walls (centre: x, y of the middle, z of the bottom)."""
    x, y, z = centre
    sx, sy, sz = (v / 2 for v in out)
    g = [box_geom(f"{prefix}_floor", (x, y, z + floor / 2), (sx, sy, floor / 2), rgba)]
    h = (sz - floor / 2)
    zc = z + floor + h - floor / 2
    g += [box_geom(f"{prefix}_wall_x0", (x - sx + wall / 2, y, zc), (wall / 2, sy, h), rgba),
          box_geom(f"{prefix}_wall_x1", (x + sx - wall / 2, y, zc), (wall / 2, sy, h), rgba),
          box_geom(f"{prefix}_wall_y0", (x, y - sy + wall / 2, zc), (sx, wall / 2, h), rgba),
          box_geom(f"{prefix}_wall_y1", (x, y + sy - wall / 2, zc), (sx, wall / 2, h), rgba)]
    return g


def gripper_xml():
    G = rot("z", math.radians(GRIP_YAW_DEG))
    box = lambda x0, x1, y0, y1, z0, z1: (f'pos="{(x0 + x1) / 2:.4f} {(y0 + y1) / 2:.4f} {(z0 + z1) / 2:.4f}" '
                                          f'size="{abs(x1 - x0) / 2:.4f} {abs(y1 - y0) / 2:.4f} {abs(z1 - z0) / 2:.4f}"')
    top, bottom = -FLANGE_TO_TOP, BODY_LEN - FLANGE_TO_TOP
    L = [f'<body name="gripper" quat="{fmt(mj_quat(G), 8)}">',
         f'  <inertial pos="{(top + bottom) / 2:.4f} 0 {BODY_DEPTH / 2:.4f}" mass="0.6" diaginertia="0.0012 0.0012 0.0008"/>',
         f'  <geom class="grip" type="box" {box(top, bottom, -0.036, 0.036, 0, ADAPTER_T)} material="alu"/>',
         f'  <geom class="grip" type="box" {box(top, bottom, -BODY_HALF_Y, BODY_HALF_Y, ADAPTER_T, BODY_DEPTH)} material="zimmer"/>',
         f'  <site name="tcp" pos="{fmt(TCP)}" size="0.004" rgba="0 1 0 1" group="4"/>']
    # looks only (owner's photos 2026-11-25): the aluminium adapter's chamfered rim and two screws, the Zimmer's two
    # housings with the seam between them, its white side cover, the label, the cable plug and the jaw guides
    mid = top + 0.070                                   # the seam between the motor housing and the jaw housing
    L += [f'  <geom class="gvis" type="box" {box(top - 0.002, bottom + 0.002, -0.037, 0.037, -0.0005, 0.0015)} material="alu"/>',
          *[f'  <geom class="gvis" type="cylinder" pos="{top + 0.012:.4f} {y:.4f} {ADAPTER_T / 2:.4f}" quat="0.7071068 0 0.7071068 0" '
            f'size="0.0035 0.0006" material="screw"/>' for y in (-0.016, 0.016)],
          f'  <geom class="gvis" type="box" {box(mid - 0.0012, mid + 0.0012, -BODY_HALF_Y - 0.0004, BODY_HALF_Y + 0.0004, ADAPTER_T, BODY_DEPTH + 0.0004)} material="seam"/>',
          f'  <geom class="gvis" type="box" {box(top + 0.004, mid - 0.004, BODY_HALF_Y, BODY_HALF_Y + 0.0025, BODY_DEPTH - 0.011, BODY_DEPTH)} material="cover"/>',
          f'  <geom class="gvis" type="box" {box(mid + 0.004, bottom - 0.004, 0.004, BODY_HALF_Y - 0.004, BODY_DEPTH, BODY_DEPTH + 0.0006)} material="label"/>',
          f'  <geom class="gvis" type="box" {box(mid + 0.010, mid + 0.016, 0.018, 0.026, BODY_DEPTH + 0.0006, BODY_DEPTH + 0.0009)} material="zlogo"/>',
          f'  <geom class="gvis" type="box" {box(bottom - 0.001, bottom + 0.004, -0.010, 0.010, 0.012, BODY_DEPTH - 0.006)} material="slot"/>']
    for side, s in (("l", +1), ("r", -1)):
        y_in = GAP_CLOSED / 2                           # gripping face, closed
        ys = lambda a, b: (s * a, s * b)
        L.append(f'  <body name="jaw_{side}">')
        L.append(f'    <inertial pos="{TCP[0]:.3f} {s * 0.02:.3f} 0.09" mass="{FINGER_MASS + 0.04:.3f}" diaginertia="2e-4 2e-4 1e-4"/>')
        L.append(f'    <joint name="jaw_{side}" type="slide" axis="0 {s} 0" range="0 {JAW_STROKE}" damping="20" armature="0.05"/>')
        L.append(f'    <geom class="grip" type="box" {box(*BLOCK_X, *ys(0.0002, y_in), *BLOCK_Z)} material="steel"/>')
        yf = ys(y_in + PAD_T, y_in + FINGER_T)
        L.append(f'    <geom class="grip" type="box" {box(bottom, ARM_X[0], *yf, 0.0, BLOCK_Z[1])} material="finger"/>')
        L.append(f'    <geom name="arm_{side}" class="grip" type="box" {box(*ARM_X, *yf, *ARM_Z)} material="finger"/>')
        L.append(f'    <geom name="pad_{side}" class="pad" type="box" {box(*ARM_X, *ys(y_in, y_in + PAD_T), *PAD_Z)} material="pad"/>')
        yc = s * (y_in + (PAD_T + FINGER_T) / 2)
        L += [f'    <geom class="gvis" type="box" {box(BLOCK_X[0], BLOCK_X[1], *ys(0.0002, y_in), BLOCK_Z[1] - 0.003, BLOCK_Z[1] + 0.030)} material="steel"/>',
              f'    <geom class="gvis" type="cylinder" pos="{sum(ARM_X) / 2:.4f} {yc:.4f} {ARM_Z[1]:.4f}" quat="0.7071068 0.7071068 0 0" '
              f'size="{(ARM_X[1] - ARM_X[0]) / 2:.4f} {(FINGER_T - PAD_T) / 2:.4f}" material="finger"/>',
              f'    <geom class="gvis" type="cylinder" pos="{bottom + 0.012:.4f} {s * (y_in + FINGER_T + 0.0006):.4f} {BLOCK_Z[1] - 0.012:.4f}" quat="0.7071068 0.7071068 0 0" '
              f'size="0.0035 0.0008" material="screw"/>',
              *[f'    <geom class="gvis" type="box" {box(ARM_X[0] + 0.001, ARM_X[1] - 0.001, *ys(y_in - 0.0004, y_in), z, z + 0.002)} material="pad_rib"/>'
                for z in [PAD_Z[0] + 0.004 + 0.006 * k for k in range(8)]]]
        L.append('  </body>')
    L.append('</body>')
    return L


def build():
    model = fitted()
    offsets, spread = mesh_offsets(model)
    base, frames, joint_offsets = model
    tgeoms, meshfile = torso()
    T2 = link2_in_controller(model)
    cam = json.loads(CAM_FILE.read_text())
    Tc = np.array(cam["T_base_cam"])
    cam_R, cam_t = Tc[:3, :3], Tc[:3, 3] / 1000.0
    fovy = 2 * math.degrees(math.atan(360.0 / 608.4))       # 1280x720, fy 608.4 (06_CAMERAS_AND_VISION.md)
    limits = [360, 125, 130, 360, 120, 360]                 # deg, controller joint limits (01_HARDWARE.md)

    x = []
    x.append('<mujoco model="lumi_sorting">')
    x.append('  <!-- generated by sim/sorting/build.py: edit that file, not this one -->')
    x.append('  <compiler angle="radian" autolimits="true"/>')
    x.append('  <option timestep="0.002" integrator="implicitfast" cone="elliptic" impratio="10"/>')
    # an office: light walls all round and soft light from everywhere, so the white shell reads white
    x.append('  <visual><global offwidth="1280" offheight="960"/><quality shadowsize="4096"/>'
             '<headlight ambient="0.45 0.45 0.45" diffuse="0.35 0.35 0.35" specular="0.1 0.1 0.1"/></visual>')
    x.append('  <asset>')
    for i in range(1, 7):
        x.append(f'    <mesh name="mc_a{i}" file="assets/minicobo/link_a{i}.stl"/>')
    look = app_look.parts()
    by_link = {}
    for k, part in enumerate(look):
        name = f"app{k}_{part['link']}_{part['material']}"
        by_link.setdefault(part["link"], []).append(name)
        x.append(f'    <mesh name="{name}" file="{part["file"]}" inertia="shell"/>')   # looks only: thin decals have no volume
        tex = ""
        if part["texture"]:
            x.append(f'    <texture name="tex_{name}" type="2d" file="{part["texture"]}"/>')
            tex = f' texture="tex_{name}"'
        x.append(f'    <material name="{name}" rgba="{fmt(part["rgba"])}" specular="{part["specular"]}" '
                 f'shininess="{part["shininess"]}"{tex}/>')
    x.append('    <texture name="sky" type="skybox" builtin="gradient" rgb1="0.93 0.93 0.92" rgb2="0.78 0.79 0.80" width="512" height="512"/>')
    x.append('    <texture name="grid" type="2d" builtin="checker" rgb1="0.82 0.82 0.80" rgb2="0.76 0.76 0.74" width="512" height="512"/>')
    x.append('    <material name="floor" texture="grid" texrepeat="8 8"/>')
    for name, rgba in (("white", "0.92 0.93 0.94 1"), ("black", "0.08 0.08 0.09 1"), ("alu", "0.80 0.81 0.83 1"),
                       ("zimmer", "0.07 0.07 0.08 1"), ("steel", "0.74 0.75 0.77 1"), ("finger", "0.09 0.09 0.10 1"),
                       ("pad", "0.05 0.05 0.05 1"), ("table", "0.55 0.56 0.58 1"), ("tray", "0.36 0.22 0.15 1"),
                       ("box", "0.94 0.94 0.92 1")):
        shiny = {"alu": ' specular="0.8" shininess="0.7"', "steel": ' specular="1" shininess="0.9"'}.get(name, "")
        x.append(f'    <material name="{name}" rgba="{rgba}"{shiny}/>')
    # the gripper's finishes (owner's photos): brushed aluminium, shiny steel, matte black print, a light label
    for name, rgba, spec, shine in (("screw", "0.55 0.56 0.58 1", 0.9, 0.9), ("seam", "0.02 0.02 0.02 1", 0.1, 0.1),
                                    ("cover", "0.86 0.87 0.88 1", 0.3, 0.4), ("label", "0.93 0.90 0.86 1", 0.1, 0.2),
                                    ("zlogo", "0.10 0.35 0.75 1", 0.1, 0.2), ("slot", "0.62 0.63 0.65 1", 0.6, 0.6),
                                    ("pad_rib", "0.16 0.16 0.17 1", 0.05, 0.1)):
        x.append(f'    <material name="{name}" rgba="{rgba}" specular="{spec}" shininess="{shine}"/>')
    x.append('  </asset>')
    x.append('  <default>')
    x.append('    <default class="visual"><geom type="mesh" contype="0" conaffinity="0" group="2" density="0"/></default>')
    # the torso and head only for clearance checks in code (as on the robot), not as physical obstacles: the arm's
    # first link sits inside the column's collision cylinder
    x.append('    <default class="body_col"><geom group="3" density="0" contype="0" conaffinity="0" rgba="0.9 0.4 0.4 0.3"/></default>')
    x.append('    <default class="grip"><geom group="1" density="0" friction="0.8 0.01 0.001"/></default>')
    x.append('    <default class="gvis"><geom contype="0" conaffinity="0" group="2" density="0"/></default>')
    x.append('    <default class="pad"><geom group="1" density="0" friction="1.6 0.02 0.002" condim="4" solref="0.004 1" priority="1"/></default>')
    x.append('    <default class="arm_big"><position kp="1500" dampratio="1" forcerange="-60 60"/></default>')
    x.append('    <default class="arm_small"><position kp="400" dampratio="1" forcerange="-20 20"/></default>')
    x.append('  </default>')
    x.append('  <worldbody>')
    x.append('    <light pos="0 0.5 1.6" dir="0 0 -1" diffuse="0.8 0.8 0.8" castshadow="true"/>')
    x.append('    <light pos="-1 -1 1.2" dir="1 1 -1" diffuse="0.35 0.35 0.35"/>')
    x.append('    <light pos="0.3 2.0 0.8" dir="-0.1 -1 -0.4" diffuse="0.45 0.45 0.45"/>')   # from Lumi's front
    floor_z = FLOOR_Z
    x.append(f'    <geom name="floor" type="plane" pos="0 0 {floor_z:.3f}" size="3 3 0.05" material="floor"/>')
    x.append(f'    <camera name="torso_cam" pos="{fmt(cam_t)}" xyaxes="{fmt(cam_R[:, 0])} {fmt(-cam_R[:, 1])}" fovy="{fovy:.2f}"/>')
    x.append('    <camera name="overview" pos="0.55 1.35 0.25" xyaxes="-0.92 0.39 0 -0.15 -0.36 0.92" fovy="50"/>')
    x.append('    <camera name="top" pos="-0.10 0.58 0.55" xyaxes="1 0 0 0 1 0" fovy="70"/>')

    # torso, lift, head and base, fixed at the sorting pose
    x.append(f'    <body name="torso" {pose_attr(T2)}>')
    for i, (kind, mesh, Tg, size, mat) in enumerate(tgeoms):
        if kind == "mesh":                       # the URDF link's frame here: the app's parts of that link go on it
            for name in by_link.get(mesh, []):
                x.append(f'      <geom class="visual" mesh="{name}" {pose_attr(Tg)} material="{name}"/>')
        else:
            x.append(f'      <geom class="body_col" type="{kind}" {pose_attr(Tg)} size="{fmt(size[:3 if kind == "box" else 2])}"/>')
    x.append('    </body>')

    # arm: fitted joint frames, MiniCobo meshes
    x.append(f'    <body name="arm_base" {pose_attr(base)}>')
    ind = "      "
    for i in range(6):
        F = frames[i] @ hmat(rot("z", joint_offsets[i]), np.zeros(3))   # the zero offset is part of the body frame
        x.append(f'{ind}<body name="a{i + 1}" {pose_attr(F)} gravcomp="1">')
        x.append(f'{ind}  <inertial pos="0 0 0.05" mass="{[1.35, 1.6, 1.1, 0.7, 0.7, 0.3][i]}" diaginertia="0.005 0.005 0.002"/>')
        lim = math.radians(limits[i])
        x.append(f'{ind}  <joint name="j{i + 1}" axis="0 0 1" range="{-lim:.4f} {lim:.4f}" armature="0.1" damping="2"/>')
        for name in by_link[f"link_a{i + 1}"]:
            x.append(f'{ind}  <geom class="visual" mesh="{name}" {pose_attr(offsets[i])} material="{name}"/>')
        if i == 5:                               # the flange plate (link_at): 36 mm out along link_a6's z
            for name in by_link["link_at"]:
                x.append(f'{ind}  <geom class="visual" mesh="{name}" {pose_attr(offsets[i] @ hmat(np.eye(3), [0, 0, 0.036]))} material="{name}"/>')
        x.append(f'{ind}  <geom group="3" type="mesh" mesh="mc_a{i + 1}" {pose_attr(offsets[i])} density="0" rgba="0.4 0.6 0.9 0.3"/>')
        ind += "  "
    x.append(f'{ind}<site name="flange" size="0.005" group="4"/>')
    x += [ind + l for l in gripper_xml()]
    for i in range(6):
        ind = ind[:-2]
        x.append(f'{ind}</body>')
    x.append('    </body>')

    # table, tray, boxes, balls
    tc = (TRAY_C[0], TRAY_C[1] + 0.05)
    x.append(f'    <geom name="table" type="box" pos="{tc[0]:.3f} {tc[1]:.3f} {TABLE_Z - 0.015:.4f}" size="0.60 0.35 0.015" material="table"/>')
    for sx in (-0.55, 0.55):
        for sy in (-0.30, 0.30):
            x.append(f'    <geom type="box" pos="{tc[0] + sx:.3f} {tc[1] + sy:.3f} {(TABLE_Z - 0.03 + floor_z) / 2:.4f}" '
                     f'size="0.02 0.02 {(TABLE_Z - 0.03 - floor_z) / 2:.4f}" material="table" contype="0" conaffinity="0"/>')
    x += ["    " + g for g in open_box("tray", (*TRAY_C, TABLE_Z), TRAY_OUT, TRAY_WALL, TRAY_FLOOR, '0.36 0.22 0.15 1')]
    for colour, side in BOXES.items():
        bx = TRAY_C[0] + side * (TRAY_OUT[0] / 2 + BOX_GAP + BOX_OUT[0] / 2)
        x += ["    " + g for g in open_box(f"box_{colour}", (bx, TRAY_C[1], TABLE_Z), BOX_OUT, BOX_WALL, BOX_WALL,
                                            '0.94 0.94 0.92 1')]
        x.append(f'    <geom name="label_{colour}" type="box" pos="{bx:.4f} {TRAY_C[1] - BOX_OUT[1] / 2 - 0.001:.4f} '
                 f'{TABLE_Z + BOX_OUT[2] * 0.6:.4f}" size="0.04 0.0008 0.015" rgba="{COLOURS[colour]}" contype="0" conaffinity="0"/>')
    i = 0
    for row in (-0.5, 0.5):
        for col in (-1, 0, 1):
            colour = ("red", "yellow")[(col + 1 + (row > 0)) % 2]   # a checkerboard: three of each
            bx = TRAY_C[0] + col * BALL_GRID[0]
            by = TRAY_C[1] + row * BALL_GRID[1]
            x.append(f'    <body name="ball_{i}" pos="{bx:.4f} {by:.4f} {TABLE_Z + TRAY_FLOOR + BALL_R + 0.001:.4f}">')
            x.append('      <freejoint/>')
            x.append(f'      <geom name="ball_{i}" type="sphere" size="{BALL_R}" mass="{BALL_MASS}" rgba="{COLOURS[colour]}" '
                     f'friction="1.0 0.01 0.001" condim="4" solref="0.006 1"/>')
            x.append('    </body>')
            i += 1
    x.append('  </worldbody>')

    x.append('  <equality><joint joint1="jaw_r" joint2="jaw_l" polycoef="0 1 0 0 0"/></equality>')
    # the arm's own links and the gripper never touch each other here (the real arm's limits keep them apart)
    parts = [f"a{i}" for i in range(1, 7)] + ["gripper", "jaw_l", "jaw_r"]
    pairs = [(a, b) for k, a in enumerate(parts) for b in parts[k + 1:]]
    x.append('  <contact>' + "".join(f'<exclude body1="{a}" body2="{b}"/>' for a, b in pairs) + '</contact>')
    x.append('  <actuator>')
    for i in range(6):
        x.append(f'    <position name="j{i + 1}" class="{"arm_big" if i < 3 else "arm_small"}" joint="j{i + 1}" '
                 f'ctrlrange="{-math.radians(limits[i]):.4f} {math.radians(limits[i]):.4f}"/>')
    x.append(f'    <position name="gripper" joint="jaw_l" kp="4000" dampratio="1" forcerange="{-GRIP_FORCE} {GRIP_FORCE}" ctrlrange="0 {JAW_STROKE}"/>')
    x.append('  </actuator>')
    x.append('</mujoco>')
    OUT.write_text("\n".join(x) + "\n")
    print(f"wrote {OUT.relative_to(REPO)}")
    print("mesh placement spread over 40 poses (mm):", " ".join(f"a{i + 1} {s:.2f}" for i, s in enumerate(spread)))


if __name__ == "__main__":
    build()
