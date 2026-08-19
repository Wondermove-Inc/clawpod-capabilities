"""AT-SPI accessibility engine for UI tree traversal and interaction."""

import os
import sys
import subprocess
import time
import difflib

os.environ.setdefault('DISPLAY', ':99')

try:
    import gi
    gi.require_version('Atspi', '2.0')
    from gi.repository import Atspi
    HAS_ATSPI = True
except (ImportError, ValueError):
    HAS_ATSPI = False

from .exit_codes import EXIT_NOT_FOUND, EXIT_ATSPI_FAIL
from . import human_input

# Sensitive roles whose values should be masked
_SENSITIVE_ROLES = {'password text', 'password'}


def _check_atspi():
    if not HAS_ATSPI:
        print("ERROR: AT-SPI not available. Install gir1.2-atspi-2.0 and at-spi2-core.", file=sys.stderr)
        sys.exit(EXIT_ATSPI_FAIL)


def _mask_sensitive(role, value):
    """Mask value if element role is password-related."""
    if role.lower() in _SENSITIVE_ROLES and value:
        return '****'
    return value


def _node_info(node, depth=0):
    """Extract accessible info from an AT-SPI node."""
    try:
        role = node.get_role_name()
        name = node.get_name() or ""
        name = _mask_sensitive(role, name)
        state_set = node.get_state_set()
        states = []
        for s in [Atspi.StateType.FOCUSED, Atspi.StateType.SELECTED,
                   Atspi.StateType.CHECKED, Atspi.StateType.EXPANDED,
                   Atspi.StateType.VISIBLE, Atspi.StateType.SENSITIVE]:
            if state_set.contains(s):
                states.append(Atspi.StateType.get_name(s))
        child_count = 0
        try:
            child_count = node.get_child_count()
        except Exception:
            pass
        return {
            "role": role,
            "name": name,
            "states": states,
            "depth": depth,
            "children": child_count,
        }
    except Exception:
        return None


def _walk_tree(node, depth=0, max_depth=None, results=None):
    """Recursively walk the AT-SPI tree."""
    if results is None:
        results = []
    if max_depth is not None and depth > max_depth:
        return results

    info = _node_info(node, depth)
    if info:
        if depth <= 1 or 'visible' in info.get('states', []) or info['role'] in ('application', 'frame', 'dialog'):
            results.append(info)

    try:
        count = node.get_child_count()
        for i in range(count):
            child = node.get_child_at_index(i)
            if child:
                _walk_tree(child, depth + 1, max_depth, results)
    except Exception:
        pass

    return results


def _walk_tree_nodes(node, depth=0, max_depth=None):
    """Walk tree returning actual AT-SPI nodes."""
    results = [node]
    if max_depth is not None and depth >= max_depth:
        return results
    try:
        count = node.get_child_count()
        for i in range(count):
            child = node.get_child_at_index(i)
            if child:
                results.extend(_walk_tree_nodes(child, depth + 1, max_depth))
    except Exception:
        pass
    return results


def _collect_all_names(app_name=None):
    """Collect all element names for fuzzy suggestion."""
    desktop = get_desktop()
    names = []
    count = desktop.get_child_count()
    for i in range(count):
        app = desktop.get_child_at_index(i)
        if not app:
            continue
        aname = app.get_name() or ""
        if app_name and app_name.lower() not in aname.lower():
            continue
        for node in _walk_tree_nodes(app, max_depth=10):
            try:
                n = node.get_name()
                if n:
                    names.append(n)
            except Exception:
                pass
    return names


def _suggest_similar(query, app_name=None, n=5):
    """Suggest similar element names using fuzzy matching."""
    all_names = _collect_all_names(app_name)
    if not all_names:
        return []
    matches = difflib.get_close_matches(query, all_names, n=n, cutoff=0.4)
    return matches


def get_desktop():
    """Get the AT-SPI desktop object."""
    _check_atspi()
    return Atspi.get_desktop(0)


