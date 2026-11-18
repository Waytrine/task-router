# Attribution

Task Router is an independent project. It is fine-tuned with the Laya framework and starts from a Laya base checkpoint; it is not a fork of Laya and is not an official Laya or Convai Innovations product.

## Laya framework

- Project: [NandhaKishorM/laya](https://github.com/NandhaKishorM/laya) (Convai Innovations).
- License: Apache License 2.0, as stated by the `LICENSE` file and the `License: Apache-2.0` metadata shipped in the PyPI wheel `laya==0.4.15`. Wheel SHA-256 recorded on 2026-10-24: `f51301738464677cb650159684537eb267de47d33f3db4d8897f1502a9570e6e`.
- Pinned versions: training uses commit [`b9fe351ce81e2d974bca2bf219c1e4030c0a05ea`](https://github.com/NandhaKishorM/laya/tree/b9fe351ce81e2d974bca2bf219c1e4030c0a05ea); the inference service pins the PyPI release `laya==0.4.15`.
- Used for: the training loop (`laya.train.finetune`, soft cross-entropy), the checkpoint format and loader (`laya.load`), token budgeting (`laya.common.state_room`) and dataset format checks (`laya-evals validate`).
- This repository does not copy Laya source code.

## Base model

- [`convaiinnovations/laya-multilingual`](https://huggingface.co/convaiinnovations/laya-multilingual), revision [`1720e3e3357cfe1e281542e223f8273b0890ca34`](https://huggingface.co/convaiinnovations/laya-multilingual/tree/1720e3e3357cfe1e281542e223f8273b0890ca34). Task Router v1-v4 and the v5 variant trained from base start from this checkpoint.
- License: see the model card. Its terms are to be confirmed before Task Router weights are published.

## Encoder

- [`jhu-clsp/mmBERT-base`](https://huggingface.co/jhu-clsp/mmBERT-base) (ModernBERT architecture), the encoder inside the base checkpoint.
- License: see the model card; to be confirmed before weights are published.

## What this repository adds

- The ten-head routing schema (`data/questions.json`) and the synthetic bilingual dataset in `data/`.
- The training rounds, the evaluation scripts and reports, and the real-traffic evaluation summary.
- The inference service in `service/`.

## Not included

- No model weights (Task Router, base model or encoder). Task Router weights will be published separately.
- No real user requests or other private data.

When weights or modified upstream code are distributed later, include the applicable licenses, keep upstream copyright and NOTICE files, and mark the changes.
