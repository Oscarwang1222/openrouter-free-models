#!/usr/bin/env python3
"""
Fetch OpenRouter free models and generate:
  - models-global.json         (free models, sorted by context length)
  - models-strong-global.json  (free models, sorted strongest -> weakest)

Output format matches Oscarwang1222/openrouter-free-models repo schema:
  { "version": "1.0", "updated": "...", "count": N, "models": [ ... ] }

Output directory: same directory as this script (so cron workdir is
irrelevant — script always writes beside itself).
"""
import json
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

URL = "https://openrouter.ai/api/v1/models"
OUT_DIR = Path(__file__).resolve().parent
OUT_GLOBAL = OUT_DIR / "models-global.json"
OUT_STRONG_GLOBAL = OUT_DIR / "models-strong-global.json"

# --- Strength ranking (heuristic; lower tier = stronger) -----------------
# Tier 0: frontier-grade open weights (DeepSeek flagship, Qwen flagship,
#          GLM-4.6+, Kimi K2, Llama 405B, Hermes 3 405B).
# Tier 1: strong open weights 70B+ (DeepSeek-V3-lite, Qwen 72B, GLM-4,
#          Llama 70B, Nemotron Ultra/Super, Poolside Laguna).
# Tier 2: mid-size open weights 20B-32B (Nemotron Nano, Qwen 32B,
#          Mistral-Large-class, Dolphin Mistral 24B, Venice).
# Tier 3: small instruct models <20B (Llama 8B, Qwen 7B/14B,
#          Mistral 7B, Nemotron Nano 9B/12B, GLM 4.5 Air).
# Tier 4: tiny / specialised / router models (Liquid 1.2B, OpenRouter
#          free router, content-safety classifiers).
TIER_BY_ORG = {
    "deepseek": 0,
    "qwen": 0,
    "z-ai": 0,
    "moonshotai": 0,
    "nousresearch": 1,  # mostly fine-tunes of strong base models
    "meta-llama": 1,
    "nvidia": 1,        # Nemotron Ultra/Super live here; Nano drops via params
    "poolside": 1,
    "nex-agi": 1,
    "mistralai": 2,
    "cognitivecomputations": 3,  # Dolphin fine-tunes
    "liquid": 4,
    "openrouter": 4,
}

# Model-name hints that bump a model up/down within its tier.
# Each entry is (pattern_regex, delta) — delta is ADDED to the tier.
TIER_HINTS = [
    # Big boosters (move to tier 0)
    (r"deepseek[-_]?(r1|v3|v4|chat)", 0),       # top DeepSeek variants → tier 0
    (r"qwen3?[-_]?(?:max|plus|235b|480b)", 0),  # flagship Qwen → tier 0
    (r"glm-?4\.?(?:6|5|plus)", 0),              # GLM 4.5+/Plus → tier 0
    (r"kimi[-_]?k2", 0),                        # Kimi K2 → tier 0
    (r"llama[-_]?3\.?1[-_]?405b", 0),           # Llama 3.1 405B → tier 0
    # Big demoters (move to tier 4)
    (r"content[-_]?safety", 3),                 # safety classifiers → tier 4
    (r"free[-_]?router|router", 3),             # meta-router → tier 4
    # Mid boosters (move to tier 1)
    (r"nemotron[-_]?3[-_]?(?:ultra|super)", 0), # Nemotron flagship → tier 0
    (r"nemotron[-_]?3[-_]?nano", 2),            # Nano line → tier 2
    (r"laguna[-_]?(?:m|l|xl)", 0),              # Poolside flagship → tier 0
    (r"dolphin", 2),                            # Dolphin → tier 2
    (r"venice", 2),                             # Venice uncensored → tier 2
    # Small model demoter
    (r"1\.?[0-9]?b[-_]?(?:instruct|thinking)", 3),
    (r"nano[-_]?(?:9b|12b)", 2),
]


def fetch_models():
    # /v1/models is a public endpoint — no auth required.
    req = urllib.request.Request(URL, headers={"User-Agent": "orfm-sync/2.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("data", [])


def is_free(model):
    """Prompt price == 0. Matches the upstream script's behavior."""
    p = model.get("pricing") or {}
    prompt = p.get("prompt", "0")
    try:
        return float(prompt) == 0.0
    except (TypeError, ValueError):
        return False


def model_info(m):
    mid = m.get("id", "")
    name = m.get("name") or mid
    ctx = m.get("context_length", 0)
    mods = (m.get("architecture") or {}).get("input_modalities", []) or []
    return {
        "id": mid,
        "name": name,
        "context_length": ctx,
        "input_modalities": mods,
    }


def _extract_param_billions(text):
    """Best-effort extraction of total parameter count from an id/name.

    Returns float billions, or None if nothing matched.
    Handles things like '70b', '8b', '1.2b', '120b-a12b' (returns 120),
    '480b-a35b' (returns 480), '405b' (returns 405).
    """
    if not text:
        return None
    # Prefer total-params before the "-a{active}" suffix (MoE).
    # e.g. '120b-a12b' → 120, '480b-a35b' → 480
    m = re.search(r"(\d+(?:\.\d+)?)\s*b(?=[-_]?a\d|\b|$)", text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def strength_key(model):
    """Sort key: (tier, -params_b, -context_length, id). Lower = stronger."""
    mid = (model.get("id") or "").lower()
    name = (model.get("name") or "").lower()
    org = mid.split("/", 1)[0] if "/" in mid else mid

    tier = TIER_BY_ORG.get(org, 3)  # unknown orgs → tier 3
    for pat, delta in TIER_HINTS:
        if re.search(pat, mid) or re.search(pat, name):
            tier = max(0, tier + delta)
            break  # one hint wins; the first match in order

    params_b = _extract_param_billions(mid) or _extract_param_billions(name) or 0.0
    ctx = model.get("context_length") or 0
    return (tier, -params_b, -ctx, mid)


def main():
    print("Fetching models from OpenRouter...")
    try:
        all_models = fetch_models()
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"ERROR: fetch failed: {e}", file=sys.stderr)
        return 1
    print(f"Total models fetched: {len(all_models)}")

    free = []
    for m in all_models:
        if is_free(m):
            free.append(model_info(m))

    # --- Sort by context length -------------------------------------------
    by_ctx = sorted(free, key=lambda x: (-(x["context_length"] or 0), x["id"]))

    # --- Sort strongest -> weakest ----------------------------------------
    by_strength = sorted(free, key=strength_key)

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    payload_ctx = {
        "version": "1.0",
        "updated": now,
        "count": len(by_ctx),
        "models": by_ctx,
    }
    payload_strong = {
        "version": "1.0",
        "updated": now,
        "count": len(by_strength),
        "models": by_strength,
    }

    for path, payload in [
        (OUT_GLOBAL, payload_ctx),
        (OUT_STRONG_GLOBAL, payload_strong),
    ]:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    print(f"global:        {len(by_ctx)} models -> {OUT_GLOBAL}")
    print(f"strong-global: {len(by_strength)} models -> {OUT_STRONG_GLOBAL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())