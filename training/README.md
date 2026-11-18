# Training and evaluation scripts

The scripts that rebuild the dataset, score checkpoints and run one training round. Training and running a model need Laya; rebuilding the dataset, scoring predictions and comparing reports need only the Python standard library.

**Contents:** [Rebuild the dataset](#rebuild-the-dataset) · [Evaluate a checkpoint](#evaluate-a-checkpoint) · [Recorded training configuration](#recorded-training-configuration-v1-v4)

| File | What it does | Needs |
|---|---|---|
| [`build_dataset.py`](build_dataset.py) | Rebuilds the v1 splits from `data/source/*.json` into a new directory, with a manifest that matches `data/manifest.json` byte for byte. | Python 3.11+ standard library |
| [`evaluate.py`](evaluate.py) | `run` scores a local checkpoint on a data file; `compare` makes a before/after table from two reports on the same data bytes. | `run`: `laya`, GPU or CPU. `compare`: standard library |
| [`task_router_colab.ipynb`](task_router_colab.ipynb) | One full training round on a GPU runtime. Outputs cleared. | Colab GPU or any CUDA machine |

`evaluate.py run` loads the checkpoint, predicts every row, and writes `predictions.jsonl`, `report.json` (per-head accuracy, macro F1, per-label recall and precision, per-language accuracy, majority-class baseline, latency) and `mistakes.csv`. Scoring itself needs only the standard library.

The notebook verifies the data hashes, installs Laya at the pinned commit, downloads the pinned base model, scores the base model, fine-tunes, scores again and runs the final test.

## Rebuild the dataset

```sh
python training/build_dataset.py --out runs/rebuild
```

`--out` must be new or empty; the committed `data/` is never overwritten.

## Evaluate a checkpoint

```sh
python -m pip install -r requirements.txt     # Laya at the pinned commit b9fe351
python training/evaluate.py run data/test.jsonl --model-dir /path/to/checkpoint --out runs/test-eval \
  --train-data data/train_v4.jsonl --device cuda
python training/evaluate.py compare runs/base-test/report.json runs/test-eval/report.json --out runs/compare.md
```

The checkpoint must be a complete local directory (it contains `rl_agent_config.json`); the script never downloads one. The pinned public base model is `convaiinnovations/laya-multilingual` at revision `1720e3e3357cfe1e281542e223f8273b0890ca34`. Task Router weights are not published yet.

## Recorded training configuration (v1-v4)

| Setting | Value |
|---|---|
| Framework | Laya, commit `b9fe351ce81e2d974bca2bf219c1e4030c0a05ea` |
| Base checkpoint | `convaiinnovations/laya-multilingual` @ `1720e3e3357cfe1e281542e223f8273b0890ca34` |
| Loss | soft cross-entropy |
| Epochs | 4 |
| Batch | micro-batch 8 x gradient accumulation 2 |
| Learning rate | encoder 2.5e-5, heads 1e-4 |
| Weight decay / gradient clip | 0.01 / 1.0 |
| Encoder frozen | no |
| Precision | bf16 mixed precision |
| Laya internal calibration split | off (`calib_max=0`), so questions from one scenario never straddle training and calibration |
| Seed | 20261026 |

v4 additionally had a temperature fitted after training on `data/calibration_v4.jsonl` (T = 3.51; ECE 0.040 to 0.015, measured on that same 60-row split). The notebook does not include that step.

The notebook as published is a cleaned, English rewrite of the one used for round 1: the same cells and checks, with paths moved to environment variables, the repository cloned instead of a ZIP upload, a round selector for v1-v4, and the batch settings above (round 1's original draft started from micro-batch 1 x accumulation 16 before the recorded runs used 8 x 2).
