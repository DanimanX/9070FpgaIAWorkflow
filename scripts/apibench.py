"""Same-method A/B benchmark for any OpenAI-compatible local server (used for the RustingStrata vs Strata table).
Streams a chat completion and reports TTFT, approximate prefill and decode tok/s.
usage: python3 -I scripts/apibench.py URL MODEL CTX_FILE [n_tokens]   (CTX_FILE: ~24 KB of real code for the long prompt)"""
import json, sys, time, urllib.request

url, model, ctxfile = sys.argv[1], sys.argv[2], sys.argv[3]
ntok = int(sys.argv[4]) if len(sys.argv) > 4 else 256
ctx = open(ctxfile).read()
tasks = [
    ("short", "Write a SystemVerilog module for a parameterized synchronous FIFO with full/empty flags. Code only."),
    ("long", "Summarize what the following code does, listing each module/function and its role:\n\n" + ctx),
]
for name, prompt in tasks:
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": ntok,
            "temperature": 0, "stream": True, "stream_options": {"include_usage": True},
            "reasoning_effort": "none", "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(url + "/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    t0 = time.time(); first = None; chunks = 0; usage = None
    with urllib.request.urlopen(req, timeout=600) as r:
        for line in r:
            line = line.decode().strip()
            if not line.startswith("data:") or line == "data: [DONE]":
                continue
            d = json.loads(line[5:])
            if d.get("usage"):
                usage = d["usage"]
            for c in d.get("choices", []):
                delta = c.get("delta", {})
                if delta.get("content") or delta.get("reasoning_content"):
                    if first is None:
                        first = time.time()
                    chunks += 1
    t1 = time.time()
    pt = usage["prompt_tokens"] if usage else None
    ct = usage["completion_tokens"] if usage else chunks
    ttft = first - t0
    dec = (ct - 1) / (t1 - first) if t1 > first else 0
    pre = f"{pt / ttft:.0f}" if pt else "?"
    print(f"{name:5s} prompt={pt} gen={ct} ttft={ttft:.2f}s prefill~{pre} tok/s decode={dec:.1f} tok/s")
