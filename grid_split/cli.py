import argparse
import pathlib
from typing import Tuple

from .core import slice_to_single
from .gui import launch_gui


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Split mesh into grid – single-file output")
    p.add_argument("--input", type=pathlib.Path, required=False, help="Mesh file")
    p.add_argument(
        "--size",
        nargs=3,
        type=float,
        metavar=("SX", "SY", "SZ"),
        required=False,
        help="Cell size, e.g. 250 250 250",
    )
    p.add_argument("--merged", type=pathlib.Path, required=False, help="Output path (.3mf/.obj)")
    p.add_argument("--repair", action="store_true", help="Attempt watertight repair")
    p.add_argument(
        "--fallback",
        choices=["none", "planar"],
        default="planar",
        help="Fallback mode",
    )
    p.add_argument("--gui", action="store_true", help="Launch GUI")
    return p


def main(argv: Tuple[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.gui:
        launch_gui()
        return
    if not (args.input and args.size and args.merged):
        parser.error("--input, --size, --merged required in CLI mode")
    slice_to_single(args.input, tuple(args.size), args.merged, repair=args.repair)
    print("Finished →", args.merged)


if __name__ == "__main__":
    main()
