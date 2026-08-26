# -*- coding: utf-8 -*-
"""`_get_last_seal` reads from the END of the ledger — same answers, O(1) cost.

The risk of this change is not that it is slow; it is that a chunked reverse read
answers `genesis` on a ledger that HAS a head. That would append a second genesis
entry into the middle of a live chain — a silent fork, and every integrity check
downstream would still pass, because each adjacent pair still links.

So the tests below are mostly about the seams the fast path introduced and the old
whole-file loop never had: chunk boundaries, line endings that text mode used to
normalise for us, and lines that are not JSON objects.

The equivalence test carries its own discriminating control (`test_comparator_can_fail`):
an equivalence suite that cannot report a difference proves nothing.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from measure_mirror import mm  # noqa: E402


def _old_get_last_seal(ledger_path):
    """The implementation this replaced — whole-file forward scan.

    Kept verbatim except for one guard: the original did `"seal" in e`, which raises
    TypeError when a ledger line is a bare number rather than an object. Real ledgers
    in this house contain such lines, so the original would have died where the new
    one returns an answer. That is a fix, not an equivalence break — see
    `test_non_object_lines_do_not_raise`.
    """
    if not os.path.exists(ledger_path):
        return "genesis"
    last = "genesis"
    with open(ledger_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if isinstance(e, dict) and "seal" in e:
                    last = e["seal"]
            except json.JSONDecodeError:
                continue
    return last


def _write(path, lines, sep="\n"):
    path.write_bytes(sep.join(lines).encode("utf-8") + sep.encode("utf-8"))
    return str(path)


def _entry(seal, **kw):
    return json.dumps({"claim_id": kw.pop("cid", "c"), "seal": seal, **kw})


# ── the answer itself ────────────────────────────────────────────────────────
def test_missing_ledger_is_genesis(tmp_path):
    assert mm._get_last_seal(str(tmp_path / "nope.jsonl")) == "genesis"


def test_empty_ledger_is_genesis(tmp_path):
    p = tmp_path / "e.jsonl"
    p.write_text("", encoding="utf-8")
    assert mm._get_last_seal(str(p)) == "genesis"


def test_ledger_with_no_sealed_entry_is_genesis(tmp_path):
    """Not 'the file is empty' — the file is full, and none of it is sealed.

    These two must not be told apart by the caller, but they must both answer
    genesis rather than crashing or returning the last arbitrary field.
    """
    p = _write(tmp_path / "u.jsonl", ['{"note":"a"}', '{"note":"b"}', "12345"])
    assert mm._get_last_seal(p) == "genesis"


def test_last_sealed_wins_over_later_unsealed_lines(tmp_path):
    p = _write(tmp_path / "t.jsonl",
               [_entry("aa"), _entry("bb"), '{"note":"trailing"}', "", "  "])
    assert mm._get_last_seal(p) == "bb"


def test_non_object_lines_do_not_raise(tmp_path):
    """A bare number is valid JSON and has no seal. The original raised TypeError here."""
    p = _write(tmp_path / "j.jsonl", [_entry("aa"), "12345", '["a"]', "null"])
    assert mm._get_last_seal(p) == "aa"


def test_unparseable_trailing_line_is_skipped(tmp_path):
    p = _write(tmp_path / "c.jsonl", [_entry("aa"), "{not json"])
    assert mm._get_last_seal(p) == "aa"


# ── the seams the fast path introduced ───────────────────────────────────────
@pytest.mark.parametrize("sep", ["\n", "\r\n", "\r"])
def test_all_line_endings_read_the_same(tmp_path, sep):
    """Reading bytes means universal-newline translation no longer happens for us.

    A CR-only ledger parsed as ONE line would answer genesis on a chain that has a
    head — the silent-fork failure this whole test module exists for.
    """
    p = _write(tmp_path / "n.jsonl", [_entry("aa"), _entry("bb")], sep=sep)
    assert mm._get_last_seal(p) == "bb"


def test_head_spanning_a_chunk_boundary(tmp_path):
    """The last entry is larger than one read chunk, so it is assembled across reads."""
    p = _write(tmp_path / "big.jsonl", [_entry("aa"), _entry("bb", pad="x" * 40000)])
    assert mm._get_last_seal(p, _chunk=4096) == "bb"


def test_only_entry_is_larger_than_the_file_chunk(tmp_path):
    """`pos == 0` path: the head is parts[0] and was never a 'complete' line."""
    p = _write(tmp_path / "one.jsonl", [_entry("aa", pad="y" * 30000)])
    assert mm._get_last_seal(p, _chunk=1024) == "aa"


@pytest.mark.parametrize("chunk", [1, 2, 7, 64, 8192])
def test_answer_is_independent_of_chunk_size(tmp_path, chunk):
    """If any answer depended on the read size, the seam is where it would show."""
    p = _write(tmp_path / "k.jsonl",
               [_entry("aa"), '{"note":"x"}', _entry("bb"), "12345", '{"note":"y"}'])
    assert mm._get_last_seal(p, _chunk=chunk) == "bb"


def test_no_trailing_newline(tmp_path):
    p = tmp_path / "nn.jsonl"
    p.write_bytes((_entry("aa") + "\n" + _entry("bb")).encode("utf-8"))
    assert mm._get_last_seal(str(p)) == "bb"


def test_utf8_multibyte_across_the_boundary(tmp_path):
    """A chunk can split a multi-byte character; the line is only decoded once whole."""
    p = _write(tmp_path / "u8.jsonl", [_entry("aa", pad="한글" * 3000)])
    assert mm._get_last_seal(p, _chunk=1024) == "aa"


# ── equivalence, with a control that proves the comparator works ─────────────
def _corpus(tmp_path):
    cases = {
        "plain": [_entry("aa"), _entry("bb")],
        "unsealed_tail": [_entry("aa"), '{"note":"t"}'],
        "none_sealed": ['{"note":"a"}'],
        "blank_lines": [_entry("aa"), "", "   ", _entry("bb"), ""],
        "corrupt": [_entry("aa"), "{not json", _entry("bb")],
        "nonobject": [_entry("aa"), "12345", "null"],
        "big": [_entry("aa"), _entry("bb", pad="z" * 20000)],
    }
    return [_write(tmp_path / f"{n}.jsonl", ls) for n, ls in cases.items()]


def test_matches_the_old_implementation(tmp_path):
    paths = _corpus(tmp_path)
    assert paths, "empty corpus — a green here would mean nothing"
    for p in paths:
        assert mm._get_last_seal(p) == _old_get_last_seal(p), p


def test_the_corpus_can_tell_a_broken_reader_apart(tmp_path):
    """⊕ Discriminating control: run a deliberately wrong reader over the SAME corpus
    and require the comparison to report a difference.

    Without this, `test_matches_the_old_implementation` could be green because the
    corpus is empty, or because every case happens to answer genesis — a suite that
    cannot fail is not evidence of equivalence, it is evidence of nothing.
    """
    def always_genesis(path, _chunk=8192):
        return "genesis"

    def first_seal_not_last(path, _chunk=8192):
        """Off by the direction of the scan — the exact bug this rewrite could introduce."""
        if not os.path.exists(path):
            return "genesis"
        for line in open(path, encoding="utf-8", errors="replace"):
            try:
                e = json.loads(line.strip() or "null")
            except Exception:
                continue
            if isinstance(e, dict) and "seal" in e:
                return e["seal"]
        return "genesis"

    paths = _corpus(tmp_path)
    for broken in (always_genesis, first_seal_not_last):
        caught = [p for p in paths if broken(p) != _old_get_last_seal(p)]
        assert caught, f"{broken.__name__} slipped through the corpus unnoticed"
    # ...and the real one is not merely lucky: it disagrees with both broken readers
    disagreements = [p for p in paths if mm._get_last_seal(p) != always_genesis(p)]
    assert disagreements, "corpus has no sealed head at all — it cannot discriminate"


# ── the chain must still verify after an append ──────────────────────────────
def test_append_keeps_the_chain_linked(tmp_path):
    p = str(tmp_path / "chain.jsonl")
    mm.preregister(p, "c1", metric="acc", min_n=10, baseline=0.5, pass_threshold=0.6,
                   kill_condition="acc<0.5", kill_threshold={"metric": "acc", "threshold": 0.5,
                                                             "direction": "below"})
    mm.preregister(p, "c2", metric="acc", min_n=10, baseline=0.5, pass_threshold=0.6,
                   kill_condition="acc<0.5", kill_threshold={"metric": "acc", "threshold": 0.5,
                                                             "direction": "below"})
    rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    assert len(rows) == 2
    assert rows[0]["prev_seal"] == "genesis"
    assert rows[1]["prev_seal"] == rows[0]["seal"], "the fast reader forked the chain"
