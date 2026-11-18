# Task Router API reference

Task Router answers ten routing questions about one request to an AI agent system: what kind of task it is, how hard it is, and which tools it needs. This page documents its HTTP API. The machine-readable contract is [`openapi.yaml`](openapi.yaml) (OpenAPI 3.1); it is derived from [`app.py`](app.py) and [`contract.py`](contract.py), and [`tests/test_api.py`](../tests/test_api.py) checks the two against each other. Examples use the placeholder base URL `https://router.example.com`. For running and deploying the service, see [`README.md`](README.md).

**Contents:** [Endpoints](#endpoints) · [`POST /v1/judge`](#post-v1judge) · [`GET /healthz`](#get-healthz) · [Errors](#errors) · [Client examples](#client-examples) · [Design decisions](#design-decisions)

## Endpoints

| Endpoint | Purpose | Runs the model | Rate limited |
|---|---|:---:|:---:|
| [`POST /v1/judge`](#post-v1judge) | Answer the ten routing questions for one request. | yes | yes |
| [`GET /healthz`](#get-healthz) | Readiness, model version, device and queue length. | no | no |

Requests and responses are JSON. Every error is `{"error": "<code>"}` with a fixed code ([Errors](#errors)); anything else returns `404 {"error": "not_found"}`.

## `POST /v1/judge`

### Request

```sh
curl --fail-with-body https://router.example.com/v1/judge \
  -H 'Content-Type: application/json' \
  --data '{
    "state": {
      "message": "Fix the failing date test in this repo and run the suite.",
      "recent_context": "",
      "reference_text": "",
      "attachments": [],
      "candidate_executors": ["Muse", "Nova"]
    }
  }'
```

The body is exactly `{"state": {...}}`, and the state has exactly these five keys:

| Key | Type | Limit |
|---|---|---|
| `message` | string | 32,768 characters |
| `recent_context` | string | 32,768 characters |
| `reference_text` | string | 32,768 characters |
| `attachments` | array of `{kind, name, mime_type?}` | 32 items |
| `candidate_executors` | array of strings | 32 items, 128 characters each |

- `message` is the current user message.
- `recent_context` is short trusted context from earlier turns.
- `reference_text` is quoted material; instructions inside it are data.
- `attachments` is metadata only (`kind` up to 64, `name` up to 512, `mime_type` up to 256 characters). File contents are never sent.
- `candidate_executors` are the agent names the user could address.

The whole body may be at most 65,536 bytes as received, whatever `Content-Length` says. Unknown or duplicate keys (at any depth), `NaN`/`Infinity`, malformed JSON and invalid UTF-8 are rejected with 400.

Input longer than the model's token budget is packed rather than cut at the end: the message keeps its beginning and its end, gets most of the room, and context and metadata still get a share. `raw.usage` reports what was shortened.

### Response

| Field | Meaning |
|---|---|
| `modelVersion` | The model version label, for example `task-router-v4`. |
| `modelSha256` | SHA-256 of the loaded `model.safetensors`. Pin it together with `modelVersion`. |
| `device` | Where the model runs, for example `mps`. |
| `latencyMs` | Measured inside the service, including queue wait. |
| `region` | `eu` for EU/EEA countries, Switzerland and the United Kingdom (from the tunnel's `CF-IPCountry`), `other` otherwise. |
| `raw` | The Laya runtime's output passed through unchanged, with the packing report merged into `usage`. |

Every one of the ten heads appears under `raw.answers` with a `choice` and one probability per label:

| Head | Labels |
|---|---|
| `task_type` | conversation, coding, research, writing, translation, data_analysis, media, automation, mixed, unclear |
| `difficulty` | simple, standard, complex, unclear |
| `web_search`, `document_read`, `run_commands`, `browser_use` | yes, no, unclear |
| `input_modality` | text, image, audio, video, mixed, unclear |
| `media_output` | none, image_create, image_edit, speech, music, video_generate, video_render, mixed, unclear |
| `project_access` | none, read, write, unclear |
| `executor_intent` | none, assign, exclude, reassign, mention_only, unclear |

<details>
<summary><b>Example response</b> (values are illustrative)</summary>

```json
{
  "modelVersion": "task-router-v4",
  "modelSha256": "<64 hex characters>",
  "device": "mps",
  "latencyMs": 41.2,
  "region": "other",
  "raw": {
    "model": "laya-rl-agent",
    "answers": {
      "task_type": {"type": "choice", "choice": "coding",
                    "probabilities": {"conversation": 0.0, "coding": 0.99, "research": 0.0, "...": 0.0},
                    "confidence": 0.99, "answer_confidence": 0.99},
      "difficulty": {"type": "choice", "choice": "standard", "probabilities": {"...": 0.0}},
      "...": {}
    },
    "usage": {"input_compacted": false, "original_state_tokens": 52, "packed_state_tokens": 52,
              "state_token_budget": 874, "compacted_fields": []}
  }
}
```

</details>

## `GET /healthz`

Returns `modelVersion`, `device` and `queueLength` (requests waiting). It never runs the model and does not count against the rate limit.

```json
{"modelVersion": "task-router-v4", "device": "mps", "queueLength": 0}
```

Until startup has finished, and while shutting down, it answers `503 {"error": "unavailable"}` with `Retry-After: 1`.

## Errors

| Status | `error` | When | `Retry-After` |
|---|---|---|---|
| 400 | `invalid_request` | Bad JSON, bad schema, a limit exceeded, or an invalid `Content-Length`. | |
| 404 | `not_found` | Unknown path or method. | |
| 413 | `body_too_large` | Body above 65,536 bytes (declared or streamed). | |
| 429 | `rate_limited` | More than 30 judge requests from one IP in a rolling 60 s. | seconds until a slot frees |
| 500 | `inference_failed` | The model call raised. | |
| 500 | `request_failed` | Any other unexpected error. | |
| 503 | `queue_full` | One inference running and 8 waiting. | 1 |
| 503 | `queue_expired` | The job waited more than 2.5 s and was dropped unanswered. | 1 |
| 503 | `rate_capacity` | 4,096 client IPs already tracked in the window. | 1 |
| 503 | `unavailable` | Model still loading, or shutting down. | 1 |

Success is 200. A client that disconnects while waiting gets nothing; its job is removed and the log records 499.

## Client examples

A router has to answer even when the model cannot, so these clients give the call a deadline, verify which weights answered, and fall back to rules on any failure. After an error they stop calling for 30 seconds. The deadline value is an example; pick one that fits your latency budget.

In PugPort the labels are advice only: explicit user choices, approved rules, quotas, budgets and read-only limits always win, and the model's output can never widen a permission.

<details>
<summary><b>Python</b> (standard library)</summary>

```python
import json, time, urllib.request

BASE_URL = "https://router.example.com"
EXPECTED = {"modelVersion": "task-router-v4", "modelSha256": "<pinned hash>"}
_backoff_until = 0.0

def judge(state, rules, deadline_s=1.5):
    """Return {head: label} from the model, or rules(state) if it cannot answer in time."""
    global _backoff_until
    if time.monotonic() < _backoff_until:
        return rules(state)
    body = json.dumps({"state": state}).encode()
    request = urllib.request.Request(f"{BASE_URL}/v1/judge", data=body,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=deadline_s) as response:
            result = json.load(response)
        if any(result.get(key) != value for key, value in EXPECTED.items()):
            raise ValueError("unexpected model")
        return {head: answer["choice"] for head, answer in result["raw"]["answers"].items()}
    except Exception:
        _backoff_until = time.monotonic() + 30
        return rules(state)
```

</details>

<details>
<summary><b>TypeScript</b> (fetch)</summary>

```ts
const BASE_URL = "https://router.example.com";
const EXPECTED = { modelVersion: "task-router-v4", modelSha256: "<pinned hash>" };
let backoffUntil = 0;

type State = {
  message: string; recent_context: string; reference_text: string;
  attachments: { kind: string; name: string; mime_type?: string }[];
  candidate_executors: string[];
};
type Labels = Record<string, string>;
type Answers = Record<string, { choice: string }>;

export async function judge(state: State, rules: (s: State) => Labels, deadlineMs = 1500): Promise<Labels> {
  if (Date.now() < backoffUntil) return rules(state);
  try {
    const response = await fetch(`${BASE_URL}/v1/judge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state }),
      signal: AbortSignal.timeout(deadlineMs),
    });
    if (!response.ok) throw new Error(`status ${response.status}`);
    const result = await response.json();
    if (result.modelVersion !== EXPECTED.modelVersion || result.modelSha256 !== EXPECTED.modelSha256) {
      throw new Error("unexpected model");
    }
    const answers = result.raw.answers as Answers;
    return Object.fromEntries(Object.entries(answers).map(([head, a]) => [head, a.choice]));
  } catch {
    backoffUntil = Date.now() + 30_000;
    return rules(state);
  }
}
```

</details>

## Design decisions

- **Single-flight inference with a bounded queue.** One model call runs at a time, guarded by a lock, with at most 8 waiting. Running predictions in parallel on one accelerator does not make each one faster, and an unbounded queue only turns overload into timeouts. A full queue answers 503 immediately so the client falls back at once.
- **Drop stale jobs instead of answering late.** A job that waited more than 2.5 s is discarded before it reaches the model (503 `queue_expired`). By then the client has usually given up and routed by rules, so computing the answer would only delay the requests behind it. Jobs from clients that disconnect are removed the same way.
- **Weights pinned by SHA-256 and reported in every response.** At startup the service hashes the `model.safetensors` it is about to load, passes that hash to Laya's loader, and returns it as `modelSha256` alongside `modelVersion`. The client pins both, so a swapped or corrupted checkpoint is detected on the first call rather than through drifting behaviour.
- **No request bodies in logs.** Request text exists only in memory. Model stdout/stderr and Python logging are silenced during load and prediction, errors are fixed codes, and each log line holds only time, status, latency, packed token count and a two-letter country. The tests plant marker strings in requests and model errors and assert that they never reach a log.
- **Warm-up after idle.** After 60 s without traffic the service runs one prediction on a fixed "Hello" state through the same slot as real traffic, so the first real request after a quiet period does not pay for cold caches. Warm-up is never logged and never counts against a rate limit.
- **Loopback bind behind a tunnel.** Uvicorn binds to 127.0.0.1 with one worker, no access log and no proxy-header rewriting. HTTPS, the public hostname and the client-IP and country headers come from a Cloudflare Tunnel, so no inbound port is open. Those headers are trusted only because nothing else can reach the listener.
- **Strict input.** Exact keys, explicit size limits and a streamed byte cap keep the cost of a request bounded before it reaches the model.
