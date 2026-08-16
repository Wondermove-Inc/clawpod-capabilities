#!/usr/bin/env python3
"""Install an owner-scoped command wrapper without network access."""
import argparse, os
from pathlib import Path

p = argparse.ArgumentParser(); p.add_argument("--bin-dir", required=True); a = p.parse_args()
source = Path(__file__).resolve().parents[1] / "openclaw_node_host.py"
target = Path(a.bin_dir).expanduser().resolve() / ("openclaw-node-host.cmd" if os.name == "nt" else "openclaw-node-host")
target.parent.mkdir(parents=True, exist_ok=True)
if os.name == "nt": content = f'@"{os.environ.get("PYTHON", "python")}" "{source}" %*\r\n'
else: content = f'#!/bin/sh\nexec "${{PYTHON:-python3}}" "{source}" "$@"\n'
temporary = target.with_name("." + target.name + ".tmp"); temporary.write_text(content, encoding="utf-8"); os.chmod(temporary, 0o755); os.replace(temporary, target)
print(target)
