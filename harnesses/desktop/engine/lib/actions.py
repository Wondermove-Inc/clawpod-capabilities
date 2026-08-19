"""JSON action executor for desktop computer-use."""

from . import atspi_engine
from . import xdotool_engine
from . import app_manager
from . import power_commands
from . import safety
from . import human_input
from . import image_target


def execute_action(action, allow_coordinate=False, approve_sensitive=False, force=False, policy=None):
    safety.require_allowed_action(action, policy=policy, allow_coordinate=allow_coordinate, approve_sensitive=approve_sensitive, force=force)
    kind = action.get('kind')
    if kind == 'click_text':
        target = action.get('target') or action.get('text')
        if not target:
            raise ValueError('click_text requires target or text')
        return atspi_engine.click(target, nth=int(action.get('nth', 1)), app_name=action.get('app'), role_filter=action.get('role'), allow_coordinate=allow_coordinate)
    if kind == 'dblclick_text':
        target = action.get('target') or action.get('text')
        if not target:
            raise ValueError('dblclick_text requires target or text')
        return atspi_engine.dblclick(target, nth=int(action.get('nth', 1)), app_name=action.get('app'), role_filter=action.get('role'), allow_coordinate=allow_coordinate)
    if kind == 'rclick_text':
        target = action.get('target') or action.get('text')
        if not target:
            raise ValueError('rclick_text requires target or text')
        return atspi_engine.rclick(target, nth=int(action.get('nth', 1)), app_name=action.get('app'), role_filter=action.get('role'), allow_coordinate=allow_coordinate)
    if kind in ('click_xy', 'coordinate_click'):
        return _click_xy(action['x'], action['y'], allow_coordinate=allow_coordinate)
    if kind == 'click_image':
        return _click_image(action, allow_coordinate=allow_coordinate)
    if kind == 'handle_dialog':
        return _handle_dialog(action)
    if kind in ('type', 'type_text'):
        return xdotool_engine.type_text(
            action.get('text', ''),
            into_element=action.get('into'),
            allow_coordinate=allow_coordinate,
            clear=bool(action.get('clear', False)),
            verify=bool(action.get('verify', False)),
        )
    if kind == 'form_fill':
        return _form_fill(action, allow_coordinate=allow_coordinate)
    if kind == 'key':
        return xdotool_engine.press_key(action['combo'])
    if kind == 'scroll':
        return xdotool_engine.scroll(action.get('direction', 'down'), int(action.get('amount', 3)))
    if kind == 'open':
        return app_manager.open_app(action['app'], *action.get('args', []))
    if kind == 'launch_command':
        import subprocess
        argv = action.get('argv') or []
        if not isinstance(argv, list) or not argv:
            raise ValueError('launch_command requires argv list')
        subprocess.Popen([str(x) for x in argv], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        print(f"Launched command: {argv[0]}")
        return
    if kind == 'close':
        return app_manager.close_app(action.get('app'), force=force)
    if kind == 'focus':
        return atspi_engine.focus_window(action['target'])
    if kind == 'activate_window':
        import os, subprocess
        target = action['target']
        env = {**os.environ, 'DISPLAY': ':99'}
        result = subprocess.run(['xdotool', 'search', '--name', target], capture_output=True, text=True, env=env, timeout=5)
        if result.returncode != 0 or not result.stdout.strip():
            result = subprocess.run(['xdotool', 'search', '--class', target.lower()], capture_output=True, text=True, env=env, timeout=5)
        if result.returncode != 0 or not result.stdout.strip():
            result = subprocess.run(['xdotool', 'search', '--class', 'chromium'], capture_output=True, text=True, env=env, timeout=5)
        windows = [w for w in result.stdout.splitlines() if w.strip()]
        if not windows:
            raise RuntimeError(f'window not found: {target}')
        subprocess.run(['xdotool', 'windowactivate', windows[-1]], env=env, timeout=5, check=True)
        print(f'Activated window: {target}')
        return
    if kind == 'wait_text':
        return power_commands.wait_for(action['text'], timeout=int(action.get('timeout', 30)), gone=bool(action.get('gone', False)))
    if kind == 'wait_seconds':
        import time
        seconds = float(action.get('seconds', 1))
        if seconds < 0 or seconds > 60:
            raise ValueError('wait_seconds must be between 0 and 60')
        time.sleep(seconds)
        print(f'Waited {seconds:g}s')
        return
    raise ValueError(f'unknown action kind: {kind}')


def _click_xy(x, y, allow_coordinate=False):
    if not allow_coordinate:
        raise PermissionError('coordinate click requires --allow-coordinate')
    import os
    ix = int(x)
    iy = int(y)
    human_input.click_at(ix, iy, button=int(os.environ.get('DESKTOP_CLICK_BUTTON', '1')))
    print(f'Clicked coordinate ({ix}, {iy})')


def _click_image(action, allow_coordinate=False):
    """Locate a user-provided visual target and click its center.

    This is intentionally coordinate-gated because the final operation is a raw
    screen coordinate click. Matching refuses CAPTCHA/human-verification labels
    and is limited to deterministic local template matching.
    """
    if not allow_coordinate:
        raise PermissionError('click_image requires --allow-coordinate')
    result = image_target.locate_template(
        action['screenshot'],
        action['template'],
        threshold=float(action.get('threshold', 0.96)),
        stride=int(action.get('stride', 1)),
        label=action.get('label'),
    )
    if not result['found']:
        raise RuntimeError(f"image target not found: score={result['score']} threshold={result['threshold']}")
    _click_xy(result['center']['x'], result['center']['y'], allow_coordinate=True)
    print(f"Clicked image target center=({result['center']['x']}, {result['center']['y']}) score={result['score']:.6f}")


def _handle_dialog(action):
    """Handle a known, safe modal/dialog choice and verify by later steps.

    Supported choices are accept (Enter) and dismiss (Escape). Prompt text is
    only typed when explicitly supplied and must not look sensitive.
    """
    choice = (action.get('choice') or 'accept').lower()
    if choice not in ('accept', 'dismiss'):
        raise PermissionError('handle_dialog only supports safe choices: accept or dismiss')
    prompt_text = action.get('promptText') or action.get('text')
    modal_window = None
    try:
        import os, subprocess
        env = {**os.environ, 'DISPLAY': ':99'}
        for klass in ('xmessage', 'zenity'):
            res = subprocess.run(['xdotool', 'search', '--class', klass], capture_output=True, text=True, env=env, timeout=2)
            wins = [w for w in res.stdout.splitlines() if w.strip()]
            if wins:
                modal_window = wins[-1]
                subprocess.run(['xdotool', 'windowactivate', wins[-1]], env=env, timeout=2)
                break
    except Exception:
        pass
    if prompt_text:
        safety.require_allowed_action({'kind': 'type', 'text': prompt_text}, approve_sensitive=False)
        xdotool_engine.type_text(prompt_text)
    if choice == 'accept':
        # Native modal tools usually bind Enter to the safe affirmative button;
        # try this before ambiguous accessibility names like multiple "OK"s.
        xdotool_engine.press_key('enter')
        if modal_window:
            try:
                subprocess.run(['xdotool', 'key', '--window', modal_window, 'Return'], env=env, timeout=2)
            except Exception:
                pass
        import time
        time.sleep(0.2)
    # Prefer accessible dialog buttons when present; Chromium JS dialogs do not
    # always accept a raw Enter key unless the OK button already has focus.
    explicit_target = action.get('target') or action.get('button')
    candidates = [explicit_target] if explicit_target else (('OK', '확인', 'Yes') if choice == 'accept' else ('Cancel', '취소', 'No'))
    clicked = False
    for target in candidates:
        try:
            atspi_engine.click(target, role_filter='push button', allow_coordinate=False)
            clicked = True
            break
        except SystemExit:
            continue
        except Exception:
            continue
    if not clicked:
        combo = 'enter' if choice == 'accept' else 'escape'
        xdotool_engine.press_key(combo)
    elif choice == 'accept':
        xdotool_engine.press_key('enter')
    print(f'Handled dialog with safe choice: {choice}')


def _form_fill(action, allow_coordinate=False):
    """Fill multiple fields with focus/click/clear/type steps and optional submit."""
    fields = action.get('fields') or []
    if not isinstance(fields, list) or not fields:
        raise ValueError('form_fill requires fields: [{"into": "Field", "text": "..."}]')
    for field in fields:
        target = field.get('into') or field.get('target') or field.get('name')
        if not target:
            raise ValueError('form_fill field requires into/target/name')
        xdotool_engine.type_text(
            field.get('text', ''),
            into_element=target,
            allow_coordinate=allow_coordinate,
            clear=field.get('clear', True),
            verify=field.get('verify', False),
        )
    if action.get('submit'):
        return xdotool_engine.press_key(action.get('submitKey', 'enter'))
    print(f'Filled form fields: {len(fields)}')
