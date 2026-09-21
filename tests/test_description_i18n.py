"""Localized description generation and validation, including legacy v1 entries."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync = load_module("i18n_sync", ROOT / "scripts/sync_registry.py")
validator = load_module("i18n_validator", ROOT / "scripts/validate.py")
KOREAN = "근거를 확인하고 관련 자료를 검색하는 테스트 능력입니다."


class DescriptionI18nTests(unittest.TestCase):
    def test_all_canonical_packages_have_english_and_korean_descriptions(self) -> None:
        registry = sync.generate_registry(ROOT)
        packages = list((ROOT / "skills").glob("*/capability.json"))
        packages += list((ROOT / "harnesses").glob("*/capability.json"))
        self.assertEqual(len(registry["capabilities"]), len(packages))
        for entry in registry["capabilities"]:
            with self.subTest(type=entry["type"], id=entry["id"]):
                metadata = json.loads((ROOT / entry["path"] / "capability.json").read_text())
                self.assertIn("descriptionI18n", metadata, "New packages must include a Korean translation")
                self.assertEqual(set(metadata["descriptionI18n"]), {"ko"})
                self.assertEqual(set(entry["descriptionI18n"]), {"en", "ko"})
                self.assertEqual(entry["descriptionI18n"]["en"], entry["description"])
                self.assertNotRegex(entry["description"], "[가-힣]", "The default description must be English")
                self.assertEqual(entry["descriptionI18n"]["ko"], metadata["descriptionI18n"]["ko"])
                self.assertRegex(entry["descriptionI18n"]["ko"], "[가-힣]", "The Korean translation must contain Korean")

    def setUp(self) -> None:
        self.metadata = {
            "schemaVersion": 1,
            "version": "1.0.0",
            "description": "Search and verify supporting evidence.",
            "descriptionI18n": {"ko": KOREAN},
            "compatibility": {"openclaw": ">=2026.4.0"},
            "safety": {"risk": "read-only", "approvalRequired": False},
        }

    def test_generation_uses_effective_english_source_and_preserves_digests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "skills/example"
            package.mkdir(parents=True)
            frontmatter = "Use to inspect evidence and its original sources."
            (package / "SKILL.md").write_text(
                f"---\nname: example\ndescription: {frontmatter}\n---\n", encoding="utf-8"
            )
            metadata_path = package / "capability.json"
            for source, english in (("package-metadata", self.metadata["description"]),
                                    ("skill-frontmatter", frontmatter)):
                with self.subTest(source=source):
                    self.metadata["descriptionSource"] = source
                    metadata_path.write_text(json.dumps(self.metadata), encoding="utf-8")
                    entry = sync.build_entry(root, "skill", package)
                    self.assertEqual(entry["description"], english)
                    self.assertEqual(entry["descriptionI18n"], {"en": english, "ko": KOREAN})
                    rendered = sync.render_registry({"capabilities": [entry]})
                    self.assertIn(KOREAN, rendered)
                    self.assertEqual(json.loads(rendered)["capabilities"][0], entry)
                    legacy = {k: v for k, v in self.metadata.items() if k != "descriptionI18n"}
                    metadata_path.write_text(json.dumps(legacy), encoding="utf-8")
                    old_entry = sync.build_entry(root, "skill", package)
                    self.assertNotIn("descriptionI18n", old_entry)
                    self.assertEqual(old_entry, {k: v for k, v in entry.items() if k != "descriptionI18n"})

    def test_invalid_authored_translations_are_rejected(self) -> None:
        invalid = [None, [], "한국어 설명", {}, {"en": "Manually duplicated English."},
                   {"ko": KOREAN, "en": "Manually duplicated English."},
                   {"ko": KOREAN, "ja": "Unsupported language."}]
        invalid += [{"ko": value} for value in (None, 12, True, [], {}, "", " " * 20, "짧음", "가" * 501,
                                                " " + KOREAN, KOREAN + "\n")]
        for translations in invalid:
            with self.subTest(translations=translations):
                self.metadata["descriptionI18n"] = translations
                with self.assertRaisesRegex(sync.SyncError, "descriptionI18n"):
                    sync.validate_package_metadata(Path("capability.json"), self.metadata)

    def test_translation_length_boundaries(self) -> None:
        for length in (10, 500):
            self.metadata["descriptionI18n"] = {"ko": "가" * length}
            sync.validate_package_metadata(Path("capability.json"), self.metadata)

    def test_validator_rejects_malformed_or_drifted_localizations(self) -> None:
        entry = json.loads((ROOT / "registry/index.json").read_text())["capabilities"][0]
        valid = {"en": entry["description"], "ko": KOREAN}
        invalid = [None, [], {}, {"en": entry["description"]}, {"ko": KOREAN},
                   {**valid, "en": "An English description that has drifted."},
                   {**valid, "ja": "Unsupported language."}]
        invalid += [{**valid, "ko": value} for value in (None, 7, "", " " * 20, "가" * 501, " " + KOREAN)]
        for translations in invalid:
            with self.subTest(translations=translations), contextlib.redirect_stderr(io.StringIO()) as error:
                candidate = {**entry, "descriptionI18n": translations}
                with self.assertRaises(SystemExit):
                    validator.validate_entry(candidate, 0, set())
                self.assertIn("descriptionI18n", error.getvalue())
        validator.validate_entry({**entry, "descriptionI18n": valid}, 0, set())
        legacy = {k: v for k, v in entry.items() if k != "descriptionI18n"}
        validator.validate_entry(legacy, 0, set())


if __name__ == "__main__":
    unittest.main()
