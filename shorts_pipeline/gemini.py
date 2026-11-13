"""Optional Google Gemini helpers (free Google AI Studio key in GEMINI_API_KEY).

Gemini is never required. Every caller has a local fallback, and this module raises
GeminiUnavailable whenever Gemini cannot answer (no key, daily quota used up, the job's own
request budget spent, the service down, or a safety block), so the pipeline always finishes.

What it is used for (each caller documents its own fallback):
- watch_clip:    watches a public YouTube clip (no download) → what happens, second by second,
                 whether it is really a scene of this movie, overlays to avoid, the peak moment
- the writer:    a stronger, faster script writer with a much bigger context (writer.py)
- scene_hints:   the movie's most talked-about scenes, from Google Search, for better searches
- embed:         sentence ↔ shot-description similarity for the edit
- pick_cover:    picks the strongest real frame for the cover, plus 2–4 cover words
- critique:      watches the finished Short and reviews it like a strict editor

Models are discovered from the API (the newest Flash / Flash-Lite / embedding models, or
Google's "-latest" aliases), never hardcoded, because Google retires model names often.
SHORTS_GEMINI_<ROLE>_MODEL overrides a role, e.g. SHORTS_GEMINI_SMART_MODEL=gemini-flash-latest.
"""
from __future__ import annotations

import base64
import json
import math
import os
import re
import sys
import time
from pathlib import Path

