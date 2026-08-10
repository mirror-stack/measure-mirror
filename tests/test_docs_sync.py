"""Docs ↔ code SSOT guard.

An anti-overclaim tool must not misstate its own probe count. The README's
"N probes" phrasing had drifted to 26 while the code (GROUPS registry) carries
27 — exactly the kind of self-contradiction the tool exists to catch. These
tests make the count derive from code so it cannot drift again.
"""
import re
from pathlib import Path

import measure_mirror as mm

REPO = Path(__file__).resolve().parents[1]


def _probe_count() -> int:
    return sum(len(v) for v in mm.GROUPS.values())


def test_readme_probe_count_matches_code():
    """Every 'N probes' claim in README.md must equal the GROUPS registry."""
    n = _probe_count()
    counts = [int(x) for x in re.findall(r"(\d+) probes", (REPO / "README.md").read_text())]
    assert counts, "no 'N probes' phrase found in README.md — did the wording change?"
    assert all(c == n for c in counts), f"README.md probe count(s) {counts} != code {n}"


def test_readme_ko_probe_count_matches_code():
    """KO total-count claim must equal code; subset-usage numbers (e.g. the
    full_audit '7종' example) are allowed only if strictly below the total."""
    n = _probe_count()
    counts = [int(x) for x in re.findall(r"(\d+)종 probe", (REPO / "README_KO.md").read_text())]
    assert counts, "no 'N종 probe' phrase found in README_KO.md"
    assert max(counts) == n, f"README_KO.md total probe count {max(counts)} != code {n}"
    assert all(c <= n for c in counts), f"a subset count exceeds the total: {counts}"


def test_readme_wilson_ci_example_matches_the_code():
    """The documented example value must be computed, not written by hand.

    It was written by hand once — README said (0.7527, 0.8042) where the code
    returns (0.7533, 0.8046). A number in the docs that the code does not
    produce is the exact defect class this tool exists to catch.
    """
    import re
    from measure_mirror import wilson_ci
    lo, hi = wilson_ci(780, 1000)
    expected = f"({lo:.4f}, {hi:.4f})"
    for name in ("README.md", "README_KO.md"):
        txt = (REPO / name).read_text(encoding="utf-8")
        shown = re.findall(r'wilson_ci\(780, 1000\)\s*#\s*(\([\d.,\s]+\))', txt)
        assert shown, f"{name}: wilson_ci example missing"
        for s in shown:
            assert s == expected, f"{name} shows {s}, code returns {expected}"


def _catalog_counts():
    """Entries per category, counted over GIT-TRACKED files.

    Tracked, not on-disk: what a README claim can contradict is what actually
    ships. An untracked draft in someone's working tree is not yet a published
    entry, so it must not trip the guard — but the moment it is `git add`ed the
    counts have to agree. `.DRAFT` files are work in progress either way.
    """
    import collections
    import subprocess
    out = subprocess.run(["git", "ls-files", "catalog/"], cwd=REPO,
                         capture_output=True, text=True)
    if out.returncode != 0:                     # not a git checkout — fall back
        files = [str(f.relative_to(REPO)) for f in (REPO / "catalog").rglob("*.md")]
    else:
        files = out.stdout.split()
    per = collections.Counter()
    for f in files:
        parts = f.split("/")
        if len(parts) < 3 or not f.endswith(".md"):
            continue
        if parts[-1].lower().startswith("readme") or ".DRAFT" in parts[-1]:
            continue
        per[parts[1]] += 1
    return dict(per)


def test_catalog_counts_match_the_tree():
    """README claims about the catalog must match the files on disk.

    Guards a pending-commit landmine: `catalog/README.md` was updated to 66
    while the top-level README still said 46, so committing the new entries
    would have published the contradiction. Nothing checked this — the probe
    count had a guard, the catalog count did not.
    """
    import re
    per = _catalog_counts()
    total = sum(per.values())

    header = re.search(r'v[\d.]+:\s*(\d+)\s*항목',
                       (REPO / "catalog" / "README.md").read_text(encoding="utf-8"))
    assert header, "catalog/README.md lost its 'vX.Y: N항목' header"
    assert int(header.group(1)) == total, (
        f"catalog/README.md header says {header.group(1)}, tree has {total}")

    for name in ("README.md", "README_KO.md"):
        txt = (REPO / name).read_text(encoding="utf-8")
        for claimed in {int(x) for x in re.findall(r'(\d+) real sealed cases', txt)}:
            assert claimed == total, (
                f"{name} claims {claimed} real sealed cases, tree has {total}")


def test_catalog_per_category_table_matches_the_tree():
    import re
    per = _catalog_counts()
    txt = (REPO / "catalog" / "README.md").read_text(encoding="utf-8")
    rows = re.findall(r'\[(\w[\w-]*)/\]\([^)]*\)[^|]*\|[^|]*\|\s*(\d+)\s*\|', txt)
    assert rows, "catalog/README.md category table not found"
    for name, claimed in rows:
        assert name in per, f"table lists unknown category {name!r}"
        assert int(claimed) == per[name], (
            f"catalog/README.md says {name}={claimed}, tree has {per[name]}")


# --- Korean docs: same guards as the English side. The KO count phrases use
# "N표본"/"vX.Y: N항목" (not "real sealed cases"), so the English guards above
# never covered them and they silently lagged to 67 while the tree was 72.
def test_readme_ko_catalog_count_matches_the_tree():
    """README_KO's catalog blurb ('봉인 사례 N표본') must equal the tree total."""
    import re
    total = sum(_catalog_counts().values())
    txt = (REPO / "README_KO.md").read_text(encoding="utf-8")
    claims = [int(x) for x in re.findall(r'사례\s*(\d+)\s*표본', txt)]
    assert claims, "README_KO.md: catalog count phrase '사례 N표본' not found — did the wording change?"
    for claimed in set(claims):
        assert claimed == total, (
            f"README_KO.md claims {claimed}표본, tree has {total}")


def test_catalog_ko_header_matches_the_tree():
    """catalog/README_KO.md 'vX.Y: N항목' header must equal the tree total."""
    import re
    total = sum(_catalog_counts().values())
    header = re.search(r'v[\d.]+:\s*(\d+)\s*항목',
                       (REPO / "catalog" / "README_KO.md").read_text(encoding="utf-8"))
    assert header, "catalog/README_KO.md lost its 'vX.Y: N항목' header"
    assert int(header.group(1)) == total, (
        f"catalog/README_KO.md header says {header.group(1)}, tree has {total}")


def test_catalog_ko_per_category_table_matches_the_tree():
    """catalog/README_KO.md per-category table must equal the tree, like the EN one."""
    import re
    per = _catalog_counts()
    txt = (REPO / "catalog" / "README_KO.md").read_text(encoding="utf-8")
    rows = re.findall(r'\[(\w[\w-]*)/\]\([^)]*\)[^|]*\|[^|]*\|\s*(\d+)\s*\|', txt)
    assert rows, "catalog/README_KO.md category table not found"
    for name, claimed in rows:
        assert name in per, f"table lists unknown category {name!r}"
        assert int(claimed) == per[name], (
            f"catalog/README_KO.md says {name}={claimed}, tree has {per[name]}")
