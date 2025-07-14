#!/usr/bin/env python3
"""grid_split.py – v3.4  (2025-07-13) + Print Time Estimation
=====================================
* Split mesh into one multi-object file (OBJ/3MF).
* Preview with pyglet window: cutting planes, millimeter rulers, no fog.
* After slicing, estimates 3D print time for Bambu Lab P1S with:
  - Layer height: 0.2 mm
  - Infill: 10%
  - Perimeters: 2
  - Line width: 0.4 mm
  - Volumetric flow: 21 mm³/s

Requirements:
    pip install trimesh numpy pyglet<2

Usage GUI:
    python grid_split.py --gui

Usage CLI:
    python grid_split.py --input model.stl --size 250 250 250 --merged out.3mf
"""
import argparse
import pathlib
import sys
import threading
from typing import Optional, Tuple

import numpy as np
import trimesh

# Constants for preview
RULER_STEP_MM = 100
TICK_SIZE_RATIO = 0.02

# ----------------------------------------------------------------------------
# Slicing core
# ----------------------------------------------------------------------------

def repair_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    m = mesh.copy()
    m.remove_infinite_values()
    m.remove_duplicate_faces()
    m.remove_degenerate_faces()
    trimesh.repair.fill_holes(m)
    m.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(m)
    return m
 

def build_grid(bounds: np.ndarray, step: Tuple[float, float, float]):
    min_pt, max_pt = bounds
    xs = np.arange(min_pt[0], max_pt[0] + step[0], step[0])
    ys = np.arange(min_pt[1], max_pt[1] + step[1], step[1])
    zs = np.arange(min_pt[2], max_pt[2] + step[2], step[2])
    cells = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            for k in range(len(zs) - 1):
                cmin = np.array([xs[i], ys[j], zs[k]])
                cmax = np.array([xs[i+1], ys[j+1], zs[k+1]])
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
    mesh = trimesh.load_mesh(input_path, force="mesh")
    if repair and not mesh.is_watertight:
        mesh = repair_mesh(mesh)
    scene = trimesh.Scene()
    cells = build_grid(mesh.bounds, size)
    total = len(cells)
    for idx, (cmin, cmax, (ix, jy, kz)) in enumerate(cells, 1):
        try:
            box = trimesh.creation.box(
                extents=cmax-cmin,
                transform=trimesh.transformations.translation_matrix((cmin+cmax)/2)
            )
            part = trimesh.boolean.intersection([mesh, box], engine=None, resolution=32)
        except Exception:
            part = None
            if fallback == "planar":
                v = mesh.vertices
                inside = np.logical_and.reduce([
                    v[:,0] >= cmin[0], v[:,0] <= cmax[0],
                    v[:,1] >= cmin[1], v[:,1] <= cmax[1],
                    v[:,2] >= cmin[2], v[:,2] <= cmax[2],
                ])
                mask = inside[mesh.faces].all(axis=1)
                part = mesh.submesh([mask], append=True, repair=False)
        if part is not None and part.volume >= tol:
            scene.add_geometry(part, node_name=f"chunk_{ix}_{jy}_{kz}")
        if progress:
            progress(idx, total)
    scene.export(merged_path)

# ----------------------------------------------------------------------------
# Preview helpers
# ----------------------------------------------------------------------------

def _plane_mesh(axis: str, coord: float, bounds: np.ndarray) -> trimesh.Trimesh:
    min_pt, max_pt = bounds
    thickness = (max_pt - min_pt).max() * 0.002
    if axis == 'x':
        cmin = [coord - thickness, min_pt[1], min_pt[2]]
        cmax = [coord + thickness, max_pt[1], max_pt[2]]
    elif axis == 'y':
        cmin = [min_pt[0], coord - thickness, min_pt[2]]
        cmax = [max_pt[0], coord + thickness, max_pt[2]]
    else:
        cmin = [min_pt[0], min_pt[1], coord - thickness]
        cmax = [max_pt[0], max_pt[1], coord + thickness]
    box = trimesh.creation.box(
        extents=np.array(cmax) - np.array(cmin),
        transform=trimesh.transformations.translation_matrix((np.array(cmin) + np.array(cmax)) / 2)
    )
    box.visual.face_colors = [200, 50, 50, 80]
    return box


def _axis_ruler(bounds: np.ndarray, axis: int, color: Tuple[int,int,int]) -> trimesh.path.Path3D:
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
    # main axis
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


def create_preview_scene(model_path: pathlib.Path, cell: Tuple[float,float,float]) -> trimesh.Scene:
    mesh = trimesh.load_mesh(model_path, force='mesh')
    scene = trimesh.Scene(mesh)
    for x in np.arange(mesh.bounds[0][0] + cell[0], mesh.bounds[1][0], cell[0]):
        scene.add_geometry(_plane_mesh('x', x, mesh.bounds))
    for y in np.arange(mesh.bounds[0][1] + cell[1], mesh.bounds[1][1], cell[1]):
        scene.add_geometry(_plane_mesh('y', y, mesh.bounds))
    for z in np.arange(mesh.bounds[0][2] + cell[2], mesh.bounds[1][2], cell[2]):
        scene.add_geometry(_plane_mesh('z', z, mesh.bounds))
    scene.add_geometry(_axis_ruler(mesh.bounds, 0, (255,0,0)))
    scene.add_geometry(_axis_ruler(mesh.bounds, 1, (0,255,0)))
    scene.add_geometry(_axis_ruler(mesh.bounds, 2, (0,0,255)))
    diag = np.linalg.norm(mesh.bounds[1] - mesh.bounds[0])
    scene.set_camera(angles=[0.3, -0.5, 0], distance=diag*2, center=mesh.centroid)
    if hasattr(scene.camera, 'z_near'): scene.camera.z_near = diag*0.001
    if hasattr(scene.camera, 'z_far'):  scene.camera.z_far  = diag*10
    if hasattr(scene, 'fog'):         scene.fog        = False
    return scene

