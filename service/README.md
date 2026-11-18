# Task Router inference service

A small HTTP service that answers the ten routing questions for one request. It is the API PugPort calls in production (currently serving Task Router v4). This page covers running, deploying and testing it; the endpoint-by-endpoint reference is [`API.md`](API.md).

**Contents:** [Run it locally](#run-it-locally) · [API](#api) · [Queue, limits and failure behaviour](#queue-limits-and-failure-behaviour) · [Privacy](#privacy) · [macOS LaunchAgent and tunnel](#macos-launchagent-and-tunnel) · [Tests](#tests)

- `POST /v1/judge` and `GET /healthz`.
- A raw ASGI app under Uvicorn: one process, one worker, bound to `127.0.0.1`. A Cloudflare Tunnel publishes it over HTTPS.
- Loads the checkpoint once at startup with the Laya framework (`laya.load(..., backend="eager", fast=False, compile=False)`), on Apple silicon (`mps`) in FP32 with mixed precision off. `cpu` is also accepted. There is no automatic device fallback.
- Median latency on the current Apple-silicon host, by request length: 37 ms short / 68 ms medium / 140 ms long.

Files:

| File | Purpose |
|---|---|
| [`API.md`](API.md) | API reference: request, response, status codes, example clients, design decisions. |
| [`openapi.yaml`](openapi.yaml) | OpenAPI 3.1 contract, derived from the code. |
| [`app.py`](app.py) | The ASGI service and its entry point. |
| [`contract.py`](contract.py) | The ten heads, input validation and token-budget packing. No torch or Laya import. |
| [`requirements.txt`](requirements.txt) | Direct dependency pins (not a full lock). |
| [`deploy/com.pugport.task-router.plist`](deploy/com.pugport.task-router.plist) | Example macOS LaunchAgent. |
| [`deploy/cloudflared-config.example.yml`](deploy/cloudflared-config.example.yml) | Example Cloudflare Tunnel ingress. |

## Run it locally

You need a complete local checkpoint directory (`model.safetensors`, `questions.json`, `rl_agent_config.json`, `encoder/`, `tokenizer/`). The Task Router weights are not published yet; any Laya checkpoint with the same ten questions loads the same way. The service never downloads a model: it sets `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` before importing anything.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r service/requirements.txt

export TASK_ROUTER_CHECKPOINT="$HOME/task-router/models/task-router-v4"   # required
export TASK_ROUTER_DEVICE=mps                                               # mps (default) or cpu
export TASK_ROUTER_PORT=8787                                                # optional, 1-65535
export TASK_ROUTER_MODEL_VERSION=task-router-v4                             # optional label returned to clients
.venv/bin/python -B service/app.py
```

The entry point fixes the host to loopback and the worker count to one, and turns off Uvicorn access logs and request diagnostics. Do not start extra workers: one process owns the model, the queue and the rate counters.

From another terminal, with synthetic input only:

```sh
curl --fail http://127.0.0.1:8787/healthz
curl --fail http://127.0.0.1:8787/v1/judge \
  -H 'Content-Type: application/json' \
  --data '{"state": {"message": "Translate hello to French.", "recent_context": "", "reference_text": "",
              "attachments": [], "candidate_executors": []}}'