API = "https://generativelanguage.googleapis.com"
ROLES = ("smart", "light", "embed")
EXCLUDE = re.compile(r"tts|image|live|audio|native|embedding|robotics|computer|learnlm|gemma|aqa|vision|thinking-exp", re.I)
SAFETY = [{"category": c, "threshold": "BLOCK_ONLY_HIGH"} for c in (
    "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "HARM_CATEGORY_DANGEROUS_CONTENT")]  # movie violence is described, not promoted
MAX_WAIT = 65.0        # longest per-minute rate-limit wait before giving up on Gemini for a request
MAX_MODELS_PER_REQUEST = 6
MINUTE_WAIT = float(os.environ.get("SHORTS_GEMINI_MINUTE_WAIT", "60"))  # wait after a per-minute limit
MINUTE_RETRIES = int(os.environ.get("SHORTS_GEMINI_MINUTE_RETRIES", "2"))  # same model, after waiting
MIN_GAP = float(os.environ.get("SHORTS_GEMINI_MIN_GAP", "6"))  # seconds between this job's requests
REQUEST_WAIT = float(os.environ.get("SHORTS_GEMINI_REQUEST_WAIT", "150"))  # most waiting for one answer
JOB_WAIT = float(os.environ.get("SHORTS_GEMINI_JOB_WAIT", "900"))  # most waiting for limits in one job
MAX_VIDEO_SECONDS = 20 * 60
TPM_LIMIT = int(os.environ.get("SHORTS_GEMINI_TPM", "200000"))  # input tokens per minute per (key, model), with margin
DEFAULT_OUTPUT_TOKENS = int(os.environ.get("SHORTS_GEMINI_OUTPUT_TOKENS", "8192"))
BIG_OUTPUT_TOKENS = 32768


class GeminiUnavailable(RuntimeError):
    """Gemini cannot answer this request; use the local fallback."""


def api_keys() -> list[str]:
    """Every configured key, first one first: GEMINI_API_KEY, GEMINI_API_KEY_2.._5, GEMINI_API_KEYS (comma
    separated) and GOOGLE_API_KEY. Empty ones are ignored, duplicates once."""
    found = [os.environ.get("GEMINI_API_KEY", "")]
    found += [os.environ.get(f"GEMINI_API_KEY_{n}", "") for n in range(2, 6)]
    found += (os.environ.get("GEMINI_API_KEYS") or "").split(",") + [os.environ.get("GOOGLE_API_KEY", "")]
    return list(dict.fromkeys(k.strip() for k in found if k and k.strip()))


def api_key() -> str:
    keys = api_keys()
    return keys[0] if keys else ""


def enabled() -> bool:
    return bool(api_key()) and os.environ.get("SHORTS_GEMINI", "auto").lower() not in ("0", "off", "false", "no")


def _version(name: str) -> float:
    found = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
    return float(found.group(1)) if found else 0.0


def rank_models(models: list[dict], role: str) -> list[str]:
    """Best first, from the API's model list. Aliases ending in -latest win (Google keeps them
    pointing at the newest model); otherwise the highest version, stable before preview."""
    names = []
    for m in models:
        name = m.get("name", "").split("/", 1)[-1]
        methods = m.get("supportedGenerationMethods") or []
        if role == "embed":
            if "embedding" in name and ("embedContent" in methods or not methods):
                names.append(name)
            continue
        if "generateContent" not in methods and methods:
            continue
        if not name.startswith("gemini") or EXCLUDE.search(name) or "flash" not in name:
            continue
        lite = "lite" in name
        if (role == "light") != lite:
            continue
        names.append(name)

    def key(name: str):
        return ("latest" in name, _version(name), "preview" not in name and "exp" not in name, -len(name))
    return sorted(set(names), key=key, reverse=True)


class Client:
    """Small REST client: JSON output, YouTube links, file uploads, embeddings, retries, budget.

    Several API keys (GEMINI_API_KEY, GEMINI_API_KEY_2.._5, GEMINI_API_KEYS) share the work. Google's free
    limits are per project and per model, so the state is kept per (key, model):
    - requests are spaced (MIN_GAP) and a rolling 60-second input-token window is respected (TPM), so a
      request waits for room instead of hitting a 429;
    - a per-minute 429 cools that (key, model) down and the next key is tried at once;
    - a per-day 429 retires that (key, model) for the day; a zero limit is remembered for good;
    - only when every key is cooling down does the job wait.
    """

    def __init__(self, key: str | None = None, *, session=None, sleep=time.sleep, max_calls: int | None = None,
                 keys: list[str] | None = None):
        import requests
        self.keys = [k for k in (keys or ([key] if key else api_keys())) if k]
        if not self.keys:
            raise GeminiUnavailable("no GEMINI_API_KEY")
        self.key = self.keys[0]
        self.session = session or requests.Session()
        self.sleep = sleep
        per_key = max_calls if max_calls is not None else int(os.environ.get("SHORTS_GEMINI_MAX_CALLS", "80"))
        self.max_calls = per_key * len(self.keys)
        self.calls: list[dict] = []
        self.ex: list[set[str]] = [set() for _ in self.keys]        # per key: no quota left today
        self.nf: list[set[str]] = [set() for _ in self.keys]        # per key: free limit is 0, on every day
        self.cool: dict[tuple[int, str], float] = {}                 # (key, model) → usable again after this time
        self.last: dict[tuple[int, str], float] = {}                 # (key, model) → time of the last request
        self.window: dict[tuple[int, str], list[tuple[float, int]]] = {}  # (key, model) → (time, input tokens)
        self.file_key: dict[str, int] = {}                          # uploaded file → the key that owns it
        self.good: dict[str, str] = {}         # the model that last answered, per role: tried first
        self.last_call = 0.0
        self.waited = 0.0                      # seconds spent waiting for limits in this job
        self._request_wait = REQUEST_WAIT
        self.state_file = Path(os.environ["SHORTS_GEMINI_STATE"]) if os.environ.get("SHORTS_GEMINI_STATE") else None
        self._load_state()
        self._models: dict[str, list[str]] | None = None

    # ------------------------------------------------------------------ views (all keys together)
    @property
    def exhausted(self) -> set[str]:
        """Models no key can use today."""
        return set.intersection(*[e | n for e, n in zip(self.ex, self.nf)]) if self.keys else set()

    @property
    def never_free(self) -> set[str]:
        return set.intersection(*self.nf) if self.keys else set()

    @property
    def cooldown(self) -> dict[str, float]:
        """Per model: when the first key that may still use it is free again (only models cooling on every key)."""
        out: dict[str, float] = {}
        now = time.time()
        for (k, model), until in self.cool.items():
            usable = [i for i in range(len(self.keys)) if model not in self.ex[i] | self.nf[i]]
            if k in usable and all(self.cool.get((i, model), 0) > now for i in usable):
                out[model] = min(self.cool.get((i, model), 0) for i in usable)
        return out

    def _usable_keys(self, model: str) -> list[int]:
        return [i for i in range(len(self.keys)) if model not in self.ex[i] | self.nf[i]]

    # ------------------------------------------------------------------ shared state
    @staticmethod
    def _quota_day() -> str:
        """Google resets daily limits at midnight Pacific time (UTC-8, or UTC-7 in summer)."""
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc) - timedelta(hours=8)).strftime("%Y-%m-%d")

    @staticmethod
    def _key_id(key: str) -> str:
        import hashlib
        return hashlib.sha256(key.encode()).hexdigest()[:12]  # never the key itself

    def _load_state(self) -> None:
        """Models an earlier job already found used up today are skipped without spending a request."""
        try:
            data = json.loads(self.state_file.read_text()) if self.state_file and self.state_file.exists() else {}
        except (OSError, ValueError):
            data = {}
        per_key = data.get("keys") or {}
        for i, key in enumerate(self.keys):
            row = per_key.get(self._key_id(key)) or (data if i == 0 and not per_key else {})
            self.nf[i] |= set(row.get("never_free") or [])
            if data.get("day") == self._quota_day():
                self.ex[i] |= set(row.get("exhausted") or [])

    def _save_state(self) -> None:
        if not self.state_file:
            return
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            keys = {self._key_id(k): {"exhausted": sorted(self.ex[i] - self.nf[i]), "never_free": sorted(self.nf[i])}
                    for i, k in enumerate(self.keys)}
            first = keys[self._key_id(self.keys[0])]
            self.state_file.write_text(json.dumps({"day": self._quota_day(), **first, "keys": keys}))
        except OSError:
            pass

    # ------------------------------------------------------------------ plumbing
    def _http(self, method: str, url: str, *, key: int = 0, **kwargs):
        headers = {"x-goog-api-key": self.keys[key], **kwargs.pop("headers", {})}
        try:
            return self.session.request(method, url, headers=headers, timeout=kwargs.pop("timeout", 600), **kwargs)
        except Exception as exc:  # noqa: BLE001 - network trouble means "use the fallback"
            raise GeminiUnavailable(f"network: {str(exc)[:160]}") from exc

    def models(self) -> dict[str, list[str]]:
        if self._models is None:
            found, token = [], ""
            for _ in range(10):
                reply = self._http("GET", f"{API}/v1beta/models", params={"pageSize": 1000, **({"pageToken": token} if token else {})})
                if reply.status_code != 200:
                    raise GeminiUnavailable(f"model list: HTTP {reply.status_code} {reply.text[:160]}")
                data = reply.json()
                found += data.get("models", [])
                token = data.get("nextPageToken") or ""
                if not token:
                    break
            self._models = {role: rank_models(found, role) for role in ROLES}
            for role in ROLES:
                override = os.environ.get(f"SHORTS_GEMINI_{role.upper()}_MODEL")
                if override:
                    self._models[role] = [override] + [m for m in self._models[role] if m != override]
        return self._models

    def chain(self, role: str) -> list[str]:
        """Models to try for a role: its own models, then (for smart only) the lighter ones."""
        models = self.models()
        names = list(models.get(role, []))
        if role == "smart":
            names += models.get("light", [])
        # Light work (watching clips, matching titles, searches) never falls back to the smart models: their
        # small free daily limit is kept for writing. A busy light model is waited for instead.
        if self.good.get(role) in names:
            names.insert(0, self.good[role])
        now = time.time()
        return [n for n in dict.fromkeys(names)
                if any(self.cool.get((k, n), 0) <= now for k in self._usable_keys(n))]

    @staticmethod
    def estimate_tokens(body: dict) -> int:
        """Rough input size: text / 4, ~258 per image, ~100 per second of low-resolution video."""
        total = 0
        for content in body.get("contents") or []:
            for part in content.get("parts") or []:
                if "text" in part:
                    total += len(part["text"]) // 4
                elif "inlineData" in part:
                    total += 258 if str(part["inlineData"].get("mimeType", "")).startswith("image") else \
                        len(part["inlineData"].get("data", "")) // 1000
                elif "fileData" in part:
                    meta = part.get("videoMetadata") or {}
                    try:
                        seconds = float(str(meta.get("endOffset", "60s")).rstrip("s")) - \
                            float(str(meta.get("startOffset", "0s")).rstrip("s"))
                    except ValueError:
                        seconds = 60.0
                    total += int(max(1.0, seconds) * 100)
        for part in (body.get("systemInstruction") or {}).get("parts") or []:
            total += len(part.get("text", "")) // 4
        return max(1, total)

    def _room(self, slot: tuple[int, str], tokens: int) -> float:
        """Seconds to wait before this (key, model) may send: request spacing and the input-token window."""
        now = time.time()
        wait = MIN_GAP - (now - self.last.get(slot, 0.0))
        window = [(t, n) for t, n in self.window.get(slot, []) if now - t < 60]
        self.window[slot] = window
        used = sum(n for _, n in window)
        if window and used + tokens > TPM_LIMIT:
            freed, need = 0, used + tokens - TPM_LIMIT
            for t, n in window:  # oldest first: wait until enough has left the minute
                freed += n
                if freed >= need:
                    wait = max(wait, 60 - (now - t) + 0.5)
                    break
        return max(0.0, wait)

    def _post(self, model: str, method: str, body: dict) -> dict:
        """One request on the first key that may send it. Per-minute limit → next key (or a bounded wait);
        daily limit → that key is done with this model for today."""
        if len(self.calls) >= self.max_calls:
            raise GeminiUnavailable(f"this job's Gemini budget ({self.max_calls} requests) is spent")
        tokens = self.estimate_tokens(body)
        pinned = next((self.file_key[u] for u in re.findall(r'"fileUri":\s*"([^"]+)"', json.dumps(body))
                       if u in self.file_key), None)  # an uploaded file only exists for the key that uploaded it
        minute_waits, server_errors, errors = 0, 0, []
        while True:
            keys = [k for k in self._usable_keys(model) if pinned is None or k == pinned]
            if not keys:
                raise _Exhausted(f"{model}: {errors[-1] if errors else 'no key can use it today'}")
            now = time.time()
            ready = [k for k in keys if self.cool.get((k, model), 0) <= now]
            if not ready:  # every key is cooling down: wait for the first one, within the job's limits
                first = min(keys, key=lambda i: self.cool[(i, model)])
                pause = round(self.cool[(first, model)] - now + 1, 1)
                if minute_waits >= MINUTE_RETRIES or pause > self._request_wait or self.waited + pause > JOB_WAIT:
                    raise _Exhausted(f"{model}: {errors[-1] if errors else 'per-minute limit on every key'}")
                minute_waits += 1
                self._request_wait -= pause
                self.waited += pause
                self.sleep(pause)
                self.cool.pop((first, model), None)  # its minute is over
                continue
            k = min(ready, key=lambda i: self._room((i, model), tokens))
            slot = (k, model)
            pause = self._room(slot, tokens)
            if pause > 0:
                if pause > MIN_GAP + 0.01:  # a token-window wait (spacing waits are routine)
                    self.waited += pause
                self.sleep(pause)
            started = self.last_call = self.last[slot] = time.time()
            self.window.setdefault(slot, []).append((started, tokens))
            reply = self._http("POST", f"{API}/v1beta/models/{model}:{method}", key=k, json=body)
            row = {"model": model, "key": k + 1, "method": method, "status": reply.status_code,
                   "seconds": round(time.time() - started, 1), "input_estimate": tokens}
            self.calls.append(row)
            if reply.status_code == 200:
                data = reply.json()
                usage = data.get("usageMetadata") or {}
                row.update(prompt_tokens=usage.get("promptTokenCount", 0), output_tokens=usage.get("candidatesTokenCount", 0))
                if usage.get("promptTokenCount"):  # learn the real size for the window
                    self.window[slot][-1] = (started, int(usage["promptTokenCount"]))
                return data
            text = reply.text[:4000]
            if reply.status_code == 429:
                wait, daily, why = quota_problem(text)
                row["error"], row["google_says"] = why, google_message(text)
                errors.append(why)
                label = f"{model} (key {k + 1})" if len(self.keys) > 1 else model
                print(f"[gemini] {label}: {why} — Google: {row['google_says'][:300]}", file=sys.stderr, flush=True)
                if daily:  # nothing left today for this key on this model: never ask it again today
                    self.ex[k].add(model)
                    if why.startswith("free limit is 0"):
                        self.nf[k].add(model)  # not a daily limit: this key never gets this model
                    self._save_state()
                    continue  # the next key, if any
                self.cool[slot] = time.time() + max(wait, MINUTE_WAIT if len(self.keys) == 1 else wait)
                continue  # another key now, or a bounded wait when all are cooling
            if reply.status_code in (500, 502, 503, 504) and server_errors < 3:
                server_errors += 1
                self.sleep(4 * 2 ** (server_errors - 1))
                continue
            if reply.status_code == 404:
                self.ex[k].add(model)
                if not self._usable_keys(model):
                    raise _Exhausted(f"{model}: not available ({text[:160]})")
                continue
            raise _BadRequest(f"{model}: HTTP {reply.status_code} {text[:300]}")

    def smart_ready(self) -> str | None:
        """The first smart model that still answers today on any key (one tiny request), or None when only
        the light models are left. Models already known to be used up are not asked again."""
        light = set(self.models().get("light", []))
        for model in self.models().get("smart", []):
            if model in light or not self._usable_keys(model):
                continue
            body = {"contents": [{"role": "user", "parts": [{"text": "Reply with the word ok."}]}],
                    "generationConfig": {"temperature": 0, "maxOutputTokens": 4}}
            try:
                self._post(model, "generateContent", body)
                self.good["smart"] = model
                return model
            except (_Exhausted, _BadRequest):
                continue
        return None

    # ------------------------------------------------------------------ generation
    def generate(self, role: str, parts: list[dict], *, system: str | None = None, schema: dict | None = None,
                 temperature: float = 0.4, seed: int | None = None, tools: list | None = None,
                 low_media: bool = False, max_tokens: int | None = None) -> dict | str:
        """Text (or parsed JSON when `schema` is given) from the best model still available."""
        self._request_wait = REQUEST_WAIT
        for round_ in range(2):
            try:
                return self._generate(role, parts, system=system, schema=schema, temperature=temperature, seed=seed,
                                      tools=tools, low_media=low_media, max_tokens=max_tokens)
            except GeminiUnavailable:
                # Every model is only pausing for its per-minute limit: wait for the first one, once.
                waiting = [t for m, t in self.cooldown.items() if t > time.time()]
                pause = (min(waiting) - time.time() + 1) if waiting else 0
                if round_ or not waiting or pause > min(MAX_WAIT, self._request_wait) or self.waited + pause > JOB_WAIT \
                        or self.chain(role):
                    raise
                self.waited += pause
                self.sleep(pause)
        raise GeminiUnavailable("no Gemini model answered")

    def _generate(self, role, parts, *, system, schema, temperature, seed, tools, low_media, max_tokens=None):
        errors = []
        for model in self.chain(role)[:MAX_MODELS_PER_REQUEST]:
            limit = max_tokens or DEFAULT_OUTPUT_TOKENS
            for attempt in range(2):  # a reply cut off by the output limit is asked again with more room
                config: dict = {"temperature": temperature, "maxOutputTokens": limit}
                if seed is not None:
                    config["seed"] = seed
                if low_media:
                    config["mediaResolution"] = "MEDIA_RESOLUTION_LOW"
                use_schema = schema is not None and not tools  # search grounding cannot be combined with JSON mode
                if use_schema:
                    config.update(responseMimeType="application/json", responseJsonSchema=schema)
                body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": config, "safetySettings": SAFETY}
                if system:
                    body["systemInstruction"] = {"parts": [{"text": system}]}
                if tools:
                    body["tools"] = tools
                try:
                    try:
                        data = self._post(model, "generateContent", body)
                    except _BadRequest as exc:
                        if (use_schema and "responseJsonSchema" in str(exc)) or "mediaResolution" in str(exc):
                            config.pop("responseJsonSchema", None)  # older model: JSON mode with the schema in the prompt
                            config.pop("mediaResolution", None)
                            body["contents"][0]["parts"] = parts + ([{"text": "Answer as JSON matching this schema:\n" +
                                                                      json.dumps(schema)}] if schema else [])
                            data = self._post(model, "generateContent", body)
                        else:
                            raise
                    cut = ((data.get("candidates") or [{}])[0] or {}).get("finishReason") == "MAX_TOKENS"
                    try:
                        text = _text(data)
                        result = _parse_json(text) if schema is not None else text
                    except _BadRequest:
                        if cut and attempt == 0:
                            limit = min(BIG_OUTPUT_TOKENS, limit * 4)
                            continue
                        raise
                    self.calls[-1]["role"] = role
                    self.good[role] = model
                    return result
                except (_Exhausted, _BadRequest) as exc:
                    errors.append(str(exc)[:200])
                    if not str(exc).split(": ", 1)[-1].startswith(("daily", "free limit", "per-minute")):
                        # quota answers are printed where they happen; everything else is printed here
                        print(f"[gemini] {str(exc)[:300]}", file=sys.stderr, flush=True)
                    break
        raise GeminiUnavailable("; ".join(errors) or f"no Gemini model for {role}")

    def upload(self, path: Path, mime: str = "video/mp4", wait: float = 300) -> dict:
        """Files API (free, kept 48 h): returns the file record once it is ready to use."""
        path = Path(path)
        wanted = self.models().get("smart", []) + self.models().get("light", [])
        key = next((i for i in range(len(self.keys))  # a key that can still use a model to read the file with
                    if any(m not in self.ex[i] | self.nf[i] for m in wanted)), 0)
        start = self._http("POST", f"{API}/upload/v1beta/files", key=key, headers={
            "X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(path.stat().st_size),
            "X-Goog-Upload-Header-Content-Type": mime, "Content-Type": "application/json"},
            json={"file": {"display_name": path.name[:100]}})
        url = start.headers.get("x-goog-upload-url") or start.headers.get("X-Goog-Upload-URL")
        if start.status_code != 200 or not url:
            raise GeminiUnavailable(f"upload start: HTTP {start.status_code} {start.text[:160]}")
        with open(path, "rb") as handle:
            done = self._http("POST", url, key=key, headers={"X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize",
                                                    "Content-Length": str(path.stat().st_size)}, data=handle, timeout=900)
        if done.status_code != 200:
            raise GeminiUnavailable(f"upload: HTTP {done.status_code} {done.text[:160]}")
        record = done.json().get("file", {})
        deadline = time.time() + wait
        while record.get("state") == "PROCESSING" and time.time() < deadline:
            self.sleep(5)
            reply = self._http("GET", f"{API}/v1beta/{record['name']}", key=key)
            record = reply.json() if reply.status_code == 200 else record
        if record.get("state") not in (None, "ACTIVE"):
            raise GeminiUnavailable(f"uploaded file not usable: {record.get('state')}")
        if record.get("uri"):
            self.file_key[record["uri"]] = key
        return record

    def delete(self, record: dict) -> None:
        try:
            self._http("DELETE", f"{API}/v1beta/{record['name']}", key=self.file_key.get(record.get("uri", ""), 0))
        except Exception:  # noqa: BLE001 - files expire on their own after 48 h
            pass

    def embed(self, texts: list[str]) -> list[list[float]]:
        errors = []
        for model in self.chain("embed"):
            body = {"requests": [{"model": f"models/{model}", "content": {"parts": [{"text": t[:2000] or " "}]}}
                                 for t in texts]}
            try:
                data = self._post(model, "batchEmbedContents", body)
                return [e.get("values", []) for e in data.get("embeddings", [])]
            except (_Exhausted, _BadRequest) as exc:
                errors.append(str(exc)[:200])
        raise GeminiUnavailable("; ".join(errors) or "no embedding model")

    def usage(self) -> dict:
        models = {}
        for call in self.calls:
            models[call["model"]] = models.get(call["model"], 0) + 1
        chosen = {role: (names[:2] if names else []) for role, names in (self._models or {}).items()}
        errors = {}
        for call in self.calls:
            if call.get("error"):
                errors.setdefault(call["model"], f"{call['error']} — Google: {call.get('google_says', '')[:300]}")
        keys = {}
        for call in self.calls:
            keys[f"key{call.get('key', 1)}"] = keys.get(f"key{call.get('key', 1)}", 0) + 1
        return {"requests": len(self.calls), "by_model": models, "by_key": keys, "keys": len(self.keys),
                "exhausted": sorted(self.exhausted), "errors": errors,
                "seconds": round(sum(c["seconds"] for c in self.calls), 1), "waited_for_limits": round(self.waited),
                "models": chosen}