def tree(app_name=None, max_depth=2, as_json=False):
    """Print the UI accessibility tree.
    Default depth=2 for summary. Use --depth 0 for unlimited.
    Without --app: per-app summary (name + windows + child count).
    """
    desktop = get_desktop()
    count = desktop.get_child_count()
    effective_depth = None if max_depth == 0 else max_depth

    if as_json:
        import json

    # Summary mode (default depth 2, with optional --app filter)
    if max_depth == 2:
        entries = []
        for i in range(count):
            app = desktop.get_child_at_index(i)
            if not app:
                continue
            name = app.get_name() or "(unnamed)"
            if app_name and app_name.lower() not in name.lower():
                continue
            try:
                child_count = app.get_child_count()
                windows = []
                for j in range(child_count):
                    win = app.get_child_at_index(j)
                    if win:
                        wname = win.get_name() or ""
                        wrole = win.get_role_name()
                        wchildren = 0
                        try:
                            wchildren = win.get_child_count()
                        except Exception:
                            pass
                        windows.append({"name": wname, "role": wrole, "children": wchildren})
                entry = {"app": name, "windows": windows}
                entries.append(entry)
                if not as_json:
                    print(f"[application] \"{name}\"")
                    for w in windows:
                        wname_str = f' "{w["name"]}"' if w["name"] else ""
                        print(f"  [{w['role']}]{wname_str} ({w['children']} children)")
            except Exception:
                if not as_json:
                    print(f"[application] \"{name}\"")
        if as_json:
            print(json.dumps(entries, indent=2, ensure_ascii=False))
        return

    for i in range(count):
        app = desktop.get_child_at_index(i)
        if not app:
            continue
        name = app.get_name() or ""
        if app_name and app_name.lower() not in name.lower():
            continue

        results = _walk_tree(app, depth=0, max_depth=effective_depth)
        if as_json:
            import json
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            for node in results:
                indent = "  " * node["depth"]
                states_str = ",".join(node["states"]) if node["states"] else ""
                name_str = f' "{node["name"]}"' if node["name"] else ""
                state_part = f" [{states_str}]" if states_str else ""
                print(f"{indent}[{node['role']}]{name_str}{state_part}")


def find(query, role_filter=None, app_name=None, as_json=False):
    """Find UI elements by name or role. Suggests similar if not found."""
    desktop = get_desktop()
    count = desktop.get_child_count()
    matches = []

    for i in range(count):
        app = desktop.get_child_at_index(i)
        if not app:
            continue
        name = app.get_name() or ""
        if app_name and app_name.lower() not in name.lower():
            continue

        results = _walk_tree_nodes(app, max_depth=15)
        for node in results:
            try:
                node_role = node.get_role_name()
                if role_filter and role_filter.lower() != node_role.lower():
                    continue
                if query.lower() in _node_search_text(node).lower():
                    info = _node_info(node) or {"role": node_role, "name": node.get_name() or "", "states": []}
                    matches.append(info)
            except Exception:
                continue

    if not matches:
        suggestions = _suggest_similar(query, app_name)
        msg = f"No elements found matching '{query}'"
        if suggestions:
            msg += f". Did you mean: {', '.join(suggestions)}"
        print(msg)
        sys.exit(EXIT_NOT_FOUND)

    if as_json:
        import json
        print(json.dumps(matches[:20], indent=2, ensure_ascii=False))
    else:
        for m in matches[:20]:
            states_str = ",".join(m["states"]) if m["states"] else ""
            state_part = f" [{states_str}]" if states_str else ""
            print(f"[{m['role']}] \"{m['name']}\"{state_part}")


def _node_search_text(node):
    parts = []
    try:
        n = node.get_name()
        if n:
            parts.append(n)
    except Exception:
        pass
    try:
        text_iface = node.get_text_iface()
        if text_iface:
            length = min(Atspi.Text.get_character_count(text_iface), 500)
            if length > 0:
                parts.append(Atspi.Text.get_text(text_iface, 0, length))
    except Exception:
        pass
    try:
        value_iface = node.get_value_iface()
        if value_iface:
            parts.append(str(value_iface.get_current_value()))
    except Exception:
        pass
    return ' '.join(p for p in parts if p)


