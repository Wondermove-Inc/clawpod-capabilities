"""Structured observation support for commercial-grade desktop computer use.

Combines screenshot, active-window data, app/window inventory, and AT-SPI node
metadata into one JSON object that can drive an observe -> act -> verify loop.
"""

import hashlib
import json
import os
import subprocess
import sys
import time

os.environ.setdefault('DISPLAY', ':99')

from . import atspi_engine

_ENV = {**os.environ, 'DISPLAY': ':99'}


def _run(cmd, timeout=5):
    try:
        result = subprocess.run(cmd, env=_ENV, capture_output=True, text=True, timeout=timeout)
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
        }
    except Exception as exc:
        return {"ok": False, "stdout": "", "stderr": str(exc), "returncode": None}


def _screenshot(path):
    if not path:
        return None
    for cmd in (['scrot', path], ['import', '-window', 'root', path]):
        result = _run(cmd, timeout=10)
        if result["ok"] and os.path.exists(path):
            return {"path": path, "bytes": os.path.getsize(path), "sha256": _sha256(path)}
    # Last resort without shell interpolation. Do not build a shell pipeline here:
    # screenshot paths are user-controlled and must never be interpreted by a shell.
    try:
        xwd = subprocess.Popen(
            ['xwd', '-root', '-display', ':99'],
            env=_ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        convert = subprocess.Popen(
            ['convert', 'xwd:-', path],
            env=_ENV, stdin=xwd.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if xwd.stdout:
            xwd.stdout.close()
        _, convert_err = convert.communicate(timeout=10)
        _, xwd_err = xwd.communicate(timeout=2)
        if convert.returncode == 0 and xwd.returncode == 0 and os.path.exists(path):
            return {"path": path, "bytes": os.path.getsize(path), "sha256": _sha256(path)}
    except Exception:
        try:
            xwd.kill()
        except Exception:
            pass
        try:
            convert.kill()
        except Exception:
            pass
    return {"path": path, "error": "screenshot failed"}


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _active_window():
    title = _run(['xdotool', 'getactivewindow', 'getwindowname'])
    wid = _run(['xdotool', 'getactivewindow'])
    return {
        "window_id": wid["stdout"] if wid["ok"] else None,
        "title": title["stdout"] if title["ok"] else None,
        "error": None if title["ok"] else title["stderr"],
    }


def _screen_size():
    result = _run(['xdpyinfo'])
    if result["ok"]:
        for line in result["stdout"].splitlines():
            line = line.strip()
            if line.startswith('dimensions:'):
                dims = line.split()[1]
                if 'x' in dims:
                    w, h = dims.split('x', 1)
                    return {"width": int(w), "height": int(h)}
    return {"width": None, "height": None}


def _node_path(parent_path, index):
    return f"{parent_path}/{index}" if parent_path else str(index)


def _node_actions(node):
    actions = []
    try:
        action = node.get_action_iface()
        if action:
            for i in range(action.get_n_actions()):
                try:
                    actions.append(action.get_action_name(i))
                except Exception:
                    pass
    except Exception:
        pass
    return actions


def _node_bbox(node):
    try:
        component = node.get_component_iface()
        if component:
            rect = component.get_extents(atspi_engine.Atspi.CoordType.SCREEN)
            return {"x": rect.x, "y": rect.y, "width": rect.width, "height": rect.height}
    except Exception:
        pass
    return None


def _node_text_value(node, role):
    try:
        text_iface = node.get_text_iface()
        if text_iface:
            length = min(text_iface.get_character_count(), 500)
            if length > 0:
                return text_iface.get_text(0, length)
    except Exception:
        pass
    try:
        value_iface = node.get_value_iface()
        if value_iface:
            return str(value_iface.get_current_value())
    except Exception:
        pass
    return None


def _walk(node, app_name, parent_path="", index=0, depth=0, max_depth=None, out=None):
    if out is None:
        out = []
    if max_depth is not None and depth > max_depth:
        return out
    try:
        info = atspi_engine._node_info(node, depth) or {}
        path = _node_path(parent_path, index)
        info.update({
            "id": f"node:{path}",
            "path": path,
            "app": app_name,
            "bbox": _node_bbox(node),
            "actions": _node_actions(node),
        })
        text_value = _node_text_value(node, info.get('role') or '')
        if text_value and text_value != info.get('name'):
            info['text'] = text_value
        out.append(info)
        count = node.get_child_count()
        for i in range(count):
            child = node.get_child_at_index(i)
            if child:
                _walk(child, app_name, path, i, depth + 1, max_depth, out)
    except Exception:
        pass
    return out


def build_observation(app_name=None, max_depth=6, screenshot_path=None):
    desktop = atspi_engine.get_desktop()
    nodes = []
    apps = []
    warnings = []
    effective_depth = None if max_depth == 0 else max_depth
    count = desktop.get_child_count()
    for i in range(count):
        app = desktop.get_child_at_index(i)
        if not app:
            continue
        name = app.get_name() or "(unnamed)"
        if app_name and app_name.lower() not in name.lower():
            continue
        try:
            child_count = app.get_child_count()
        except Exception:
            child_count = 0
        apps.append({"name": name, "children": child_count})
        nodes.extend(_walk(app, name, "", i, 0, effective_depth))

    if not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
        warnings.append("D-Bus session bus is not set; AT-SPI may still work via registryd")

    zero_bbox = sum(1 for n in nodes if n.get('bbox') and (n['bbox']['width'] <= 0 or n['bbox']['height'] <= 0))
    if zero_bbox:
        warnings.append(f"{zero_bbox} node(s) have zero-size bounding boxes")

    obs = {
        "schema": "desktop.observation.v1",
        "timestamp": time.time(),
        "display": os.environ.get('DISPLAY', ':99'),
        "screen": _screen_size(),
        "active_window": _active_window(),
        "screenshot": _screenshot(screenshot_path),
        "apps": apps,
        "nodes": nodes,
        "warnings": warnings,
    }
    return obs


def print_observation(app_name=None, max_depth=6, screenshot_path=None):
    print(json.dumps(build_observation(app_name, max_depth, screenshot_path), indent=2, ensure_ascii=False))


def write_observation(path, app_name=None, max_depth=6, screenshot_path=None):
    obs = build_observation(app_name, max_depth, screenshot_path)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obs, f, indent=2, ensure_ascii=False)
        f.write('\n')
    return obs
