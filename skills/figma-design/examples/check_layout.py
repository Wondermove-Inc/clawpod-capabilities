#!/usr/bin/env python3
"""Find layout defects a render can hide.

  - frames left at 100 x 100 (no sizing was set)
  - text boxes shorter than one line of their text
  - text that runs past its screen or a clipping frame
  - a frame or instance that an auto-layout parent cuts off (content pushed out of a screen)
  - two text layers of one frame that overlap each other
  - top-level frames (200 px or more on each side) that overlap each other on a page

Hidden layers are skipped, and so are rotated or flipped layers and anything inside a scrolling frame.
It does not measure text: a fixed box that holds more lines than fit, or a line cut by a
neighbour in another frame, shows only in the render.

usage: python3 check_layout.py design.figcraft [more files...]
exit:  0 nothing found (or a file could not be checked: the line says NOT CHECKED),
       1 something to look at, 2 a file is missing or unreadable, or figcraft-cli is missing

It reads the document through `figcraft-cli convert file out.json`. That JSON is FigCraft's
own format and may change between versions: when the fields this script needs are not
there it says NOT CHECKED instead of "ok", and the check is done by eye. A clean result
does not replace looking at the render; it only catches what is easy to miss there.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

BOXES = ("frame", "instance", "component")


class Unreadable(Exception):
    """figcraft-cli could not open the file: not a design file, or damaged."""


def load(path: str) -> dict:
    if not Path(path).is_file():
        raise FileNotFoundError(path)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "doc.json"
        run = subprocess.run(["figcraft-cli", "convert", path, str(out)], capture_output=True, text=True)
        if run.returncode != 0:
            raise Unreadable(run.stderr.strip()[:200] or "figcraft-cli convert failed")
        nodes = {int(k): v for k, v in json.loads(out.read_text(encoding="utf-8"))["nodes"].items()}
    # The fields every check below depends on. If a version renames them, say so instead of reporting "ok".
    if not any(n.get("type") == "page" for n in nodes.values()):
        raise ValueError("no node of type 'page'")
    layers = [n for n in nodes.values() if n.get("type") != "page"]
    if layers and not all("width" in n and "height" in n and "parent" in n for n in layers):
        raise ValueError("layers without width, height or parent")
    if layers and not any("transform" in n for n in layers):
        raise ValueError("no layer has a transform")
    return nodes


def check(path: str) -> list[str]:
    return scan(load(path))


def scan(nodes: dict) -> list[str]:
    def origin(node_id: int) -> tuple[float, float]:
        x = y = 0.0
        while node_id in nodes and nodes[node_id].get("type") != "page":
            transform = nodes[node_id].get("transform") or [1, 0, 0, 1, 0, 0]
            x, y = x + transform[4], y + transform[5]
            node_id = nodes[node_id].get("parent")
        return x, y

    def ancestors(node_id: int):
        node_id = nodes[node_id].get("parent")
        while node_id in nodes and nodes[node_id].get("type") != "page":
            yield node_id
            node_id = nodes[node_id].get("parent")

    def label(node_id: int) -> str:
        names = [nodes[i].get("name", "?") for i in [node_id, *ancestors(node_id)]]
        return " < ".join(names[:4])

    def hidden(node_id: int) -> bool:
        return any(nodes[i].get("visible") is False for i in [node_id, *ancestors(node_id)])

    def rotated(node_id: int) -> bool:  # positions below are sums of offsets: only right for layers neither rotated nor flipped
        chain = [nodes[i].get("transform") or [1, 0, 0, 1, 0, 0] for i in [node_id, *ancestors(node_id)]]
        return any(abs(t[1]) > 1e-6 or abs(t[2]) > 1e-6 or t[0] < 0 or t[3] < 0 for t in chain)

    def scrolls(node: dict) -> bool:
        return node.get("overflow") not in (None, "none")

    def outside(node_id: int, frame_id: int) -> bool:
        node, frame = nodes[node_id], nodes[frame_id]
        x, y = origin(node_id)
        fx, fy = origin(frame_id)
        return x + 1 < fx or y + 1 < fy or x + node["width"] > fx + frame["width"] + 1 or y + node["height"] > fy + frame["height"] + 1

    found = []
    for node_id, node in nodes.items():
        kind, width, height = node.get("type"), node.get("width", 0), node.get("height", 0)
        if kind == "page" or hidden(node_id) or rotated(node_id):
            continue
        chain = list(ancestors(node_id))  # nearest ancestor first
        if kind == "frame" and width == 100 and height == 100:
            found.append(f"frame still 100 x 100 (no sizing set?): {label(node_id)}")
        if kind in BOXES and chain:
            parent = nodes[chain[0]]
            flows = (parent.get("layout") or {}).get("mode") in ("horizontal", "vertical", "grid")
            placed = (node.get("child_layout") or {}).get("absolute")
            if flows and not placed and parent.get("clip") and not any(scrolls(nodes[i]) for i in chain) and outside(node_id, chain[0]):
                found.append(f"cut off by its auto-layout parent '{parent.get('name')}': {label(node_id)}")
        if kind != "text":
            continue
        style = node.get("style") or {}
        line = style.get("line_height") or {}
        size = style.get("font_size") or 0
        # An automatic line height depends on the font, but a line is never shorter than its font size.
        line_px = line.get("value", 0) if line.get("unit") == "pixels" else size * line.get("value", 0) / 100 if line.get("unit") == "percent" else size
        trimmed = node.get("leading_trim") not in (None, "none")  # cap-height trim makes the box shorter than the line on purpose
        if line_px and not trimmed and height + 0.5 < line_px:
            found.append(f"text box {height:g} px high, one line needs {line_px:g}: {label(node_id)}")
        for frame_id in chain:
            frame = nodes[frame_id]
            if scrolls(frame):
                break  # inside a scrolling frame, content past the edge is the point
            if not (frame.get("clip") or frame_id == chain[-1]):
                continue
            if not frame.get("width") and not frame.get("height"):
                continue  # a 0 x 0 holder (imported files keep library components in one) is not a screen
            if outside(node_id, frame_id):
                found.append(f"text runs outside '{frame.get('name')}': {label(node_id)}")
                break

    for parent_id, parent in nodes.items():
        texts = [i for i in parent.get("children") or [] if i in nodes and nodes[i].get("type") == "text" and not hidden(i) and not rotated(i)]
        boxes = {i: (*origin(i), nodes[i]["width"], nodes[i]["height"]) for i in texts}
        for n, a in enumerate(texts):
            for b in texts[n + 1:]:
                ax, ay, aw, ah = boxes[a]
                bx, by, bw, bh = boxes[b]
                if min(ax + aw, bx + bw) - max(ax, bx) > 2 and min(ay + ah, by + bh) - max(ay, by) > 2:
                    found.append(f"text layers overlap in '{parent.get('name')}': '{nodes[a].get('name')}' and '{nodes[b].get('name')}'")

    for page in (n for n in nodes.values() if n.get("type") == "page"):
        # Screens and sheets only: small top-level frames (stamps on a board, stickers) overlap things on purpose.
        tops = [i for i in page.get("children") or [] if i in nodes and nodes[i].get("type") == "frame" and not hidden(i) and min(nodes[i]["width"], nodes[i]["height"]) >= 200]
        boxes = {i: (*origin(i), nodes[i]["width"], nodes[i]["height"]) for i in tops}
        for n, a in enumerate(tops):
            for b in tops[n + 1:]:
                ax, ay, aw, ah = boxes[a]
                bx, by, bw, bh = boxes[b]
                if min(ax + aw, bx + bw) - max(ax, bx) > 1 and min(ay + ah, by + bh) - max(ay, by) > 1:
                    found.append(f"top-level frames overlap on page '{page.get('name')}': '{nodes[a].get('name')}' and '{nodes[b].get('name')}'")
    return found


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    status = 0
    for path in sys.argv[1:]:
        try:
            found = check(path)
        except FileNotFoundError as error:
            if error.filename == path or str(error) == path:
                print(f"{path}: no such file")
                status = 2
                continue
            print("figcraft-cli is not on PATH: run this where FigCraft is installed")
            return 2
        except Unreadable as error:
            print(f"{path}: figcraft-cli could not read this file ({error})")
            status = 2
            continue
        except Exception as error:  # the document JSON is not a stable interface
            print(f"{path}: NOT CHECKED, this FigCraft version's JSON is not what the script reads ({type(error).__name__}: {error}); check the render by eye")
            continue
        print(f"{path}: {'ok' if not found else str(len(found)) + ' to look at'}")
        for line in found:
            print("  " + line)
        status = status or (1 if found else 0)
    return status


if __name__ == "__main__":
    sys.exit(main())