class _Exhausted(RuntimeError):
    pass


class _BadRequest(RuntimeError):
    pass


_CLIENT: Client | None = None


def client() -> Client | None:
    """The shared client for this process, or None when Gemini is off or has no key."""
    global _CLIENT
    if not enabled():
        return None
    if _CLIENT is None:
        try:
            _CLIENT = Client()
        except GeminiUnavailable:
            return None
    return _CLIENT


def _retry_delay(text: str) -> float | None:
    found = re.search(r'"retryDelay":\s*"(\d+(?:\.\d+)?)s"', text)
    return float(found.group(1)) if found else 30.0


def google_message(text: str) -> str:
    """Google's own words about the limit (which quota, which model, its value), for the logs."""
    try:
        error = json.loads(text).get("error", {})
    except (ValueError, AttributeError):
        return text[:400]
    parts = [str(error.get("message", ""))[:400]]
    for detail in error.get("details") or []:
        for v in detail.get("violations") or []:
            parts.append(f"{v.get('quotaId', '')} = {v.get('quotaValue', '?')} ({(v.get('quotaDimensions') or {}).get('model', '')})")
    return " | ".join(p for p in parts if p)


def quota_problem(text: str) -> tuple[float, bool, str]:
    """(seconds to wait, is it a daily / zero limit, short reason) from a 429 answer."""
    ids = re.findall(r'"quotaId":\s*"([^"]+)"', text)
    values = re.findall(r'"quotaValue":\s*"?(\d+)', text) + re.findall(r"limit:\s*(\d+)", text)
    daily = "PerDay" in text or "per day" in text.lower() or any(v == "0" for v in values)
    wait = _retry_delay(text) or 30.0
    reason = ("free limit is 0 for this model" if any(v == "0" for v in values) else
              "daily free limit used up" if daily else f"per-minute limit, retry in {wait:.0f}s")
    return wait, daily, reason + (f" [{', '.join(sorted(set(ids)))[:160]}]" if ids else "")


