# Dataset: pugport-routing-synthetic-v1

Synthetic, bilingual (Chinese and English) routing examples for the ten Task Router heads. Created 2026-10-26.

**Everything here is synthetic.** Rows were written by an AI assistant and reviewed by a second agent. No private logs, real user requests, real accounts or real attachments were used ([`provenance.json`](provenance.json): `"private_logs_used": false`). Attachments are invented metadata (kind and a made-up file name) with no content. Executor names such as Muse, Alex, Orion and Nova are fictional; URLs use `example.com`/`example.org`.

The real requests used for v5 are private and are **not** in this repository; see [`../eval/REAL_TRAFFIC.md`](../eval/REAL_TRAFFIC.md) for aggregate results.

**Contents:** [Files](#files) · [Row format](#row-format) · [How the splits were made](#how-the-splits-were-made) · [Known limits](#known-limits)

## Files

| File | Rows | Use |
|---|---:|---|
| `train.jsonl` | 240 | Round 1 (v1) training. 120 scenarios. |
| `validation.jsonl` | 60 | Comparing checkpoints and choosing what to add. 30 scenarios. |
| `calibration.jsonl` | 40 | Reserved for confidence calibration. 20 scenarios. |
| `test.jsonl` | 60 | Held-out test. 30 scenarios. |
| `all.jsonl` | 400 | The four splits above together. Do not train on it and then report test scores. |
| `train_v2.jsonl` | 400 | Round 2 training: `train.jsonl` + 160 new rows. |
| `train_v3.jsonl` | 520 | Round 3 training: `train_v2.jsonl` + 120 new rows. |
| `train_v4.jsonl` | 720 | Round 4 training: `train_v3.jsonl` + 200 new rows. |
| `calibration_v4.jsonl` | 60 | `calibration.jsonl` + 20 rows; used to fit v4's temperature. |
| `blind_test_v4.jsonl` | 20 | 10 bilingual scenarios run once on v4. Has template neighbours in `train_v4`, so treat it as a regression check. |
| `questions.json` | | The ten questions and their label definitions, exactly as the model receives them. |
| `manifest.json` | | Counts and SHA-256 of the v1 splits. |
| `rounds.json` | | Counts and SHA-256 of the later-round files. |
| `provenance.json` | | Origin, pinned Laya commit and base-model revision. |
| `LABEL_GUIDE.md` | | Short label guide. |
| `source/` | | Authoring source for the 200 v1 scenarios (`coding`, `general`, `media`), with the authoring contract and a Chinese rationale per scenario. `training/build_dataset.py` rebuilds the v1 splits from it byte for byte. |
| `policy_cases.jsonl` | 22 | Cases for the deterministic policy layer around the model (UI pins, unknown or ambiguous targets, missing search configuration, permissions). Not used for training; they document what the model is not allowed to decide. |

The `.jsonl` files keep their original CRLF line endings so the published hashes stay valid; `.gitattributes` stops Git from converting them.

## Row format

```json
{
  "id": "C001-en", "group_id": "C001", "family_id": "C001", "language": "en",
  "tags": ["inline-code", "explain", "no-execution"], "split": "train",
  "state": {"message": "...", "recent_context": "", "reference_text": "",
            "attachments": [], "candidate_executors": []},
  "questions": {"task_type": {"type": "choice", "instructions": "...",
                              "criteria": {"conversation": "...", "...": "..."}}, "...": {}},
  "expected": {"task_type": "coding", "difficulty": "simple", "web_search": "no", "...": "..."}
}
```

Only `state` and `questions` reach the model. `expected` holds one label per head.

## How the splits were made

- 200 scenarios, each written in Chinese and English (400 rows), grouped into 169 families. A family holds a translation pair plus any contrast pairs or near-duplicates that must not be separated.
- Splits are assigned per family by a seeded search that balances label distribution and keeps every label present in training. There is zero family, group or input overlap across splits (`manifest.json`).
- Later-round files add new families only; none of them shares a family, group or exact message with validation, calibration or test (`tests/test_dataset.py` checks this).

## Known limits

- The v2-v4 additions were written after earlier errors had been inspected, including test errors, and some are close rewrites of evaluation scenarios. Later test scores are therefore regression numbers ([`../eval/README.md`](../eval/README.md)).
- Small: 120 independent training scenarios in v1. Ten heads per row make 2,400 head-level training items, which are not independent of each other.
- Chinese and English only.
- Synthetic requests are shorter and cleaner than real work. A model trained only on this data scored 72.0% on real requests.