```

## API

A summary for operators; [`API.md`](API.md) has the full reference with error codes and client examples.

`GET /healthz` returns `modelVersion`, `device` and `queueLength` (requests waiting). It does not run the model and does not count against the rate limit. It returns 503 until startup has finished and while shutting down.

`POST /v1/judge` accepts exactly `{"state": {...}}`, where the state has exactly five keys:

| Key | Type | Limit |
|---|---|---|
| `message` | string | 32,768 characters |
| `recent_context` | string | 32,768 characters |
| `reference_text` | string | 32,768 characters |
| `attachments` | list of `{kind, name, mime_type?}` | 32 items; metadata only, never file contents |
| `candidate_executors` | list of strings | 32 items |

The request body is capped at 64 KiB as streamed, independent of `Content-Length`. Duplicate keys at any level, unknown keys, `NaN`/`Infinity`, malformed JSON and invalid UTF-8 are rejected with 400.

Long input is packed to the model's token budget (the smallest budget across the ten questions, computed with `laya.common.state_room`). Packing keeps the start and the end of the message, gives most room to the current message and still leaves a share for context and metadata. What was shortened is reported in `raw.usage` (`input_compacted`, `original_state_tokens`, `packed_state_tokens`, `state_token_budget`, `compacted_fields`).

A successful response:

```json
{
  "modelVersion": "task-router-v4",
  "modelSha256": "<SHA-256 of the loaded model.safetensors>",
  "device": "mps",
  "latencyMs": 41.2,
  "raw": {
    "answers": {"task_type": {"choice": "translation", "...": "..."}, "...": "..."},
    "usage": {"...": "..."}
  },
  "region": "other"
}
```

`modelSha256` is computed from the file actually loaded, not hard-coded, so a client can pin both the version and the weights. `region` is `eu` for EU/EEA countries, Switzerland and the United Kingdom (from the `CF-IPCountry` header) and `other` otherwise; the PugPort client uses it to default optional sample sharing to off there.

## Queue, limits and failure behaviour

- One inference at a time, plus a queue of 8. A full queue answers 503 with `Retry-After`.
- A request that waited more than 2.5 s is dropped before inference (503 `queue_expired`).
- Per-IP rate limit: 30 judge requests per rolling minute per `CF-Connecting-IP` (429 with `Retry-After`). At most 4,096 clients are tracked; at capacity new clients get 503 rather than evicting live limits. Counters live in memory only.
- A client disconnect removes waiting work immediately. An inference that has started keeps the model slot until it finishes, so predictions never overlap.
- After 60 s without traffic the service runs one warm-up prediction on a fixed "Hello" state, through the same slot, without logging it or counting it against any limit.
- Errors return fixed codes (`invalid_request`, `body_too_large`, `rate_limited`, `queue_full`, `inference_failed`, ...) and never echo input, paths or tracebacks.

Cloudflare headers are trusted only because the listener is loopback-only behind the tunnel connector. Do not expose the port directly. Other processes on the same host can reach it; the service has no local-process authentication.

## Privacy

Request bodies, predictions and IP addresses are never written anywhere. Model stdout/stderr and Python logging are silenced while loading and predicting. Each log line contains only:

```json
{"timestamp": "2026-10-30T00:00:00+00:00", "status": 200, "latencyMs": 275.1, "packedTokenCount": 300, "country": "CA"}
```

Country values are restricted to two ASCII letters (`XX` otherwise); a disconnected request is logged as 499.

## macOS LaunchAgent and tunnel

`deploy/com.pugport.task-router.plist` assumes this layout: `~/task-router/repo` (this repository), `~/task-router/venv`, `~/task-router/models/<checkpoint>`, `~/task-router/logs`. Replace every `YOUR_USERNAME`, then:

```sh
plutil -lint deploy/com.pugport.task-router.plist
cp deploy/com.pugport.task-router.plist "$HOME/Library/LaunchAgents/"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.pugport.task-router.plist"
curl --fail http://127.0.0.1:8787/healthz
```

It is a per-user agent: it starts in the user's login session, and `KeepAlive` restarts it with a 30 s throttle. To switch checkpoints, put the new one in a new directory, change `TASK_ROUTER_CHECKPOINT`, bootstrap again, and compare `modelSha256` in a synthetic request with the expected hash. Keep the old directory for rollback.

`deploy/cloudflared-config.example.yml` shows the tunnel ingress; fill in your own tunnel ID and hostname.

## Tests

The service tests use the standard library only. They inject a fake agent and tokenizer and never import torch or Laya, load weights or open a network connection:

```sh
python -B -m unittest discover -s tests -p "test_service.py"
python -B -m unittest discover -s tests -p "test_contract.py"
python -B -m unittest discover -s tests -p "test_api.py"   # service vs openapi.yaml
```

The test seam is `Runtime(agent, questions, state_budget, model_sha256, device="cpu", inference_context=nullcontext, synchronize=lambda: None)` plus `create_app(runtime=..., clock=..., log_sink=...)`. These tests do not establish MPS numerical parity, latency, launchd behaviour or tunnel routing.