def _text(data: dict) -> str:
    feedback = data.get("promptFeedback") or {}
    if feedback.get("blockReason"):
        raise _BadRequest(f"blocked: {feedback['blockReason']}")
    candidates = data.get("candidates") or []
    if not candidates:
        raise _BadRequest("no answer")
    first = candidates[0]
    text = "".join(p.get("text", "") for p in (first.get("content") or {}).get("parts", []) if not p.get("thought"))
    if not text.strip():
        raise _BadRequest(f"empty answer ({first.get('finishReason')})")
    return text


def _parse_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        found = re.search(r"[\[{].*[\]}]", text, re.S)
        if found:
            try:
                return json.loads(found.group(0))
            except json.JSONDecodeError:
                pass
    raise _BadRequest(f"answer was not JSON: {text[:120]}")


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    size = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / size if size else 0.0


# ======================================================================== writer adapter

class GeminiWriter:
    """Same interface as writer.Ollama, so the writer can use either."""
    extras = True                      # also writes title options, cover words, pinned comment, hashtags
    context_tokens = 200_000

    def __init__(self, gemini: Client, role: str = "smart"):
        self.gemini, self.role = gemini, role
        self.stats: list[dict] = []

    def chat(self, system: str, user: str, schema: dict, *, temperature: float = 0.7, seed: int = 0,
             max_tokens: int = 1800) -> dict:
        started = time.time()
        reply = self.gemini.generate(self.role, [{"text": user}], system=system, schema=schema,
                                     temperature=temperature, seed=seed)
        call = self.gemini.calls[-1]
        seconds = round(time.time() - started, 1)
        self.stats.append({"model": call.get("model"), "prompt_tokens": call.get("prompt_tokens", 0), "prompt_seconds": 0.0,
                           "output_tokens": call.get("output_tokens", 0), "output_seconds": seconds,
                           "total_seconds": seconds})
        if not isinstance(reply, dict):
            raise ValueError("writer answer was not a JSON object")
        return reply


class FallbackWriter:
    """Gemini first; the local model takes over for good once no Gemini model is left, and for
    one call when Gemini refuses or fails that call."""

    def __init__(self, primary, make_backup, *, wait_ready=None):
        self.primary, self.make_backup, self.wait_ready = primary, make_backup, wait_ready
        self.backup = None
        self.stats: list[dict] = []
        self.notes: list[str] = []
        self.extras = getattr(primary, "extras", False)
        self.context_tokens = getattr(primary, "context_tokens", None)
        self._primary_ok = True

    def _local(self):
        if self.backup is None:
            if self.wait_ready:
                self.wait_ready()
            self.backup = self.make_backup()
        return self.backup

    def chat(self, system, user, schema, **kwargs):
        if self._primary_ok:
            try:
                reply = self.primary.chat(system, user, schema, **kwargs)
                self.stats.append(self.primary.stats[-1])
                return reply
            except GeminiUnavailable as exc:
                self.notes.append(f"Gemini unavailable, local writer used: {str(exc)[-400:]}")
                # Give Gemini up for good only when no model is left (one used-up model says nothing about
                # the others), the job's budget is spent or the network is down.
                client = getattr(self.primary, "gemini", None)
                left = client.chain(getattr(self.primary, "role", "smart")) if client is not None and \
                    hasattr(client, "chain") else []
                if not left or any(k in str(exc) for k in ("budget", "network")):
                    self._primary_ok = False
            except ValueError as exc:
                self.notes.append(f"Gemini answer unusable, local writer used once: {str(exc)[:120]}")
        local = self._local()
        reply = local.chat(system, user, schema, **kwargs)
        if getattr(local, "stats", None):
            self.stats.append({**local.stats[-1], "model": getattr(local, "model", "local")})
        return reply


def wait_for_ollama(base: str = "http://127.0.0.1:11434", model: str = "", timeout: float = 2400) -> None:
    """The workflow installs the local model in the background when Gemini is set up; wait for it."""
    import requests
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            names = [m["name"] for m in requests.get(base.rstrip("/") + "/api/tags", timeout=5).json().get("models", [])]
            if not model or any(n == model or n == model + ":latest" for n in names):
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(10)
    raise RuntimeError("the local writer model never became ready")


# ======================================================================== clip watching

OVERLAY_TYPES = ["title_card", "text_over_picture", "subtitles", "channel_logo", "subscribe_button", "border",
                 "picture_in_picture", "other"]
# Kept out of the Short when they cover part of the picture. Small corner logos and subtitles are not:
# the crop and our own text checks deal with those, and they often run through the whole upload.
AVOID_OVERLAYS = {"title_card", "text_over_picture", "subscribe_button", "picture_in_picture", "other"}
MAX_AVOID_SHARE = 0.4   # an "overlay" over more of the clip than this is part of the upload, not a moment to skip
KINDS = ["movie_scene", "trailer", "recap_or_review", "reaction", "fan_edit", "compilation", "behind_the_scenes",
         "interview", "other"]
WATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "right_movie": {"type": "boolean"},
        "confidence": {"type": "number"},
        "kind": {"type": "string", "enum": KINDS},
        "narrator_over_picture": {"type": "boolean"},
        "overlays": {"type": "array", "items": {"type": "object", "properties": {
            "start": {"type": "number"}, "end": {"type": "number"}, "what": {"type": "string"},
            "type": {"type": "string", "enum": OVERLAY_TYPES},
            "size": {"type": "string", "enum": ["small_corner", "large"]}},
            "required": ["start", "end", "what", "type", "size"]}},
        "moments": {"type": "array", "items": {"type": "object", "properties": {
            "start": {"type": "number"}, "end": {"type": "number"}, "what": {"type": "string"},
            "intensity": {"type": "integer"}, "story": {"type": "integer"},
            "subject_x": {"type": "number"}},
            "required": ["start", "end", "what", "intensity", "story"]}},
        "best_moment": {"type": "object", "properties": {
            "start": {"type": "number"}, "end": {"type": "number"}, "why": {"type": "string"}},
            "required": ["start", "end", "why"]},
    },
    "required": ["right_movie", "confidence", "kind", "narrator_over_picture", "overlays", "moments", "best_moment"],
}
WATCH_PROMPT = """You are screening YouTube uploads for a movie-recap channel. Watch this upload.
Movie it should be from: {movie}. Main characters: {characters}.
Answer in JSON:
- right_movie / confidence (0-1): is this footage really from that movie?
- kind: movie_scene (plain footage of the film), trailer, recap_or_review, reaction, fan_edit, compilation,
  behind_the_scenes, interview or other.
- narrator_over_picture: true if someone talks over the film who is not a character (commentary, narration).
- overlays: every stretch with text, logos, channel names, subscribe buttons, borders, picture-in-picture or
  title cards over the picture (start/end in seconds). Ordinary subtitles count too. For each give type
  (title_card, text_over_picture, subtitles, channel_logo, subscribe_button, border, picture_in_picture, other)
  and size: small_corner (a small logo or bug in a corner) or large (covers part of the picture).
- moments: the whole upload as consecutive moments of 2-8 seconds each, in order, covering it end to end.
  For each: start/end in seconds from the start of the video (numbers, not mm:ss), what (one short factual
  sentence of what is visible: who does what, objects, place; call people by appearance unless their name is
  spoken in the clip), intensity 1-10 (1 people standing still, 10 explosive action or shock),
  story 1-10 (how much this moment matters to the story or would make a viewer keep watching),
  subject_x 0-1 (horizontal position of the main action in the frame).
- best_moment: the single strongest few seconds to open a Short with, and why."""


def watch_clip(gemini: Client, video_id: str, movie: dict, *, duration: float | None = None,
               local: Path | None = None) -> dict:
    """What happens in a clip, second by second. Uses the YouTube link (nothing uploaded); if
    Google cannot open it (age-restricted, private), the local file is uploaded instead."""
    characters = ", ".join(c.get("character") or "" for c in (movie.get("cast") or [])[:8] if c.get("character"))
    prompt = WATCH_PROMPT.format(movie=f"{movie.get('title')} ({movie.get('year')})", characters=characters or "unknown")
    video: dict = {"fileData": {"fileUri": f"https://www.youtube.com/watch?v={video_id}"}}
    if duration and duration > MAX_VIDEO_SECONDS:
        video["videoMetadata"] = {"startOffset": "0s", "endOffset": f"{int(MAX_VIDEO_SECONDS)}s"}
    try:
        result = gemini.generate("light", [video, {"text": prompt}], schema=WATCH_SCHEMA, temperature=0.2,
                                 low_media=True)
        source = "youtube link"
    except GeminiUnavailable:
        if not local or not Path(local).exists() or Path(local).stat().st_size > 1_500_000_000:
            raise
        record = gemini.upload(Path(local))
        try:
            result = gemini.generate("light", [{"fileData": {"fileUri": record["uri"], "mimeType": record.get("mimeType", "video/mp4")}},
                                               {"text": prompt}], schema=WATCH_SCHEMA, temperature=0.2, low_media=True)
        finally:
            gemini.delete(record)
        source = "uploaded file"
    return clean_watch(result, duration, source)


def clean_watch(result: dict, duration: float | None, source: str = "") -> dict:
    """Clamp times, drop nonsense, sort; Gemini's times are roughly ±1 s."""
    end = float(duration or 1e9)

    def span(row):
        s, e = float(row.get("start") or 0), float(row.get("end") or 0)
        s, e = max(0.0, min(s, end)), max(0.0, min(e, end))
        return (s, e) if e > s else None

    moments = []
    for row in result.get("moments") or []:
        times = span(row)
        if not times or not str(row.get("what") or "").strip():
            continue
        moments.append({"start": round(times[0], 1), "end": round(times[1], 1), "what": str(row["what"]).strip()[:200],
                        "intensity": int(min(10, max(1, row.get("intensity") or 5))),
                        "story": int(min(10, max(1, row.get("story") or 5))),
                        **({"subject_x": round(min(1.0, max(0.0, float(row["subject_x"]))), 2)}
                           if row.get("subject_x") is not None else {})})
    overlays = []
    for row in result.get("overlays") or []:
        times = span(row)
        if times:
            overlays.append({"start": round(times[0], 1), "end": round(times[1], 1), "what": str(row.get("what", ""))[:80],
                             "type": row.get("type") if row.get("type") in OVERLAY_TYPES else "other",
                             "size": "small_corner" if row.get("size") == "small_corner" else "large"})
    best = result.get("best_moment") or {}
    best_span = span(best) if best else None
    return {"source": source, "right_movie": bool(result.get("right_movie", True)),
            "confidence": float(min(1.0, max(0.0, result.get("confidence") or 0.0))),
            "kind": result.get("kind") if result.get("kind") in KINDS else "other",
            "narrator_over_picture": bool(result.get("narrator_over_picture")),
            "overlays": sorted(overlays, key=lambda r: r["start"]),
            "moments": sorted(moments, key=lambda r: r["start"]),
            "best_moment": {"start": best_span[0], "end": best_span[1], "why": str(best.get("why", ""))[:160]}
            if best_span else None}


REJECT_KINDS = {"trailer": "trailer", "recap_or_review": "someone else's recap or review", "reaction": "reaction video",
                "fan_edit": "fan edit", "behind_the_scenes": "behind-the-scenes footage", "interview": "interview"}


def apply_watch(report: dict, watch: dict) -> dict:
    """Fold what Gemini saw into a screening report: more reasons to reject, more ranges to avoid."""
    report = dict(report)
    report["watch"] = watch
    reasons = list(report.get("reasons") or [])
    notes = list(report.get("notes") or [])
    if not watch["right_movie"] and watch["confidence"] >= 0.75:
        reasons.append("Gemini: footage is not from this movie")
    if watch["kind"] in REJECT_KINDS:
        reasons.append(f"Gemini: {REJECT_KINDS[watch['kind']]}, not a plain movie scene")
    if watch["narrator_over_picture"]:
        reasons.append("Gemini: someone talks over the film (commentary or narration)")
    avoid = [list(r) for r in report.get("avoid") or []]
    skip = [[max(0.0, r["start"] - 0.5), r["end"] + 0.5] for r in watch["overlays"]
            if r.get("type", "other") in AVOID_OVERLAYS and r.get("size", "large") == "large"]
    length = float(report.get("duration") or 0) or max([r[1] for r in skip] + [1.0])
    covered = sum(e - s for s, e in _merge(skip))
    if skip and covered > MAX_AVOID_SHARE * length:
        # Text over most of the upload is part of the upload: skipping it would leave nothing to show.
        notes.append(f"Gemini: overlays over {covered / length:.0%} of the clip; not skipped (the crop and text checks decide)")
    elif skip:
        avoid += skip
        notes.append(f"Gemini: {len(skip)} overlay stretches kept out of the Short")
    corner = [r for r in watch["overlays"] if r.get("size") == "small_corner"]
    if corner:
        notes.append(f"Gemini: small corner logo ({corner[0]['what'][:40]}) — kept out by the crop")
    report.update(reasons=reasons, notes=notes, avoid=avoid, accept=not reasons)
    return report


def _merge(spans: list[list[float]]) -> list[list[float]]:
    merged: list[list[float]] = []
    for s, e in sorted(spans):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


# ======================================================================== scene hints

def scene_hints(gemini: Client, movie: dict, limit: int = 8) -> list[str]:
    """The scenes people talk about most (Google Search), as short YouTube search phrases."""
    prompt = (f"Use Google Search. For the movie {movie.get('title')} ({movie.get('year')}), list the {limit} scenes "
              "people talk about and rewatch most (fights, reveals, famous lines, shocking moments). For each, give a "
              "2-6 word phrase someone would type on YouTube to find that scene, without the movie title. "
              'Answer only as JSON: {"scenes": ["...", "..."]}')
    text = gemini.generate("light", [{"text": prompt}], tools=[{"google_search": {}}], temperature=0.3)  # keep the scarce Flash quota for writing
    try:
        data = _parse_json(text) if isinstance(text, str) else text
    except _BadRequest as exc:
        raise GeminiUnavailable(str(exc)) from exc
    hints = []
    for phrase in data.get("scenes", []) if isinstance(data, dict) else []:
        phrase = re.sub(r"\s+", " ", str(phrase)).strip(" .\"'")
        if 2 <= len(phrase.split()) <= 8 and phrase.lower() not in (h.lower() for h in hints):
            hints.append(phrase)
    return hints[:limit]


