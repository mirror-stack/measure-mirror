"""README.md is the PyPI long description; PyPI cannot resolve relative links.

Guard: every Markdown link and <img src> in README.md must be absolute (or an
in-page #anchor), so the project page on PyPI has no dead links.
"""
import re
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"


def _targets(text):
    yield from re.findall(r"\]\(([^)\s]+)\)", text)
    yield from re.findall(r'src="([^"]+)"', text)


def test_readme_links_are_absolute():
    bad = [t for t in _targets(README.read_text(encoding="utf-8"))
           if not t.startswith(("http://", "https://", "#", "mailto:"))]
    assert not bad, f"relative links break on PyPI: {bad}"
