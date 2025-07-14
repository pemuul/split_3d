import pathlib
from typing import Tuple

import numpy as np
import trimesh

from .core import RULER_STEP_MM, TICK_SIZE_RATIO


def _plane_mesh(axis: str, coord: float, bounds: np.ndarray) -> trimesh.Trimesh:
    min_pt, max_pt = bounds
    thickness = (max_pt - min_pt).max() * 0.002
    if axis == "x":
        cmin = [coord - thickness, min_pt[1], min_pt[2]]
        cmax = [coord + thickness, max_pt[1], max_pt[2]]
    elif axis == "y":
        cmin = [min_pt[0], coord - thickness, min_pt[2]]
        cmax = [max_pt[0], coord + thickness, max_pt[2]]
    else:
        cmin = [min_pt[0], min_pt[1], coord - thickness]
        cmax = [max_pt[0], max_pt[1], coord + thickness]
    box = trimesh.creation.box(
        extents=np.array(cmax) - np.array(cmin),
        transform=trimesh.transformations.translation_matrix((np.array(cmin) + np.array(cmax)) / 2),
    )
    box.visual.face_colors = [200, 50, 50, 80]
    return box


def _axis_ruler(bounds: np.ndarray, axis: int, color: Tuple[int, int, int]) -> trimesh.path.Path3D:
    min_pt, max_pt = bounds
    length = max_pt[axis] - min_pt[axis]
    tick_len = length * TICK_SIZE_RATIO
    steps = int(length // RULER_STEP_MM) + 1
    lines = []
    for i in range(steps):
        coord = min_pt[axis] + i * RULER_STEP_MM
        if axis == 0:
            start, end = [coord, min_pt[1], min_pt[2]], [coord, min_pt[1], min_pt[2] + tick_len]
        elif axis == 1:
            start, end = [min_pt[0], coord, min_pt[2]], [min_pt[0] + tick_len, coord, min_pt[2]]
        else:
            start, end = [min_pt[0], min_pt[1], coord], [min_pt[0] + tick_len, min_pt[1], coord]
        lines.append([start, end])
    if axis == 0:
        lines.append([[min_pt[0], min_pt[1], min_pt[2]], [max_pt[0], min_pt[1], min_pt[2]]])
    elif axis == 1:
        lines.append([[min_pt[0], min_pt[1], min_pt[2]], [min_pt[0], max_pt[1], min_pt[2]]])
    else:
        lines.append([[min_pt[0], min_pt[1], min_pt[2]], [min_pt[0], min_pt[1], max_pt[2]]])
    path = trimesh.load_path(np.array(lines))
    rgba = np.array([*color, 255])
    path.colors = np.tile(rgba, (len(path.entities), 1))
    return path


def create_preview_scene(model_path: pathlib.Path, cell: Tuple[float, float, float]) -> trimesh.Scene:
    mesh = trimesh.load_mesh(model_path, force="mesh")
    scene = trimesh.Scene(mesh)
    for x in np.arange(mesh.bounds[0][0] + cell[0], mesh.bounds[1][0], cell[0]):
        scene.add_geometry(_plane_mesh("x", x, mesh.bounds))
    for y in np.arange(mesh.bounds[0][1] + cell[1], mesh.bounds[1][1], cell[1]):
        scene.add_geometry(_plane_mesh("y", y, mesh.bounds))
    for z in np.arange(mesh.bounds[0][2] + cell[2], mesh.bounds[1][2], cell[2]):
        scene.add_geometry(_plane_mesh("z", z, mesh.bounds))
    scene.add_geometry(_axis_ruler(mesh.bounds, 0, (255, 0, 0)))
    scene.add_geometry(_axis_ruler(mesh.bounds, 1, (0, 255, 0)))
    scene.add_geometry(_axis_ruler(mesh.bounds, 2, (0, 0, 255)))
    diag = np.linalg.norm(mesh.bounds[1] - mesh.bounds[0])
    scene.set_camera(angles=[0.3, -0.5, 0], distance=diag * 2, center=mesh.centroid)
    if hasattr(scene.camera, "z_near"):
        scene.camera.z_near = diag * 0.001
    if hasattr(scene.camera, "z_far"):
        scene.camera.z_far = diag * 10
    if hasattr(scene, "fog"):
        scene.fog = False
    return scene