# ======================================================================== covers

COVER_SCHEMA = {"type": "object", "properties": {
    "best": {"type": "integer"}, "second": {"type": "integer"}, "words": {"type": "string"}, "why": {"type": "string"}},
    "required": ["best", "second", "words"]}


def pick_cover(gemini: Client, images: list, title: str) -> dict:
    """Index of the strongest frame (a clear, expressive face or the key moment), a second
    different frame, and 2–4 cover words. `images` are PIL images."""
    import io
    parts: list[dict] = []
    for i, image in enumerate(images):
        small = image.copy()
        small.thumbnail((512, 512))
        buffer = io.BytesIO()
        small.convert("RGB").save(buffer, "JPEG", quality=80)
        parts += [{"text": f"Frame {i}:"}, {"inlineData": {"mimeType": "image/jpeg",
                                                         "data": base64.b64encode(buffer.getvalue()).decode()}}]
    parts.append({"text": (f"These are frames from a movie-recap Short titled \"{title}\". Pick the frame that makes the "
                           "best YouTube Shorts cover: sharp, a clear and expressive face or the key moment, readable at "
                           "phone size, no text in it. Then a clearly different second frame. Then 2-4 punchy cover words "
                           "(no spoilers, not the full title). Answer in JSON with the frame numbers.")})
    reply = gemini.generate("light", parts, schema=COVER_SCHEMA, temperature=0.2)
    best, second = int(reply.get("best", 0)), int(reply.get("second", 0))
    if not 0 <= best < len(images):
        best = 0
    if not 0 <= second < len(images) or second == best:
        second = next((i for i in range(len(images)) if i != best), best)
    words = [w for w in re.findall(r"[\w'’!?-]+", str(reply.get("words", "")))][:4]
    return {"best": best, "second": second, "words": words, "why": str(reply.get("why", ""))[:160]}


# ======================================================================== finished-Short critic

CRITIC_SCHEMA = {"type": "object", "properties": {
    "scores": {"type": "object", "properties": {k: {"type": "integer"} for k in (
        "hook", "story_clarity", "picture_matches_words", "pace", "framing", "ending", "overall")},
        "required": ["hook", "story_clarity", "picture_matches_words", "pace", "framing", "ending", "overall"]},
    "keep_watching": {"type": "boolean"},
    "problems": {"type": "array", "items": {"type": "object", "properties": {
        "second": {"type": "number"}, "what": {"type": "string"}, "fix": {"type": "string"}},
        "required": ["second", "what"]}},
    "age_restriction_risk": {"type": "string", "enum": ["low", "medium", "high"]},
    "age_reason": {"type": "string"},
    "best_part": {"type": "string"}},
    "required": ["scores", "keep_watching", "problems", "age_restriction_risk"]}
CRITIC_PROMPT = """You are a strict editor of viral movie-recap YouTube Shorts. Watch this finished Short.
Title: {title}. Narration script: {script}
Score 1-10 each: hook (would a scroller stop in the first 2 seconds?), story_clarity (easy to follow without
having seen the movie), picture_matches_words (the picture shows what the narrator is talking about),
pace (no dead moments, no confusing jumps), framing (faces and action fully visible, nothing important cut off,
captions not covering faces), ending (satisfying, loops back), overall.
keep_watching: would you watch to the end?
problems: every concrete problem with the second it happens and how to fix it (most important first, at most 8).
age_restriction_risk: would YouTube likely age-restrict this (graphic gore, sexual content, strong profanity in
the audio or captions)? low, medium or high, with age_reason. best_part: the strongest moment."""


def proxy(video: Path, folder: Path | None = None) -> Path:
    """A small 480p copy for Gemini to watch: uploads in seconds instead of timing out."""
    import subprocess
    video = Path(video)
    target = Path(folder or video.parent) / f"{video.stem}-480p.mp4"
    result = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf", "scale=-2:480,fps=30",
                             "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-c:a", "aac", "-b:a", "64k",
                             str(target)], capture_output=True)
    return target if result.returncode == 0 and target.exists() else video


def critique(gemini: Client, video: Path, title: str, script_text: str) -> dict:
    small = proxy(Path(video))
    try:
        record = gemini.upload(small)
    finally:
        if small != Path(video):
            small.unlink(missing_ok=True)
    try:
        reply = gemini.generate("smart", [
            {"fileData": {"fileUri": record["uri"], "mimeType": record.get("mimeType", "video/mp4")}},
            {"text": CRITIC_PROMPT.format(title=title, script=script_text[:4000])}], schema=CRITIC_SCHEMA, temperature=0.2)
    finally:
        gemini.delete(record)
    scores = {k: int(min(10, max(1, v or 1))) for k, v in (reply.get("scores") or {}).items()}
    problems = [{"second": round(float(p.get("second") or 0), 1), "what": str(p.get("what", ""))[:200],
                 "fix": str(p.get("fix", ""))[:200]} for p in (reply.get("problems") or [])[:8]]
    return {"scores": scores, "keep_watching": bool(reply.get("keep_watching")), "problems": problems,
            "age_restriction_risk": reply.get("age_restriction_risk") if reply.get("age_restriction_risk") in
            ("low", "medium", "high") else "low",
            "age_reason": str(reply.get("age_reason", ""))[:200], "best_part": str(reply.get("best_part", ""))[:200]}


# ======================================================================== picture check for scripts

PICTURE_SCHEMA = {"type": "object", "properties": {"problems": {"type": "array", "items": {"type": "object", "properties": {
    "sentence": {"type": "string"}, "why": {"type": "string"}}, "required": ["sentence", "why"]}}}, "required": ["problems"]}


def picture_check(gemini: Client, brief: dict, script: dict) -> list[str]:
    """Narration sentences that describe something the scene's footage does not show. Explaining
    who someone is or why something matters is fine; claiming a visible action that is not there
    is not (the viewer would hear one thing and see another)."""
    scenes = [{"scene": x["scene"], "on_screen": x.get("on_screen") or [], "role": x.get("role", ""),
               "dialogue": x.get("dialogue", [])[:12]} for x in brief.get("scenes", [])]
    if not any(x["on_screen"] for x in scenes):
        return []
    narration = [{"scene": b.get("scene"), "text": b.get("text")} for b in script.get("beats", [])
                 if b.get("kind") == "narration" and b.get("text")]
    prompt = ("Each scene below lists what its footage shows (on_screen, seconds from the scene start) and its "
              "dialogue. For the narration, list every sentence that claims a VISIBLE action or object that this "
              "scene's footage does not show (the viewer would hear it while seeing something else). Context "
              "(who someone is, why it matters, what happened earlier in one short clause) is allowed. "
              "Quote each problem sentence exactly.\nSCENES:\n" + json.dumps(scenes, ensure_ascii=False) +
              "\nNARRATION:\n" + json.dumps(narration, ensure_ascii=False))
    reply = gemini.generate("light", [{"text": prompt}], schema=PICTURE_SCHEMA, temperature=0.1)
    return [f'not on screen: "{p["sentence"][:140]}" ({p.get("why", "")[:100]})'
            for p in (reply.get("problems") or [])[:6] if p.get("sentence")]


# ======================================================================== director: which moments under which sentence

SHOTS_SCHEMA = {"type": "object", "properties": {"shots": {"type": "array", "items": {"type": "object", "properties": {
    "beat": {"type": "string"}, "moments": {"type": "array", "items": {"type": "integer"}}},
    "required": ["beat", "moments"]}}}, "required": ["shots"]}


