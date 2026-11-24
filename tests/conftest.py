"""Make test subprocesses speak UTF-8 regardless of the host console.

Tests read child output with encoding="utf-8". On a non-UTF-8 Windows console
(e.g. Korean cp949) a child would otherwise print in the console codepage, and the
reader thread failed on emoji bytes, handing the test `stdout=None` (40 failures in
measure-mirror, 7 in action-mirror, 2026-11-24). Tests that pin a specific console
encoding set PYTHONIOENCODING themselves and still override this default.
"""
import os

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