def _find_node(name, role_filter=None, nth=1, app_name=None):
    """Find and return an AT-SPI node by name/text/value. Returns (node, total_matches)."""
    desktop = get_desktop()
    count = desktop.get_child_count()
    match_count = 0
    total = 0

    for i in range(count):
        app = desktop.get_child_at_index(i)
        if not app:
            continue
        aname = app.get_name() or ""
        if app_name and app_name.lower() not in aname.lower():
            continue

        nodes = _walk_tree_nodes(app, max_depth=15)
        for node in nodes:
            try:
                node_name = _node_search_text(node)
                node_role = node.get_role_name()
                if role_filter and role_filter.lower() != node_role.lower():
                    continue
                if name.lower() in node_name.lower():
                    total += 1
                    match_count += 1
                    if match_count == nth:
                        # Count remaining
                        for remaining in nodes[nodes.index(node)+1:]:
                            try:
                                rn = _node_search_text(remaining)
                                rr = remaining.get_role_name()
                                if role_filter and role_filter.lower() != rr.lower():
                                    continue
                                if name.lower() in rn.lower():
                                    total += 1
                            except Exception:
                                pass
                        return node, total
            except Exception:
                continue
    return None, total


def _not_found_exit(name, app_name=None):
    """Print not-found error with suggestions and exit."""
    suggestions = _suggest_similar(name, app_name)
    msg = f"ERROR: Element '{name}' not found"
    if suggestions:
        msg += f". Did you mean: {', '.join(suggestions)}"
    print(msg, file=sys.stderr)
    sys.exit(EXIT_NOT_FOUND)


def _node_click_metadata(node):
    """Return safe metadata for the node selected by a GUI action."""
    info = _node_info(node) or {}
    try:
        component = node.get_component_iface()
        if component:
            rect = component.get_extents(Atspi.CoordType.SCREEN)
            info["bbox"] = {"x": rect.x, "y": rect.y, "width": rect.width, "height": rect.height}
    except Exception:
        info["bbox"] = None
    try:
        action = node.get_action_iface()
        actions = []
        if action:
            for i in range(action.get_n_actions()):
                actions.append(action.get_action_name(i))
        info["actions"] = actions
    except Exception:
        info["actions"] = []
    return info


def _coordinate_allowed(allow_coordinate=False):
    return allow_coordinate or os.environ.get('DESKTOP_ALLOW_COORDINATE_CLICK') == '1'


def click(name, nth=1, app_name=None, role_filter=None, allow_coordinate=False):
    """Click an element by name."""
    node, total = _find_node(name, nth=nth, app_name=app_name, role_filter=role_filter)
    if not node:
        _not_found_exit(name, app_name)

    if total > 1 and nth == 1:
        print(f"WARNING: {total} matches for '{name}', clicking first. Use --nth to specify.", file=sys.stderr)

    # Try AT-SPI action first
    try:
        action = node.get_action_iface()
        if action:
            n_actions = action.get_n_actions()
            for j in range(n_actions):
                if action.get_action_name(j) in ('click', 'activate', 'press'):
                    human_input.pause('before')
                    action.do_action(j)
                    human_input.pause('after')
                    meta = _node_click_metadata(node)
                    print(f"Clicked '{name}' via AT-SPI action role={meta.get('role')} name={meta.get('name')!r}")
                    return
    except Exception:
        pass

    # Fallback: coordinate click via xdotool
    try:
        component = node.get_component_iface()
        if component:
            rect = component.get_extents(Atspi.CoordType.SCREEN)
            if rect.width <= 0 or rect.height <= 0:
                print(f"ERROR: Element '{name}' has invalid bbox {rect.width}x{rect.height}; refusing coordinate fallback", file=sys.stderr)
                sys.exit(EXIT_NOT_FOUND)
            if not _coordinate_allowed(allow_coordinate):
                print(
                    f"ERROR: Element '{name}' requires coordinate fallback at "
                    f"({rect.x + rect.width // 2}, {rect.y + rect.height // 2}). "
                    "Re-run with --allow-coordinate after verifying the target.",
                    file=sys.stderr,
                )
                sys.exit(EXIT_NOT_FOUND)
            x = rect.x + rect.width // 2
            y = rect.y + rect.height // 2
            human_input.click_at(x, y, button=1)
            meta = _node_click_metadata(node)
            print(f"Clicked '{name}' at ({x}, {y}) role={meta.get('role')} name={meta.get('name')!r}")
            return
    except Exception as e:
        print(f"ERROR: Could not click '{name}': {e}", file=sys.stderr)
        sys.exit(EXIT_NOT_FOUND)


