"""IBM Granite via a local Ollama server (free, no API key)."""
import json, os, time, urllib.request
OLLAMA = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("LLM_MODEL", "granite4-micro")

def _body(prompt, max_tokens, system, stream):
    # keep_alive -1: Granite stays in memory; reloading it after an idle spell costs 10-100 s on CPU.
    body = {"model": MODEL, "prompt": prompt, "stream": stream, "keep_alive": -1,
            "options": {"temperature": 0, "num_predict": max_tokens}}
    if system: body["system"] = system
    return urllib.request.Request(f"{OLLAMA}/api/generate", data=json.dumps(body).encode(),
                                  headers={"Content-Type": "application/json"})

def generate(prompt, max_tokens=180, system=None):
    return json.load(urllib.request.urlopen(_body(prompt, max_tokens, system, False), timeout=300))["response"].strip()

def stream(prompt, max_tokens=180, system=None, stop=None):
    """Yield text pieces as Granite writes them. `stop(text_so_far)` returning True ends generation early
    (closing the connection makes Ollama stop). The last item is a dict with timings."""
    t0, text, first = time.time(), "", None
    resp = urllib.request.urlopen(_body(prompt, max_tokens, system, True), timeout=300)
    stats = {}
    try:
        for line in resp:
            if not line.strip(): continue
            m = json.loads(line)
            piece = m.get("response", "")
            if piece:
                if first is None: first = time.time()
                text += piece; yield piece
            if m.get("done"):
                stats = m; break
            if stop and stop(text): break
    finally:
        resp.close()
    yield {"ms_total": int((time.time() - t0) * 1000), "ms_first_token": int(((first or time.time()) - t0) * 1000),
           "prompt_tokens": stats.get("prompt_eval_count"), "text": text}

def warm():
    """Load Granite into memory (one token), so the first visitor does not wait for the model to load."""
    generate("Say OK.", max_tokens=1)
