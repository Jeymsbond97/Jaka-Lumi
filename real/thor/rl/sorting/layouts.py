"""Where the balls lie at the start of an episode (docs/sorting/03 §3): scattered (dropped and left to roll), a row,
a heap, touching pairs, or spread apart. All on the GPU for many environments at once.

Each function returns (xy, active) for M environments and B balls: xy (M, B, 2) in m, active (M, B) bool. A ball that
would lie outside the tray or inside another ball is made inactive, so a layout may hold fewer balls than asked;
at least one ball is always active.
"""
from __future__ import annotations

import math

import torch

SCATTERED, ROW, HEAP, PAIRS, SPREAD = range(5)
NAMES = ("scattered", "row", "heap", "pairs", "spread")


def _uniform(lo, hi, shape, device):
    return lo + (hi - lo) * torch.rand(shape, device=device)


def _sample_apart(n, centre, half, r, gap, M, B, device, tries=16):
    """Up to `n` balls placed one by one at random spots at least 2r + gap apart."""
    xy = torch.zeros(M, B, 2, device=device)
    ok = torch.zeros(M, B, dtype=torch.bool, device=device)
    for b in range(B):
        want = b < n
        for _ in range(tries):
            p = torch.stack([_uniform(centre[0] - half[0], centre[0] + half[0], (M,), device),
                             _uniform(centre[1] - half[1], centre[1] + half[1], (M,), device)], -1)
            if b == 0:
                free = torch.ones(M, dtype=torch.bool, device=device)
            else:
                d = torch.linalg.norm(xy[:, :b] - p[:, None], dim=-1)
                d = torch.where(ok[:, :b], d, torch.full_like(d, 1e3))
                free = d.min(-1).values >= 2 * r + gap
            take = want & free & ~ok[:, b]
            xy[take, b] = p[take]
            ok[:, b] |= take
    return xy, ok


def _row(n, centre, half, r, M, B, device):
    p0 = torch.stack([_uniform(centre[0] - half[0], centre[0] + half[0], (M,), device),
                      _uniform(centre[1] - half[1], centre[1] + half[1], (M,), device)], -1)
    ang = _uniform(0, math.pi, (M,), device)
    xy = torch.zeros(M, B, 2, device=device)
    xy[:, 0] = p0
    for b in range(1, B):
        ang = ang + _uniform(-0.2, 0.2, (M,), device)          # a row may bend a little
        step = (2 * r + 0.0005) * torch.stack([torch.cos(ang), torch.sin(ang)], -1)
        xy[:, b] = xy[:, b - 1] + step
    return xy, torch.arange(B, device=device)[None, :] < n[:, None]


def _heap(n, centre, half, r, M, B, device):
    """A packed heap: the hexagonal rings around a random point, turned at random."""
    s = 2 * r + 0.0005
    pts = [(0.0, 0.0)] + [(s * math.cos(a), s * math.sin(a)) for a in [k * math.pi / 3 for k in range(6)]]
    pts += [(2 * s * math.cos(a), 2 * s * math.sin(a)) for a in [k * math.pi / 3 for k in range(6)]]
    pts += [(s * math.sqrt(3) * math.cos(a), s * math.sqrt(3) * math.sin(a))
            for a in [math.pi / 6 + k * math.pi / 3 for k in range(6)]]
    pts = torch.tensor(pts[:max(B, 1)] if len(pts) >= B else pts, device=device)
    c = torch.stack([_uniform(centre[0] - half[0] * 0.5, centre[0] + half[0] * 0.5, (M,), device),
                     _uniform(centre[1] - half[1] * 0.5, centre[1] + half[1] * 0.5, (M,), device)], -1)
    rot = _uniform(0, 2 * math.pi, (M,), device)
    cs, sn = torch.cos(rot), torch.sin(rot)
    R = torch.stack([torch.stack([cs, -sn], -1), torch.stack([sn, cs], -1)], -2)        # (M, 2, 2)
    xy = torch.zeros(M, B, 2, device=device)
    k = min(B, len(pts))
    xy[:, :k] = c[:, None] + torch.einsum("mij,kj->mki", R, pts[:k])
    return xy, torch.arange(B, device=device)[None, :] < n[:, None]


def _pairs(n, centre, half, r, M, B, device):
    """Balls in touching pairs: anchors apart, each with a partner against it."""
    anchors, ok = _sample_apart((n + 1) // 2, centre, half, r, 4 * r + 0.01, M, (B + 1) // 2, device)
    ang = _uniform(0, 2 * math.pi, (M, anchors.shape[1]), device)
    partner = anchors + (2 * r + 0.0005) * torch.stack([torch.cos(ang), torch.sin(ang)], -1)
    xy = torch.zeros(M, B, 2, device=device)
    xy[:, 0::2] = anchors[:, : (B + 1) // 2]
    xy[:, 1::2] = partner[:, : B // 2]
    act = torch.zeros(M, B, dtype=torch.bool, device=device)
    act[:, 0::2] = ok[:, : (B + 1) // 2]
    act[:, 1::2] = ok[:, : B // 2]
    return xy, act & (torch.arange(B, device=device)[None, :] < n[:, None])


def make(kind, n, centre, inner_half, r, B, device):
    """Layouts for M = len(kind) environments: kind (M,) of SCATTERED..SPREAD, n (M,) balls wanted (1..B)."""
    M = kind.shape[0]
    half = (inner_half[0] - r - 0.002, inner_half[1] - r - 0.002)
    xy = torch.zeros(M, B, 2, device=device)
    act = torch.zeros(M, B, dtype=torch.bool, device=device)
    for k, fn in ((SCATTERED, None), (ROW, _row), (HEAP, _heap), (PAIRS, _pairs), (SPREAD, None)):
        sel = kind == k
        if not sel.any():
            continue
        m = int(sel.sum())
        if k == SCATTERED:
            x, a = _sample_apart(n[sel], centre, half, r, 0.001, m, B, device)
        elif k == SPREAD:
            x, a = _sample_apart(n[sel], centre, half, r, 0.02, m, B, device)
        else:
            x, a = fn(n[sel], centre, half, r, m, B, device)
        xy[sel], act[sel] = x, a
    # inside the tray, and not inside another ball
    inside = ((xy[..., 0] - centre[0]).abs() <= half[0] + 1e-4) & ((xy[..., 1] - centre[1]).abs() <= half[1] + 1e-4)
    act &= inside
    d = torch.linalg.norm(xy[:, :, None] - xy[:, None], dim=-1)
    clash = (d < 2 * r - 0.001) & act[:, :, None] & act[:, None, :]
    clash = torch.triu(clash, diagonal=1).any(1)                 # the later of two clashing balls goes
    act &= ~clash
    none = ~act.any(1)
    xy[none, 0] = torch.tensor(centre, device=device)
    act[none, 0] = True
    return xy, act