def dblclick(name, nth=1, app_name=None, role_filter=None, allow_coordinate=False):
    """Double-click an element."""
    node, total = _find_node(name, nth=nth, app_name=app_name, role_filter=role_filter)
    if not node:
        _not_found_exit(name, app_name)
    if total > 1 and nth == 1:
        print(f"WARNING: {total} matches for '{name}', clicking first.", file=sys.stderr)
    try:
        component = node.get_component_iface()
        if component:
            rect = component.get_extents(Atspi.CoordType.SCREEN)
            if rect.width <= 0 or rect.height <= 0:
                print(f"ERROR: Element '{name}' has invalid bbox {rect.width}x{rect.height}; refusing coordinate fallback", file=sys.stderr)
                sys.exit(EXIT_NOT_FOUND)
            if not _coordinate_allowed(allow_coordinate):
                print(f"ERROR: Element '{name}' requires coordinate fallback. Re-run with --allow-coordinate after verifying the target.", file=sys.stderr)
                sys.exit(EXIT_NOT_FOUND)
            x = rect.x + rect.width // 2
            y = rect.y + rect.height // 2
            human_input.click_at(x, y, button=1, repeat=2, delay_ms=140)
            print(f"Double-clicked '{name}' at ({x}, {y})")
    except Exception as e:
        print(f"ERROR: Could not double-click '{name}': {e}", file=sys.stderr)
        sys.exit(EXIT_NOT_FOUND)


def rclick(name, nth=1, app_name=None, role_filter=None, allow_coordinate=False):
    """Right-click an element."""
    node, total = _find_node(name, nth=nth, app_name=app_name, role_filter=role_filter)
    if not node:
        _not_found_exit(name, app_name)
    if total > 1 and nth == 1:
        print(f"WARNING: {total} matches for '{name}', clicking first.", file=sys.stderr)
    try:
        component = node.get_component_iface()
        if component:
            rect = component.get_extents(Atspi.CoordType.SCREEN)
            if rect.width <= 0 or rect.height <= 0:
                print(f"ERROR: Element '{name}' has invalid bbox {rect.width}x{rect.height}; refusing coordinate fallback", file=sys.stderr)
                sys.exit(EXIT_NOT_FOUND)
            if not _coordinate_allowed(allow_coordinate):
                print(f"ERROR: Element '{name}' requires coordinate fallback. Re-run with --allow-coordinate after verifying the target.", file=sys.stderr)
                sys.exit(EXIT_NOT_FOUND)
            x = rect.x + rect.width // 2
            y = rect.y + rect.height // 2
            human_input.click_at(x, y, button=3)
            print(f"Right-clicked '{name}' at ({x}, {y})")
    except Exception as e:
        print(f"ERROR: Could not right-click '{name}': {e}", file=sys.stderr)
        sys.exit(EXIT_NOT_FOUND)


def select_menu(path):
    """Navigate a menu path like 'File > Save As'."""
    parts = [p.strip() for p in path.split('>')]
    for i, part in enumerate(parts):
        time.sleep(0.3 if i > 0 else 0)
        node, _ = _find_node(part, role_filter='menu item' if i > 0 else None)
        if not node:
            node, _ = _find_node(part)
        if not node:
            _not_found_exit(part)
        click(part)
    print(f"Selected menu: {path}")