def shot_list(gemini: Client, arc: dict, voiceover: dict) -> dict[str, list[tuple[float, float]]]:
    """For every narration sentence, the moments of its scene that show what it says, in order (clip
    seconds). The edit plays these first, so the picture matches the words."""
    scenes, keyed = [], {}
    for i, scene in enumerate(arc.get("scenes") or []):
        rows = []
        for m in scene.get("moments") or []:
            s, e = max(m["start"], scene["clip_start"]), min(m["end"], scene["clip_end"])
            if e - s >= 0.8:
                key = len(keyed)
                keyed[key] = (i, s, e)
                rows.append({"k": key, "seconds": round(e - s, 1), "what": m["what"][:140]})
        scenes.append({"scene": i, "moments": rows})
    if not keyed:
        return {}
    beats = [{"beat": b["id"], "scene": b["scene"], "seconds": round(b.get("duration") or 0, 1), "says": b.get("text", "")[:300]}
             for b in voiceover.get("beats") or [] if b.get("kind") == "narration"]
    prompt = ("You are the editor of a movie-recap Short. For every narration beat, choose the moments of ITS OWN scene "
              "to show while it is spoken, in the order to show them, adding up to about its seconds. The picture must "
              "show what the narration says at that point (the person, the action, the object). Prefer strong moments; "
              "never use a moment twice; skip moments where nothing happens.\nSCENES:\n" +
              json.dumps(scenes, ensure_ascii=False) + "\nNARRATION BEATS:\n" + json.dumps(beats, ensure_ascii=False))
    reply = gemini.generate("light", [{"text": prompt}], schema=SHOTS_SCHEMA, temperature=0.2)
    scene_of = {b["id"]: b["scene"] for b in voiceover.get("beats") or []}
    out: dict[str, list[tuple[float, float]]] = {}
    used: set[int] = set()
    for row in reply.get("shots") or []:
        beat = str(row.get("beat"))
        ranges = []
        for k in row.get("moments") or []:
            if k in keyed and k not in used and keyed[k][0] == scene_of.get(beat):
                used.add(k)
                ranges.append((keyed[k][1], keyed[k][2]))
        if ranges:
            out[beat] = ranges
    return out


# ======================================================================== critic before rendering

BOARD_SCHEMA = {"type": "object", "properties": {"beats": {"type": "array", "items": {"type": "object", "properties": {
    "beat": {"type": "string"}, "match": {"type": "integer"}, "better": {"type": "array", "items": {"type": "integer"}},
    "why": {"type": "string"}}, "required": ["beat", "match", "better"]}}}, "required": ["beats"]}


def storyboard(arc: dict, edl: dict) -> tuple[list[dict], dict[int, tuple[int, float, float]]]:
    """Per narration beat: what is said and what its shots show (from the watched moments), plus the
    numbered moments the critic may choose from instead."""
    keyed: dict[int, tuple[int, float, float]] = {}
    for i, scene in enumerate(arc.get("scenes") or []):
        for m in scene.get("moments") or []:
            s, e = max(m["start"], scene["clip_start"]), min(m["end"], scene["clip_end"])
            if e - s >= 0.8:
                keyed[len(keyed)] = (i, s, e)
    board = []
    for shot in edl.get("shots") or []:
        if shot.get("audio") == "full":
            continue
        scene_index = next((i for i, sc in enumerate(arc["scenes"]) if sc["clip_id"] == shot["clip_id"]), None)
        seen = [m["what"][:100] for m in (arc["scenes"][scene_index].get("moments") or [])
                if scene_index is not None and m["end"] > shot["start"] and m["start"] < shot["end"]]
        if board and board[-1]["beat"] == shot["beat"]:
            board[-1]["shows"] += seen
        else:
            board.append({"beat": shot["beat"], "scene": scene_index, "shows": seen})
    return board, keyed


def critique_edit(gemini: Client, arc: dict, voiceover: dict, edl: dict, keep_above: int = 6) -> dict[str, list]:
    """Before anything is rendered, a strict editor compares each sentence with what its shots show;
    for sentences scoring under `keep_above` it picks better moments of the same scene. Returns the
    replacement shot lists ({} when everything matches or nothing was watched)."""
    board, keyed = storyboard(arc, edl)
    if not keyed or not board:
        return {}
    said = {b["id"]: b.get("text", "") for b in voiceover.get("beats") or []}
    rows = [{"beat": r["beat"], "says": said.get(r["beat"], "")[:240], "shows": r["shows"][:8],
             "choices": [{"k": k, "what": f"{v[1]:.0f}-{v[2]:.0f}s"} for k, v in keyed.items() if v[0] == r["scene"]][:20]}
            for r in board]
    menu = [{"k": k, "scene": v[0], "what": next((m["what"][:110] for m in arc["scenes"][v[0]].get("moments") or []
                                                  if m["start"] <= v[1] < m["end"] + 0.01), "")} for k, v in keyed.items()]
    prompt = ("Strict editor of a movie-recap Short, before rendering. For each narration beat, score 1-10 how well "
              "what its shots show matches what is said at that moment. For any beat under "
              f"{keep_above}, list better moments (keys from the same scene, in order) that show what is said.\n"
              "BEATS:\n" + json.dumps(rows, ensure_ascii=False) + "\nMOMENTS:\n" + json.dumps(menu, ensure_ascii=False))
    reply = gemini.generate("light", [{"text": prompt}], schema=BOARD_SCHEMA, temperature=0.2)
    scene_of = {r["beat"]: r["scene"] for r in board}
    fixes: dict[str, list] = {}
    for row in reply.get("beats") or []:
        beat = str(row.get("beat"))
        if int(row.get("match") or 10) >= keep_above or beat not in scene_of:
            continue
        ranges = [(keyed[k][1], keyed[k][2]) for k in row.get("better") or [] if k in keyed and keyed[k][0] == scene_of[beat]]
        if ranges:
            fixes[beat] = ranges
    return fixes


# ======================================================================== the real pictures under every clause

SHEET_COLUMNS = 6
TILE_WIDTH = 192
MAX_FRAMES_PER_SCENE = 30   # a sheet per scene stays small enough to answer in well under a minute


def _frames(video: str, start: float, end: float, step: float, folder: Path) -> list[tuple[float, Path]]:
    """Frames every `step` seconds of [start, end] (clip clock), as small JPEGs."""
    import subprocess
    folder.mkdir(parents=True, exist_ok=True)
    pattern = folder / "f%04d.jpg"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{max(0.5, end - start):.3f}",
                    "-i", str(video), "-vf", f"fps=1/{step:.3f},scale={TILE_WIDTH}:-2", "-q:v", "5", str(pattern)],
                   capture_output=True, timeout=300)
    files = sorted(folder.glob("f*.jpg"))
    return [(round(start + step * (i + 0.5), 2), f) for i, f in enumerate(files) if start + step * (i + 0.5) <= end]


def _sheet(frames: list[tuple[float, Path]], label: str):
    """One labelled grid image: every tile shows its clip second."""
    from PIL import Image, ImageDraw
    tiles = [Image.open(path).convert("RGB") for _, path in frames]
    if not tiles:
        return None
    tw, th = tiles[0].size
    cols = min(SHEET_COLUMNS, len(tiles))
    rows = -(-len(tiles) // cols)
    sheet = Image.new("RGB", (cols * tw, rows * th + 22), (0, 0, 0))
    draw = ImageDraw.Draw(sheet)
    draw.text((4, 4), label, fill=(255, 255, 0))
    for n, ((t, _), tile) in enumerate(zip(frames, tiles)):
        x, y = (n % cols) * tw, 22 + (n // cols) * th
        sheet.paste(tile.resize((tw, th)), (x, y))
        draw.rectangle([x, y, x + 52, y + 16], fill=(0, 0, 0))
        draw.text((x + 3, y + 2), f"{t:.1f}s", fill=(255, 255, 255))
    return sheet


def frame_sheets(arc: dict, footage: dict, work: Path, *, max_frames: int = MAX_FRAMES_PER_SCENE,
                 only: int | None = None) -> list[dict]:
    """Per scene of the story: labelled contact sheets of its footage, one frame per second or so
    (longer scenes sample more sparsely). [{'scene', 'times', 'image'}]; [] when no frame could be made."""
    sheets = []
    for i, scene in enumerate(arc.get("scenes") or []):
        video = footage.get(scene["clip_id"])
        if not video or (only is not None and i != only):
            continue
        span = scene["clip_end"] - scene["clip_start"]
        step = max(1.0, span / max(1, max_frames))
        folder = Path(work) / f"scene{i}-{max_frames}"
        frames = _frames(video, scene["clip_start"], scene["clip_end"], step, folder)
        image = _sheet(frames, f"SCENE {i}: {str(scene.get('clip_title', ''))[:60]}")
        if image is not None:
            sheets.append({"scene": i, "times": [t for t, _ in frames], "image": image})
    return sheets


def _image_part(image) -> dict:
    import io
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=78)
    return {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(buffer.getvalue()).decode()}}


