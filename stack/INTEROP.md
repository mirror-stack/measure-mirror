# 🔗 External-Witness Interop — v0.1

*[한국어 →](INTEROP_KO.md)*

> **One sentence:** interlock instead of compete — seal the **head** of an external
> audit ledger (a behaviour-governance stack's tamper-evident chain, another team's
> hash-chained log) into our action ledger, so the two chains testify to each
> other's timeline and immutability.

This extends **J3 (witness)** across a system boundary. `am witness` pins a peer
*am* ledger's head; this spec pins the head of a chain we do not operate and whose
schema we do not interpret. It is a document format, not code: no adapter, no
polling daemon, no schema mapping.

## Why head-only

- **O(1) and schema-blind.** We never parse their entries — validating what their
  log *means* is their verifier's job, not ours.
- **Same mechanism as J3.** Once head `H` is sealed at time `T` in our chain, any
  later disappearance of `H` from their chain (rollback, rewrite) is a formal
  disagreement between two committed ledgers — an event neither side can erase.
- **Honest scope.** We prove only *our claim that their head was `H` at `T`*.
  We prove nothing about whether their entries are true.

## Entry format (one `am` action entry)

```
action:  "external-witness"
agent:   <operator>
target:  "<system>:<instance>"          e.g. "agent-governance-toolkit:tenant-a"
payload:
  system:       identifying slug of the external system
  format:       their chain format label   e.g. "hash-chain-jsonl" | "merkle"
  instance:     tenant / deployment identifier
  head:         { hash, algo, seq, ts }    their chain head — full-width hash
  obtained_via: how the head was read — API route, export file + that file's
                sha256, or the exact query command
  prev_external_witness: seal of our previous external-witness entry for the
                same target (chains our *observations* of their chain)
```

Rules:

1. **`head.hash` is full-width.** A truncated hash is an unverified hash.
2. **No `obtained_via`, no entry.** A witness nobody can re-derive is a
   declaration without evidence — the exact disease measure-mirror #47 measures
   (a declared check that nothing can re-check).
3. **Periodic observations chain.** `prev_external_witness` turns repeated pins
   into a timeline, narrowing any rewrite window to the gap between two pins.

## Verification procedure (human or script)

- **V1 — our side:** `am verify` → Overall OK. (am ≤0.2.x exits 0 even on FAIL —
  parse the verdict line; fixed in action-mirror#3.)
- **V2 — entry exists:** `am history --action external-witness --target <t>`.
- **V3 — their side:** re-run `obtained_via`. Head `hash` still present at `seq`
  → that prefix of their chain is confirmed immutable since our pin. Absent →
  the two ledgers formally disagree: their rewrite or our misrecording — either
  way an event that can no longer be silently repaired.
- **V4 — reciprocity (optional):** if their audit log accepts free-form events,
  record our current head seal there. Mutual pins raise the cost of forgery
  from one chain to two chains at once.

## Worked example (illustrative, not an API contract)

A behaviour-governance toolkit keeps a SHA-256 hash-chained audit log and can
export it as a file. An operator pins it:
`obtained_via: "export 2026-08-14 audit.jsonl sha256=<full hash>; head = last line's chain hash"`.
The pin is now checkable by anyone holding that export — no access to our
infrastructure required.

## Non-goals

Live adapters and polling daemons (excluded until a demand signal — decision
sealed 2026-08-14), validation of external entry semantics, and any requirement
that the external system adopt our schema. Their governance layer enforces
behaviour; our measurement layer proves claims. The interlock is one sealed
head in each direction.