def focus_window(name):
    """Focus a window by name. Uses exact > prefix > substring priority."""
    try:
        result = subprocess.run(
            ['xdotool', 'search', '--name', name],
            capture_output=True, text=True, timeout=5,
            env={**os.environ, 'DISPLAY': ':99'}
        )
        wids = [w for w in result.stdout.strip().split('\n') if w]
        if wids:
            # Rank matches: exact > prefix > substring
            best_wid = wids[0]
            best_rank = 2  # substring
            for wid in wids:
                try:
                    title_r = subprocess.run(
                        ['xdotool', 'getwindowname', wid],
                        capture_output=True, text=True, timeout=3,
                        env={**os.environ, 'DISPLAY': ':99'}
                    )
                    title = title_r.stdout.strip()
                    if title.lower() == name.lower():
                        best_wid = wid
                        best_rank = 0
                        break
                    elif title.lower().startswith(name.lower()) and best_rank > 1:
                        best_wid = wid
                        best_rank = 1
                except Exception:
                    continue

            subprocess.run(['xdotool', 'windowactivate', best_wid],
                          env={**os.environ, 'DISPLAY': ':99'}, check=True, timeout=5)
            title_result = subprocess.run(
                ['xdotool', 'getactivewindow', 'getwindowname'],
                capture_output=True, text=True, timeout=3,
                env={**os.environ, 'DISPLAY': ':99'}
            )
            title = title_result.stdout.strip() if title_result.returncode == 0 else name
            print(f"Focused: {title}")
            return
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    _not_found_exit(name)


def read_element_value(name, app_name=None, prefer_roles=None):
    """Return text content/value of an element, or None."""
    node = None
    if prefer_roles:
        for role in prefer_roles:
            node, _ = _find_node(name, app_name=app_name, role_filter=role)
            if node:
                break
    if not node:
        node, _ = _find_node(name, app_name=app_name)
    if not node:
        _not_found_exit(name, app_name)
    role = node.get_role_name()
    try:
        text_iface = node.get_text_iface()
        if text_iface:
            length = Atspi.Text.get_character_count(text_iface)
            return _mask_sensitive(role, Atspi.Text.get_text(text_iface, 0, length))
    except Exception:
        pass
    try:
        value_iface = node.get_value_iface()
        if value_iface:
            return _mask_sensitive(role, str(value_iface.get_current_value()))
    except Exception:
        pass
    name_text = node.get_name()
    if name_text:
        return _mask_sensitive(role, name_text)
    return None


def read_element(name, app_name=None):
    """Read text content of an element."""
    value = read_element_value(name, app_name=app_name)
    if value is not None:
        print(value)
    else:
        print(f"(no readable text for '{name}')")


def read_table(name, app_name=None, as_json=False):
    """Read table data from an accessible table element."""
    node, _ = _find_node(name, app_name=app_name)
    if not node:
        _not_found_exit(name, app_name)

    try:
        table_iface = node.get_table_iface()
        if not table_iface:
            print(f"ERROR: '{name}' is not a table element", file=sys.stderr)
            sys.exit(EXIT_NOT_FOUND)

        rows = table_iface.get_n_rows()
        cols = table_iface.get_n_columns()

        headers = []
        for c in range(cols):
            hdr = table_iface.get_column_header(c)
            headers.append(hdr.get_name() if hdr else f"Col{c}")

        if as_json:
            import json
            data = []
            for r in range(min(rows, 100)):
                row = {}
                for c in range(cols):
                    cell = table_iface.get_accessible_at(r, c)
                    row[headers[c]] = cell.get_name() if cell else ""
                data.append(row)
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print("\t".join(headers))
            print("-" * (len(headers) * 15))
            for r in range(min(rows, 100)):
                row_data = []
                for c in range(cols):
                    cell = table_iface.get_accessible_at(r, c)
                    row_data.append(cell.get_name() if cell else "")
                print("\t".join(row_data))

    except Exception as e:
        print(f"ERROR: Could not read table '{name}': {e}", file=sys.stderr)
        sys.exit(EXIT_NOT_FOUND)


def active_window():
    """Print info about the currently active window."""
    try:
        result = subprocess.run(
            ['xdotool', 'getactivewindow', 'getwindowname'],
            capture_output=True, text=True,
            env={**os.environ, 'DISPLAY': ':99'}
        )
        if result.returncode == 0:
            print(f"Active: {result.stdout.strip()}")
        else:
            print("No active window")
    except Exception:
        print("No active window")


