#!/usr/bin/env python3
"""
Fetch OpenRouter free models and generate global/cn JSON files.
Eliminates Google, OpenAI, Anthropic models for cn version.
"""
import json, urllib.request, urllib.error, time

URL = "https://openrouter.ai/api/v1/models"
OUT_GLOBAL = "/tmp/orfm/models-global.json"
OUT_CN      = "/tmp/orfm/models-cn.json"

BLOCKED_ORGS_CN = {
    "google", "openai", "anthropic", "anthropic/",
    "google/", "openai/", "anyscale", "replicate",
    "cohere", "mistralai", "meta-llama", "ai21", "stabilityai",
    "azure", "amazon", "x-ai", "x.ai"
}

def fetch_models():
    req = urllib.request.Request(URL, headers={"Authorization": "Bearer sk-or-v1-demo"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("data", [])

def is_free(model):
    p = model.get("pricing", {})
    prompt = p.get("prompt", "0")
    try:
        return float(prompt) == 0.0
    except (TypeError, ValueError):
        return False

def model_info(m):
    id   = m.get("id", "")
    name = m.get("name", id)
    ctx  = m.get("context_length", 0)
    # input modalities
    mods = m.get("architecture", {}).get("input_modalities", [])
    return {"id": id, "name": name, "context_length": ctx, "input_modalities": mods}

def should_block_cn(model_id):
    oid = model_id.lower().split("/")[0] if "/" in model_id else model_id.lower()
    return oid in BLOCKED_ORGS_CN

print("Fetching models from OpenRouter...")
all_models = fetch_models()
print(f"Total models fetched: {len(all_models)}")

global_free = []
cn_free = []
blocked_ids = set()

for m in all_models:
    if not is_free(m):
        continue
    info = model_info(m)
    global_free.append(info)
    if not should_block_cn(m["id"]):
        cn_free.append(info)
    else:
        blocked_ids.add(m["id"])

# Sort both by context_length descending
global_free.sort(key=lambda x: x["context_length"], reverse=True)
cn_free.sort(key=lambda x: x["context_length"], reverse=True)

result_g = {
    "version": "1.0",
    "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "count": len(global_free),
    "models": global_free
}
result_c = {
    "version": "1.0",
    "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "count": len(cn_free),
    "blocked_orgs": sorted(BLOCKED_ORGS_CN),
    "blocked_ids": sorted(blocked_ids),
    "models": cn_free
}

with open(OUT_GLOBAL, "w") as f:
    json.dump(result_g, f, ensure_ascii=False, indent=2)
with open(OUT_CN, "w") as f:
    json.dump(result_c, f, ensure_ascii=False, indent=2)

print(f"global: {len(global_free)} models  -> {OUT_GLOBAL}")
print(f"cn:     {len(cn_free)} models  -> {OUT_CN}")