# Releasing measure-mirror to PyPI

measure-mirror is **not on PyPI yet** (checked 2026-11-23: `pypi.org/project/measure-mirror`
returns 404, and so does TestPyPI). Until the first upload, install from git as the README says.

Uploads go through [`.github/workflows/publish.yml`](../.github/workflows/publish.yml). It only
runs when someone starts it by hand, and it uses PyPI Trusted Publishing, so no API token lives in
this repository.

## One-time setup (owner, ~10 minutes)

1. Sign in to <https://test.pypi.org> and <https://pypi.org> (separate accounts).
2. On each site, go to *Your projects → Publishing → Add a new pending publisher* and enter:
   - PyPI project name: `measure-mirror`
   - Owner: `mirror-stack`
   - Repository: `measure-mirror`
   - Workflow name: `publish.yml`
   - Environment: `testpypi` on test.pypi.org, `pypi` on pypi.org
3. In GitHub, *Settings → Environments*, create `testpypi` and `pypi`. Add yourself as a
   **required reviewer** on both, so every upload stops and waits for your approval.

A pending publisher does not reserve the name. Until the first upload succeeds, someone else
can still register `measure-mirror`.

## Each release

1. Bump the version in **both** `pyproject.toml` and `measure_mirror/__init__.py`, add a
   `CHANGELOG.md` entry, merge, and push a tag `vX.Y.Z` on that commit.
   The workflow refuses to build if the tag, `pyproject.toml` and `__version__` disagree.
2. *Actions → Publish to PyPI → Run workflow*, tag `vX.Y.Z`, target `testpypi`. Approve it.
3. Check it in a clean environment:
   ```bash
   python -m venv /tmp/mm && /tmp/mm/bin/pip install \
     -i https://test.pypi.org/simple/ measure-mirror==X.Y.Z
   /tmp/mm/bin/mm --help
   ```
4. Run the workflow again with target `pypi`. Approve it.
5. Only now change the install lines in `README.md` / `README_KO.md` / the tutorial to
   `pip install measure-mirror==X.Y.Z`. Do it after the upload, not before: a README that
   points at a package that is not there yet is a broken first step.

A version number can be uploaded to PyPI **once**. If a release is wrong, yank it and publish
the next patch version; the same number cannot be reused.

## What the PyPI page shows

The project page renders `README.md`. Relative links do not work there, so README links point
at `github.com/mirror-stack/measure-mirror/blob/main/...`. Keep new links absolute.
`authors` in `pyproject.toml` (name and email) is shown publicly on the PyPI page.
