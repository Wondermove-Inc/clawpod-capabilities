from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "figma-design"
EXAMPLES = SKILL / "examples"


def steps(path: Path) -> list[dict]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("//")]
    return [json.loads(line) for line in lines]


def refs(value) -> list[str]:
    if isinstance(value, dict):
        own = [value["$ref"]] if "$ref" in value else []
        return own + [name for item in value.values() for name in refs(item)]
    if isinstance(value, list):
        return [name for item in value for name in refs(item)]
    return []


class FigmaDesignSkillTests(unittest.TestCase):
    """FigCraft is not installed in CI, so these check structure; examples/verify.sh runs the scripts for real."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.scripts = sorted(EXAMPLES.glob("*/*.jsonl"))

    def test_every_script_is_well_formed_and_its_references_resolve(self) -> None:
        self.assertGreaterEqual(len(self.scripts), 50)
        for script in self.scripts:
            with self.subTest(script=script.name):
                named: set[str] = set()
                for step in steps(script):
                    self.assertLessEqual(set(step), {"command", "params", "as"})
                    self.assertRegex(step["command"], r"^[a-zA-Z]+(\.[a-zA-Z]+)+$")
                    for name in refs(step.get("params", {})):
                        self.assertIn(name, named, f"{name} is used before a step is named it")
                    if "as" in step:
                        self.assertNotIn(step["as"], named)
                        named.add(step["as"])

    def test_inputs_named_by_scripts_exist(self) -> None:
        stems = {script.relative_to(EXAMPLES).with_suffix("").as_posix() for script in self.scripts}
        for script in self.scripts:
            match = re.search(r"^// in: (.+)$", script.read_text(encoding="utf-8"), re.M)
            if match:
                target = match.group(1)
                self.assertTrue(target in stems or (EXAMPLES / target).is_file(), f"{script.name}: {target}")

    def test_index_lists_every_script_and_licences_ship(self) -> None:
        index = (EXAMPLES / "README.md").read_text(encoding="utf-8")
        for script in self.scripts:
            self.assertIn(script.relative_to(EXAMPLES).as_posix(), index)
        for required in ("files/LICENSE-MIT", "icons/LICENSE", "verify.sh", "check_layout.py", "enterprise/README.md", "enterprise/LICENSE-USWDS.md",
                         "enterprise/LICENSE-CFPB.txt", "enterprise/LICENSE-CARBON.txt", "enterprise/LICENSE-PAJAMAS.txt", "enterprise/LICENSE-IBM-PLEX-OFL.txt", "10-token-sets/LICENSE-APACHE-2.0.txt"):
            self.assertTrue((EXAMPLES / required).is_file(), required)
        self.assertTrue((SKILL / "THIRD_PARTY_NOTICES.md").is_file())

    def test_enterprise_files_are_the_ones_named_in_the_notices(self) -> None:
        notices = (SKILL / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        shipped = sorted(p.name for p in (EXAMPLES / "enterprise").iterdir() if p.suffix in {".fig", ".sketch", ".penpot"})
        self.assertEqual(shipped, ["carbon-v11-white.sketch", "cfpb-design-system.fig", "pajamas-design-tokens.fig", "uswds-design-kit.fig"])
        for name in shipped:
            self.assertIn(f"examples/enterprise/{name}", notices)

    def test_layout_check_finds_each_kind_of_defect(self) -> None:
        spec = importlib.util.spec_from_file_location("check_layout", EXAMPLES / "check_layout.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        def box(kind, name, parent, x, y, width, height, **more):
            return {"type": kind, "name": name, "parent": parent, "transform": [1, 0, 0, 1, x, y], "width": width, "height": height, **more}

        flow = {"layout": {"mode": "vertical"}, "clip": True}
        nodes = {
            1: {"type": "page", "name": "Page 1", "children": [2, 3, 7]},
            2: box("frame", "Screen", 1, 0, 0, 400, 800, **flow),
            3: box("frame", "Overlapping", 1, 300, 0, 400, 800),
            4: box("frame", "Unsized", 2, 0, 0, 100, 100),
            5: box("frame", "Footer", 2, 0, 780, 400, 48),
            6: box("text", "Clipped", 2, 0, 0, 200, 10, style={"font_size": 16, "line_height": {"unit": "percent", "value": 150}}),
            7: box("frame", "Clean", 1, 1000, 0, 400, 800, **flow),
            8: box("text", "Auto line height", 7, 0, 0, 200, 20, style={"font_size": 16, "line_height": {"unit": "auto"}}),
            9: box("frame", "Hidden", 7, 0, 0, 100, 100, visible=False),
            10: box("text", "Squashed", 7, 0, 100, 200, 8, style={"font_size": 20, "line_height": {"unit": "auto"}}),
            11: box("frame", "Free", 1, 2000, 0, 400, 400, children=[12, 13, 14]),
            12: box("text", "Title", 11, 20, 20, 200, 24),
            13: box("text", "Subtitle", 11, 20, 30, 200, 24),
            14: {**box("text", "Rotated", 11, 500, 300, 200, 24), "transform": [0, 1, -1, 0, 500, 300]},
            15: {**box("frame", "Flipped", 2, 424, 0, 24, 24), "transform": [-1, 0, 0, 1, 424, 0]},
            16: box("text", "Trimmed", 7, 0, 300, 200, 35, leading_trim="capHeight", style={"font_size": 48, "line_height": {"unit": "auto"}}),
            17: box("frame", "Internal Only Canvas", 1, 5000, 0, 0, 0, children=[18]),
            18: box("text", "Held", 17, 10, 10, 80, 20),
        }
        nodes[2]["children"] = [4, 5, 6, 15]
        nodes[1]["children"].append(11)
        found = "\n".join(module.scan(nodes))
        for expected in ("still 100 x 100", "cut off by its auto-layout parent 'Screen': Footer", "one line needs 24", "one line needs 20: Squashed", "text layers overlap in 'Free': 'Title' and 'Subtitle'",
                         "top-level frames overlap on page 'Page 1': 'Screen' and 'Overlapping'"):
            self.assertIn(expected, found)
        self.assertNotIn("'Clean'", found)
        self.assertNotIn("Rotated", found)
        self.assertNotIn("Flipped", found)
        self.assertNotIn("Trimmed", found)
        self.assertNotIn("Held", found)
        self.assertNotIn("Hidden", found)
        self.assertNotIn("Auto line height", found)

    def test_skill_does_not_pin_an_app_version(self) -> None:
        for doc in [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]:
            self.assertNotRegex(doc.read_text(encoding="utf-8"), r"FigCraft \d+\.\d+|figcraft-cli \d+\.\d+|\b0\.\d{2}\.\d\b", doc.name)


if __name__ == "__main__":
    unittest.main()