# ----------------------------------------------------------------------------
# CLI parser
# ----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Split mesh into grid – single-file output')
    p.add_argument('--input',  type=pathlib.Path, required=False, help='Mesh file')
    p.add_argument('--size', nargs=3, type=float, metavar=('SX','SY','SZ'), required=False,
                   help='Cell size, e.g. 250 250 250')
    p.add_argument('--merged', type=pathlib.Path, required=False, help='Output path (.3mf/.obj)')
    p.add_argument('--repair', action='store_true', help='Attempt watertight repair')
    p.add_argument('--fallback', choices=['none','planar'], default='planar', help='Fallback mode')
    p.add_argument('--gui',    action='store_true', help='Launch GUI')
    return p

# ----------------------------------------------------------------------------
# GUI app
# ----------------------------------------------------------------------------

def launch_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    try:
        import pyglet  # noqa: F401
    except ImportError:
        messagebox.showerror('Missing pyglet<2', 'pip install "pyglet<2>"')
        sys.exit(1)

    root = tk.Tk()
    root.title('Grid Split')
    root.geometry('520x320')

    frm = ttk.Frame(root, padding=10)
    frm.pack(fill=tk.BOTH, expand=True)

    def row(r, text):
        ttk.Label(frm, text=text).grid(row=r, column=0, sticky='e', pady=4)

    def b_open(e):
        path = filedialog.askopenfilename(title='Select model', filetypes=[('Mesh','*.stl *.obj *.ply *.3mf'),('All','*.*')])
        if path:
            e.delete(0, 'end')
            e.insert(0, path)

    def b_save(e):
        path = filedialog.asksaveasfilename(defaultextension='.3mf', filetypes=[('3MF','*.3mf'),('OBJ','*.obj')])
        if path:
            e.delete(0, 'end')
            e.insert(0, path)

    row(0, 'Model file:')
    in_e = ttk.Entry(frm, width=48); in_e.grid(row=0, column=1, sticky='we')
    ttk.Button(frm, text='…', command=lambda: b_open(in_e)).grid(row=0, column=2)

    row(1, 'Output file:')
    out_e=ttk.Entry(frm, width=48); out_e.grid(row=1, column=1, sticky='we')
    ttk.Button(frm, text='…', command=lambda: b_save(out_e)).grid(row=1, column=2)

    row(2, 'Cell size XYZ:')
    sx = ttk.Entry(frm, width=8); sx.insert(0, '250'); sx.grid(row=2, column=1, sticky='w')
    sy = ttk.Entry(frm, width=8); sy.insert(0, '250'); sy.grid(row=2, column=1)
    sz = ttk.Entry(frm, width=8); sz.insert(0, '250'); sz.grid(row=2, column=1, sticky='e')

    rep_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(frm, text='Repair mesh', variable=rep_var).grid(row=3, column=1, sticky='w')

    prog = ttk.Progressbar(frm, length=350, mode='determinate')
    prog.grid(row=4, column=0, columnspan=3, pady=6)

    def on_preview():
        try:
            mp = pathlib.Path(in_e.get())
            if not mp.exists(): raise FileNotFoundError('Select model')
            cell = (float(sx.get()), float(sy.get()), float(sz.get()))
            scene = create_preview_scene(mp, cell)
            scene.show()
        except Exception as e:
            messagebox.showerror('Preview Error', str(e))

    def on_slice():
        def worker():
            try:
                mp = pathlib.Path(in_e.get())
                op = pathlib.Path(out_e.get())
                cell = (float(sx.get()), float(sy.get()), float(sz.get()))
                prog['value']=0
                def cb(d,t): prog.config(maximum=t, value=d)
                # slice
                slice_to_single(mp, cell, op, repair=rep_var.get(), progress=cb)
                # estimate print time
                mesh = trimesh.load_mesh(mp, force='mesh')
                vol = mesh.volume                                  # mm^3
                area = mesh.area                                    # mm^2
                infill = 0.10
                perimeters = 2
                line_width = 0.4                                  # mm
                shell_thickness = perimeters * line_width        # mm
                extruded_vol = vol * infill + area * shell_thickness
                flow_rate = 21.0                                  # mm^3/s
                t_sec = extruded_vol / flow_rate
                h = int(t_sec // 3600); m = int((t_sec % 3600)//60); s = int(t_sec % 60)
                time_str = f"{h}h {m}m {s}s"
                messagebox.showinfo('Grid Split', f"Saved → {op}\nEstimated print time: {time_str}")
                prog['value']=0
            except Exception as e:
                messagebox.showerror('Slice Error', str(e))
                prog['value']=0
        threading.Thread(target=worker, daemon=True).start()

    btn_fr = ttk.Frame(frm, padding=10)
    btn_fr.grid(row=5, column=0, columnspan=3)
    ttk.Button(btn_fr, text='Preview', command=on_preview).pack(side='left', padx=5)
    ttk.Button(btn_fr, text='Slice',   command=on_slice  ).pack(side='left', padx=5)

    frm.columnconfigure(1, weight=1)
    root.mainloop()

# ----------------------------------------------------------------------------
if __name__ == '__main__':
    parser = build_parser()
    args = parser.parse_args()
    if args.gui:
        launch_gui(); sys.exit(0)
    if not (args.input and args.size and args.merged):
        parser.error('--input, --size, --merged required in CLI mode')
    slice_to_single(args.input, tuple(args.size), args.merged, repair=args.repair)
    print('Finished →', args.merged)