PICK_SCHEMA = {"type": "object", "properties": {"slots": {"type": "array", "items": {"type": "object", "properties": {
    "id": {"type": "string"}, "start": {"type": "number"}, "end": {"type": "number"},
    "match": {"type": "integer"}, "shown": {"type": "boolean"}},
    "required": ["id", "start", "end", "match", "shown"]}}}, "required": ["slots"]}


def slot_rows(arc: dict, voiceover: dict, slots: dict[str, list[dict]], only: set | None = None) -> list[dict]:
    """The clauses to place: id 'beat#k', its scene, its seconds and its words."""
    scene_of = {b["id"]: b.get("scene") for b in voiceover.get("beats") or []}
    rows = []
    for beat_id, beat_slots in slots.items():
        for k, slot in enumerate(beat_slots):
            sid = f"{beat_id}#{k}"
            if only is None or sid in only:
                rows.append({"id": sid, "scene": scene_of.get(beat_id), "seconds": round(slot["end"] - slot["start"], 1),
                             "says": slot["text"][:200]})
    return rows


def pick_frames(gemini: Client, arc: dict, voiceover: dict, slots: dict[str, list[dict]], sheets: list[dict], *,
                only: set | None = None, avoid: dict | None = None) -> dict[str, dict]:
    """Gemini looks at the contact sheets and chooses, for every clause, the seconds of its scene that show
    what is said. {slot id: {'start', 'end', 'match', 'shown'}} in clip seconds, each stretch as long as its
    clause (shorter only when the scene ends). `avoid`: earlier choices that scored low."""
    rows = slot_rows(arc, voiceover, slots, only)
    have = {s["scene"] for s in sheets}
    rows = [r for r in rows if r["scene"] in have]
    if not rows:
        return {}
    parts: list[dict] = []
    for s in sheets:
        parts += [{"text": f"Scene {s['scene']} contact sheet (each tile is labelled with its clip second):"},
                  _image_part(s["image"])]
    note = ""
    if avoid:
        note = ("\nThese earlier choices did NOT show what was said; choose different seconds for them: " +
                json.dumps({k: [round(v["start"], 1), round(v["end"], 1)] for k, v in avoid.items()}))
    parts.append({"text": (
        "You are the editor of a movie-recap Short. Each clause of narration below is spoken over footage of ITS OWN "
        "scene. Looking at the contact sheets, choose for every clause the stretch of its scene (start and end in "
        "clip seconds, read from the tile labels) that SHOWS what the clause says: the person, the action, the "
        "object. The stretch should last about the clause's seconds. Within a scene, clauses usually move forward in "
        "time; never give two clauses the same seconds unless nothing else fits. match, strictly: 10 = the named "
        "person AND the action or object are on screen; 6 = the right person doing something else; 3 = same scene, "
        "unrelated moment; 1 = nothing related. Most clauses are NOT 10. shown: false when nothing in the scene "
        "shows it (then pick the closest stretch)." + note +
        "\nCLAUSES:\n" + json.dumps(rows, ensure_ascii=False))})
    reply = gemini.generate("smart", parts, schema=PICK_SCHEMA, temperature=0.2, low_media=True)
    bounds = {i: (sc["clip_start"], sc["clip_end"]) for i, sc in enumerate(arc.get("scenes") or [])}
    want = {r["id"]: r for r in rows}
    out: dict[str, dict] = {}
    for row in reply.get("slots") or []:
        sid = str(row.get("id"))
        if sid not in want:
            continue
        lo, hi = bounds.get(want[sid]["scene"], (0.0, 0.0))
        try:
            start, end = float(row.get("start")), float(row.get("end"))
        except (TypeError, ValueError):
            continue
        start = min(max(start, lo), hi)
        length = want[sid]["seconds"]
        if not math.isfinite(start) or hi - start < 0.5:
            continue
        end = min(hi, start + length)  # as long as the clause (shorter only where the scene ends)
        shown = row.get("shown") is not False
        match = int(row.get("match") or 0)
        out[sid] = {"start": round(start, 2), "end": round(end, 2),
                    "match": match if shown else min(match, 3),  # nothing shows it: it cannot match well
                    "shown": shown}
    return out


def picks_to_director(picks: dict[str, dict], slots: dict[str, list[dict]]) -> dict[str, list[tuple[float, float]]]:
    """Per beat, its clauses' stretches in clause order (what `edit.build_edl` plays first)."""
    out: dict[str, list[tuple[float, float]]] = {}
    for beat_id, beat_slots in slots.items():
        ranges = [(picks[f"{beat_id}#{k}"]["start"], picks[f"{beat_id}#{k}"]["end"])
                  for k in range(len(beat_slots)) if f"{beat_id}#{k}" in picks]
        if len(ranges) == len(beat_slots):  # all or nothing: a partial list would shift the cuts
            out[beat_id] = ranges
    return out


CHECK_SCHEMA_CUTS = {"type": "object", "properties": {"slots": {"type": "array", "items": {"type": "object", "properties": {
    "id": {"type": "string"}, "sees": {"type": "string"}, "match": {"type": "integer"}, "problem": {"type": "string"}},
    "required": ["id", "sees", "match"]}}}, "required": ["slots"]}


def check_cuts(gemini: Client, voiceover: dict, slots: dict[str, list[dict]], edl: dict, footage: dict,
               work: Path) -> dict[str, dict]:
    """Before rendering: the middle frame of every shot under each clause, judged against the clause's words.
    {slot id: {'match', 'problem'}}."""
    starts = {b["id"]: b["timeline_start"] for b in voiceover.get("beats") or []}
    frames, labels = [], []
    folder = Path(work) / "check"
    for n, shot in enumerate(edl.get("shots") or []):
        if shot.get("audio") == "full" or shot.get("beat") not in slots:
            continue
        at = shot["timeline_start"] + shot["duration"] / 2 - starts[shot["beat"]]
        k = next((i for i, s in enumerate(slots[shot["beat"]]) if s["start"] - 0.01 <= at < s["end"] + 0.01), None)
        source = shot.get("source") or footage.get(shot["clip_id"])
        if k is None or not source:
            continue
        middle = (shot["start"] + shot["end"]) / 2
        got = _frames(source, middle - 0.25, middle + 0.25, 0.5, folder / f"shot{n}")
        if got:
            frames.append((float(n), got[0][1]))
            labels.append((f"{shot['beat']}#{k}", n))
    if not frames:
        return {}
    sheet = _sheet(frames, "SHOTS (tile label = shot number)")
    by_slot: dict[str, list[int]] = {}
    for sid, n in labels:
        by_slot.setdefault(sid, []).append(n)
    rows = [{"id": sid, "says": slots[sid.split("#")[0]][int(sid.split("#")[1])]["text"][:200], "shots": shots}
            for sid, shots in by_slot.items()]
    reply = gemini.generate("light", [
        {"text": "Shots of a movie-recap Short, before rendering (tile label = shot number):"}, _image_part(sheet),
        {"text": "For every clause of narration below: first write in 'sees' what its shots actually show (at most "
                 "8 words, only what is visible). Then score, strictly against what you wrote: 10 = the named person "
                 "AND the action or object are on screen; 6 = the right person doing something else; 3 = same scene, "
                 "unrelated moment; 1 = nothing related. Most clauses are NOT 10. problem: what is wrong, if anything."
                 "\nCLAUSES:\n" +
                 json.dumps(rows, ensure_ascii=False)}], schema=CHECK_SCHEMA_CUTS, temperature=0.1, low_media=True)
    known = set(by_slot)
    return {str(r.get("id")): {"match": int(r.get("match") or 0), "sees": str(r.get("sees") or "")[:80],
                               "problem": str(r.get("problem") or "")[:160]}
            for r in reply.get("slots") or [] if str(r.get("id")) in known}
