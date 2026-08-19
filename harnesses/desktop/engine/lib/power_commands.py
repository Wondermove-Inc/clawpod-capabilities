"""Power commands: chain, wait, read, table."""

import shlex
import time
import sys

from .exit_codes import EXIT_TIMEOUT


def chain(commands, executor, continue_on_error=False):
    """Execute multiple desktop commands sequentially.
    Default: --fail-fast (stop on first error).
    --continue-on-error: skip failures."""
    for cmd_str in commands:
        cmd_str = cmd_str.strip()
        if not cmd_str:
            continue
        try:
            parts = shlex.split(cmd_str)
        except ValueError:
            parts = cmd_str.split()
        if not parts:
            continue
        try:
            executor(parts)
        except SystemExit as e:
            if e.code != 0 and not continue_on_error:
                print(f"Chain stopped at: {cmd_str}", file=sys.stderr)
                raise
            elif continue_on_error:
                print(f"WARNING: '{cmd_str}' failed, continuing...", file=sys.stderr)
        time.sleep(0.3)


def wait_for(element_name, timeout=30, gone=False):
    """Wait for an element to appear or disappear."""
    from .atspi_engine import _find_node

    start = time.time()
    while time.time() - start < timeout:
        node, _ = _find_node(element_name)
        if gone:
            if node is None:
                print(f"Element '{element_name}' disappeared after {time.time()-start:.1f}s")
                return
        else:
            if node is not None:
                print(f"Element '{element_name}' appeared after {time.time()-start:.1f}s")
                return
        time.sleep(0.5)

    action = "disappear" if gone else "appear"
    print(f"ERROR: Timeout waiting for '{element_name}' to {action} ({timeout}s)", file=sys.stderr)
    sys.exit(EXIT_TIMEOUT)
