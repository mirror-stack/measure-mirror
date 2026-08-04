"""CHANGELOG ↔ pyproject sync guard.

The one sync target no test covered. `pyproject.toml` was bumped 0.28.1 → 0.29.0
with no CHANGELOG line, and every existing check passed — the same silent-hole
shape as `_SYMBOL_GROUP`, where a registry nothing asserted on could be skipped
without a single failure.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    m = re.search(r'^version\s*=\s*"([^"]+)"',
                  (REPO / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    assert m, "pyproject.toml has no version field"
    return m.group(1)


def _changelog_versions() -> list[str]:
    return re.findall(r'^##\s*\[?v?([0-9]+\.[0-9]+\.[0-9]+)\]?',
                      (REPO / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)


def test_current_version_has_a_changelog_entry():
    ver = _pyproject_version()
    entries = _changelog_versions()
    assert entries, "CHANGELOG.md has no parseable '## [x.y.z]' headings"
    assert ver in entries, (
        f"pyproject version {ver} has no CHANGELOG entry "
        f"(newest is {entries[0]}). A released version with no changelog line "
        f"is a claim with no record.")


def test_changelog_newest_entry_is_the_current_version():
    ver, entries = _pyproject_version(), _changelog_versions()
    assert entries[0] == ver, (
        f"CHANGELOG's newest entry is {entries[0]} but pyproject says {ver} — "
        f"entries must be in descending order with the current release on top.")


def test_version_matches_dunder_version():
    ver = _pyproject_version()
    m = re.search(r'^__version__\s*=\s*"([^"]+)"',
                  (REPO / "measure_mirror" / "__init__.py").read_text(encoding="utf-8"), re.M)
    assert m and m.group(1) == ver, (
        f"pyproject {ver} != __init__.__version__ {m.group(1) if m else 'missing'}")