def list_apps(as_json=False):
    """List running accessible applications."""
    desktop = get_desktop()
    count = desktop.get_child_count()
    entries = []

    for i in range(count):
        app = desktop.get_child_at_index(i)
        if not app:
            continue
        name = app.get_name() or "(unnamed)"
        try:
            child_count = app.get_child_count()
            windows = []
            for j in range(child_count):
                win = app.get_child_at_index(j)
                if win:
                    wname = win.get_name() or ""
                    wrole = win.get_role_name()
                    if wrole in ('frame', 'dialog', 'window'):
                        windows.append(wname or f"({wrole})")
            entry = {"app": name, "windows": windows}
            entries.append(entry)
            if not as_json:
                if windows:
                    print(f"  {name}: {', '.join(windows)}")
                else:
                    print(f"  {name}")
        except Exception:
            if not as_json:
                print(f"  {name}")

    if as_json:
        import json
        print(json.dumps(entries, indent=2, ensure_ascii=False))


def app_get(name):
    """Report one accessible application's details as JSON (app.get):
    windows (name + role) and window/child count. Case-insensitive substring
    match on the application name."""
    import json
    _check_atspi()
    if not name:
        print("ERROR: app-get requires an application name", file=sys.stderr)
        sys.exit(EXIT_NOT_FOUND)
    desktop = get_desktop()
    needle = name.strip().lower()
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if not app:
            continue
        app_name = app.get_name() or ""
        if needle not in app_name.lower():
            continue
        windows = []
        for j in range(app.get_child_count()):
            win = app.get_child_at_index(j)
            if not win:
                continue
            try:
                windows.append({'name': win.get_name() or '', 'role': win.get_role_name()})
            except Exception:
                continue
        print(json.dumps({'app': app_name, 'windowCount': len(windows), 'windows': windows},
                         ensure_ascii=False, separators=(',', ':')))
        return
    print(f"ERROR: no accessible application matching '{name}'", file=sys.stderr)
    sys.exit(EXIT_NOT_FOUND)


def selftest():
    """Run self-diagnostic: AT-SPI, xdotool, DISPLAY, D-Bus."""
    results = []

    # DISPLAY
    display = os.environ.get('DISPLAY', '')
    results.append(('DISPLAY', 'OK' if display else 'MISSING', display or 'not set'))

    # D-Bus
    dbus_addr = os.environ.get('DBUS_SESSION_BUS_ADDRESS', '')
    results.append(('D-Bus', 'OK' if dbus_addr else 'WARN (no session bus)', dbus_addr[:50] if dbus_addr else 'not set'))

    # AT-SPI
    if HAS_ATSPI:
        try:
            desktop = Atspi.get_desktop(0)
            app_count = desktop.get_child_count()
            results.append(('AT-SPI', 'OK', f'{app_count} applications'))
        except Exception as e:
            results.append(('AT-SPI', 'FAIL', str(e)))
    else:
        results.append(('AT-SPI', 'FAIL', 'gi.repository.Atspi not importable'))

    # xdotool
    try:
        r = subprocess.run(['xdotool', 'version'], capture_output=True, text=True)
        ver = r.stdout.strip().split('\n')[0] if r.returncode == 0 else 'unknown'
        results.append(('xdotool', 'OK', ver))
    except FileNotFoundError:
        results.append(('xdotool', 'FAIL', 'not installed'))

    # at-spi2-registryd
    try:
        r = subprocess.run(['pgrep', '-f', 'at-spi'], capture_output=True, text=True)
        pids = r.stdout.strip()
        results.append(('AT-SPI registryd', 'OK' if pids else 'WARN', pids or 'not running'))
    except Exception:
        results.append(('AT-SPI registryd', 'UNKNOWN', ''))

    for name, status, detail in results:
        print(f"  {name}: {status} ({detail})")

    # AT-SPI FAIL is critical; D-Bus WARN is fine (AT-SPI uses its own bus)
    atspi_ok = any(n == 'AT-SPI' and s == 'OK' for n, s, _ in results)
    atspi_fail = any(n == 'AT-SPI' and s == 'FAIL' for n, s, _ in results)
    if atspi_fail:
        sys.exit(EXIT_ATSPI_FAIL)
