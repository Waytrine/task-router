"""Request contract shared by the service and its tests: the ten heads, input limits and state packing.

Importing this module never imports torch or Laya.
"""
import json

MAX_INPUT = 64 * 1024
MAX_OUTPUT = 256 * 1024
CHOICES = {
    "task_type": ["conversation", "coding", "research", "writing", "translation", "data_analysis", "media", "automation", "mixed", "unclear"],
    "difficulty": ["simple", "standard", "complex", "unclear"],
    "web_search": ["yes", "no", "unclear"],
    "input_modality": ["text", "image", "audio", "video", "mixed", "unclear"],
    "document_read": ["yes", "no", "unclear"],
    "media_output": ["none", "image_create", "image_edit", "speech", "music", "video_generate", "video_render", "mixed", "unclear"],
    "project_access": ["none", "read", "write", "unclear"],
    "run_commands": ["yes", "no", "unclear"],
    "browser_use": ["yes", "no", "unclear"],
    "executor_intent": ["none", "assign", "exclude", "reassign", "mention_only", "unclear"],
}


def valid_text(value, maximum):
    return isinstance(value, str) and len(value) <= maximum


def valid_state(state):
    if not isinstance(state, dict) or set(state) != {"message", "recent_context", "reference_text", "attachments", "candidate_executors"}:
        return False
    if any(not valid_text(state.get(key), 32768) for key in ["message", "recent_context", "reference_text"]):
        return False
    attachments = state["attachments"]
    executors = state["candidate_executors"]
    return (
        isinstance(attachments, list) and len(attachments) <= 32
        and all(isinstance(item, dict) and set(item) <= {"kind", "name", "mime_type"}
                and valid_text(item.get("kind"), 64) and valid_text(item.get("name"), 512)
                and ("mime_type" not in item or valid_text(item["mime_type"], 256)) for item in attachments)
        and isinstance(executors, list) and len(executors) <= 32
        and all(valid_text(item, 128) for item in executors)
    )


def pack_state(state, tokenizer, budget):
    """Keep both ends of the request and budget all fields before Laya's prefix clamp."""
    def encode(text):
        return tokenizer(text.replace(tokenizer.mask_token, " "),
                         add_special_tokens=False, truncation=False)["input_ids"]

    def size(value):
        return len(encode(json.dumps(value, ensure_ascii=False)))

    original_size = size(state)
    packed = dict(state)
    text_ids = {key: encode(state[key])
                for key in ("message", "recent_context", "reference_text")}
    limits = {key: len(ids) for key, ids in text_ids.items()}
    changed = set()
    packed_size = original_size
    while packed_size > budget:
        # The current instruction gets most room; context and metadata still get a share.
        weights = {"message": 6, "recent_context": 1, "reference_text": 2,
                   "attachments": 2, "candidate_executors": 1}
        candidates = [key for key, value in packed.items() if value]
        if not candidates:
            raise ValueError("state_budget_too_small")
        key = max(candidates, key=lambda name: size(packed[name]) / weights[name])
        if key in text_ids:
            limit = limits[key] = max(0, limits[key] // 2)
            ids = text_ids[key]
            if limit < 16:
                packed[key] = ""
            elif key == "recent_context":
                packed[key] = tokenizer.decode(ids[-limit:], clean_up_tokenization_spaces=False)
            else:
                head = limit // 3
                packed[key] = (tokenizer.decode(ids[:head], clean_up_tokenization_spaces=False)
                               + "\n[... omitted ...]\n"
                               + tokenizer.decode(ids[-(limit - head):], clean_up_tokenization_spaces=False))
        else:
            packed[key] = packed[key][:len(packed[key]) // 2]
        changed.add(key)
        packed_size = size(packed)
    return packed, {
        "input_compacted": bool(changed),
        "original_state_tokens": original_size,
        "packed_state_tokens": packed_size,
        "state_token_budget": budget,
        "compacted_fields": sorted(changed),
    }
