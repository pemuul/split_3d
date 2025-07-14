# Grid Split

`grid_split` is a small tool for slicing large 3D meshes into a grid of
smaller parts. It can be used from the command line or via a simple Tkinter
GUI. After slicing, it also provides a rough estimation of printing time for a
Bambu Lab printer.

## Installation

Python 3.10 or newer is recommended. Install the dependencies and the package
in editable mode:

```bash
pip install -e .
```

This will install the required packages (`trimesh`, `numpy`, `pyglet<2`).

## Usage

### Command line

```
python -m grid_split --input model.stl --size 250 250 250 --merged out.3mf
```

Use `--repair` to attempt watertight repair and `--fallback` to choose the
fallback mode (`planar` by default).

### GUI

Simply run:

```
python -m grid_split --gui
```

A window will open allowing you to select the model, output location and cell
size. After slicing the estimated printing time is shown in a popup.

