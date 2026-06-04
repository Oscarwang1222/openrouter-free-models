#!/usr/bin/env python3
"""
Fetch OpenRouter free models and generate models-global.json / models-cn.json.

Output format matches Oscarwang1222/openrouter-free-models repo schema:
  { "version": "1.0", "updated": "...", "count": N, "models": [ ... ] }

Output directory: same directory as this script (so cron workdir is
irrelevant — script always writes beside itself).
"""
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

URL = "https://openrouter.ai/api/v1/models"
OUT_DIR = Path(__file__).resolve().parent
OUT_GLOBAL = OUT_DIR / "models-global.json"
OUT_CN = OUT_DIR / "models-cn.json"

# Vendors excluded from the CN list. Conservative — when in doubt, drop
# the model from the CN list and let the user decide whether to trust it.
BLOCKED_ORGS_CN = {
    "google", "openai", "anthropic", "anthropic/",
    "google/", "openai/", "anyscale", "replicate",
    "cohere", "mistralai", "meta-llama", "ai21", "stabilityai",
    "azure", "amazon", "x-ai", "x.ai",
}


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


def should_block_cn(model_id):
    org = model_id.lower().split("/", 1)[0] if "/" in model_id else model_id.lower()
    return org in BLOCKED_ORGS_CN


def main():
    print("Fetching models from OpenRouter...")
    try:
        all_models = fetch_models()
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"ERROR: fetch failed: {e}", file=sys.stderr)
        return 1
    print(f"Total models fetched: {len(all_models)}")

    global_free = []
    cn_free = []
    blocked_ids = set()

    for m in all_models:
        if not is_free(m):
            continue
        info = model_info(m)
        global_free.append(info)
        if should_block_cn(m.get("id", "")):
            blocked_ids.add(m["id"])
        else:
            cn_free.append(info)

    # Sort by context_length descending, then by id for stability
    global_free.sort(key=lambda x: (-(x["context_length"] or 0), x["id"]))
    cn_free.sort(key=lambda x: (-(x["context_length"] or 0), x["id"]))

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    result_g = {
        "version": "1.0",
        "updated": now,
        "count": len(global_free),
        "models": global_free,
    }
    result_c = {
        "version": "1.0",
        "updated": now,
        "count": len(cn_free),
        "blocked_orgs": sorted(BLOCKED_ORGS_CN),
        "blocked_ids": sorted(blocked_ids),
        "models": cn_free,
    }

    OUT_GLOBAL.write_text(json.dumps(result_g, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    OUT_CN.write_text(json.dumps(result_c, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")

    print(f"global: {len(global_free)} models -> {OUT_GLOBAL}")
    print(f"cn:     {len(cn_free)} models -> {OUT_CN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
