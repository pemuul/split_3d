import pathlib
import sys
import threading
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import trimesh

from .core import slice_to_single
from .preview import create_preview_scene


def launch_gui():
    """Launch the Tkinter GUI application."""
    try:
        import pyglet  # noqa: F401
    except ImportError:
        messagebox.showerror("Missing pyglet<2", 'Run "pip install pyglet<2"')
        sys.exit(1)

    root = tk.Tk()
    root.title("Grid Split")
    root.geometry("520x320")

    frm = ttk.Frame(root, padding=10)
    frm.pack(fill=tk.BOTH, expand=True)

    def row(r, text):
        ttk.Label(frm, text=text).grid(row=r, column=0, sticky="e", pady=4)

    def b_open(e):
        path = filedialog.askopenfilename(
            title="Select model",
            filetypes=[("Mesh", "*.stl *.obj *.ply *.3mf"), ("All", "*.*")],
        )
        if path:
            e.delete(0, "end")
            e.insert(0, path)

    def b_save(e):
        path = filedialog.asksaveasfilename(
            defaultextension=".3mf",
            filetypes=[("3MF", "*.3mf"), ("OBJ", "*.obj")],
        )
        if path:
            e.delete(0, "end")
            e.insert(0, path)

    row(0, "Model file:")
    in_e = ttk.Entry(frm, width=48)
    in_e.grid(row=0, column=1, sticky="we")
    ttk.Button(frm, text="…", command=lambda: b_open(in_e)).grid(row=0, column=2)

    row(1, "Output file:")
    out_e = ttk.Entry(frm, width=48)
    out_e.grid(row=1, column=1, sticky="we")
    ttk.Button(frm, text="…", command=lambda: b_save(out_e)).grid(row=1, column=2)

    row(2, "Cell size XYZ:")
    sx = ttk.Entry(frm, width=8)
    sx.insert(0, "250")
    sx.grid(row=2, column=1, sticky="w")
    sy = ttk.Entry(frm, width=8)
    sy.insert(0, "250")
    sy.grid(row=2, column=1)
    sz = ttk.Entry(frm, width=8)
    sz.insert(0, "250")
    sz.grid(row=2, column=1, sticky="e")

    rep_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(frm, text="Repair mesh", variable=rep_var).grid(row=3, column=1, sticky="w")

    prog = ttk.Progressbar(frm, length=350, mode="determinate")
    prog.grid(row=4, column=0, columnspan=3, pady=6)

    def on_preview():
        try:
            mp = pathlib.Path(in_e.get())
            if not mp.exists():
                raise FileNotFoundError("Select model")
            cell = (float(sx.get()), float(sy.get()), float(sz.get()))
            scene = create_preview_scene(mp, cell)
            scene.show()
        except Exception as e:
            messagebox.showerror("Preview Error", str(e))

    def on_slice():
        def worker():
            try:
                mp = pathlib.Path(in_e.get())
                op = pathlib.Path(out_e.get())
                cell = (float(sx.get()), float(sy.get()), float(sz.get()))
                prog["value"] = 0

                def cb(d, t):
                    prog.config(maximum=t, value=d)

                slice_to_single(mp, cell, op, repair=rep_var.get(), progress=cb)
                mesh = trimesh.load_mesh(mp, force="mesh")
                vol = mesh.volume
                area = mesh.area
                infill = 0.10
                perimeters = 2
                line_width = 0.4
                shell_thickness = perimeters * line_width
                extruded_vol = vol * infill + area * shell_thickness
                flow_rate = 21.0
                t_sec = extruded_vol / flow_rate
                h = int(t_sec // 3600)
                m = int((t_sec % 3600) // 60)
                s = int(t_sec % 60)
                time_str = f"{h}h {m}m {s}s"
                messagebox.showinfo(
                    "Grid Split", f"Saved → {op}\nEstimated print time: {time_str}"
                )
                prog["value"] = 0
            except Exception as e:
                messagebox.showerror("Slice Error", str(e))
                prog["value"] = 0

        threading.Thread(target=worker, daemon=True).start()

    btn_fr = ttk.Frame(frm, padding=10)
    btn_fr.grid(row=5, column=0, columnspan=3)
    ttk.Button(btn_fr, text="Preview", command=on_preview).pack(side="left", padx=5)
    ttk.Button(btn_fr, text="Slice", command=on_slice).pack(side="left", padx=5)

    frm.columnconfigure(1, weight=1)
    root.mainloop()

