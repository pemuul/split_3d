import pathlib
from typing import Optional, Tuple

import numpy as np
import trimesh

# Constants for preview
RULER_STEP_MM = 100
TICK_SIZE_RATIO = 0.02


def repair_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Attempt to repair a mesh to make it watertight."""
    m = mesh.copy()
    m.remove_infinite_values()
    m.remove_duplicate_faces()
    m.remove_degenerate_faces()
    trimesh.repair.fill_holes(m)
    m.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(m)
    return m


def build_grid(bounds: np.ndarray, step: Tuple[float, float, float]):
    """Create a list of grid cells for the given bounds."""
    min_pt, max_pt = bounds
    xs = np.arange(min_pt[0], max_pt[0] + step[0], step[0])
    ys = np.arange(min_pt[1], max_pt[1] + step[1], step[1])
    zs = np.arange(min_pt[2], max_pt[2] + step[2], step[2])
    cells = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            for k in range(len(zs) - 1):
                cmin = np.array([xs[i], ys[j], zs[k]])
                cmax = np.array([xs[i + 1], ys[j + 1], zs[k + 1]])
                cells.append((cmin, cmax, (i, j, k)))
    return cells


def slice_to_single(
    input_path: pathlib.Path,
    size: Tuple[float, float, float],
    merged_path: pathlib.Path,
    repair: bool = True,
    fallback: str = "planar",
    tol: float = 1e-6,
    progress: Optional[callable] = None,
):
    """Slice a mesh into a grid and save the result as a single scene."""
    mesh = trimesh.load_mesh(input_path, force="mesh")
    if repair and not mesh.is_watertight:
        mesh = repair_mesh(mesh)

    scene = trimesh.Scene()
    cells = build_grid(mesh.bounds, size)
    total = len(cells)
    for idx, (cmin, cmax, (ix, jy, kz)) in enumerate(cells, 1):
        try:
            box = trimesh.creation.box(
                extents=cmax - cmin,
                transform=trimesh.transformations.translation_matrix((cmin + cmax) / 2),
            )
            part = trimesh.boolean.intersection([mesh, box], engine=None, resolution=32)
        except Exception:
            part = None
            if fallback == "planar":
                v = mesh.vertices
                inside = np.logical_and.reduce(
                    [
                        v[:, 0] >= cmin[0],
                        v[:, 0] <= cmax[0],
                        v[:, 1] >= cmin[1],
                        v[:, 1] <= cmax[1],
                        v[:, 2] >= cmin[2],
                        v[:, 2] <= cmax[2],
                    ]
                )
                mask = inside[mesh.faces].all(axis=1)
                part = mesh.submesh([mask], append=True, repair=False)
        if part is not None and part.volume >= tol:
            scene.add_geometry(part, node_name=f"chunk_{ix}_{jy}_{kz}")
        if progress:
            progress(idx, total)
    scene.export(merged_path)
