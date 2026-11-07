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


class GeminiUnavailable(RuntimeError):
    """Gemini cannot answer this request; use the local fallback."""


def api_key() -> str:
    return (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()


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
    """Small REST client: JSON output, YouTube links, file uploads, embeddings, retries, budget."""

    def __init__(self, key: str | None = None, *, session=None, sleep=time.sleep, max_calls: int | None = None):
        import requests
        self.key = key or api_key()
        if not self.key:
            raise GeminiUnavailable("no GEMINI_API_KEY")
        self.session = session or requests.Session()
        self.sleep = sleep
        self.max_calls = max_calls if max_calls is not None else int(os.environ.get("SHORTS_GEMINI_MAX_CALLS", "80"))
        self.calls: list[dict] = []
        self.exhausted: set[str] = set()      # no quota left today (or not available) for this key
        self.cooldown: dict[str, float] = {}   # per-minute limit hit: usable again after this time
        self.good: dict[str, str] = {}         # the model that last answered, per role: tried first
        self.last_call = 0.0
        self.waited = 0.0                      # seconds spent waiting for per-minute limits in this job
        self._request_wait = REQUEST_WAIT
        self.state_file = Path(os.environ["SHORTS_GEMINI_STATE"]) if os.environ.get("SHORTS_GEMINI_STATE") else None
        self._load_state()
        self._models: dict[str, list[str]] | None = None

    # ------------------------------------------------------------------ shared state
    @staticmethod
    def _quota_day() -> str:
        """Google resets daily limits at midnight Pacific time (UTC-8, or UTC-7 in summer)."""
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc) - timedelta(hours=8)).strftime("%Y-%m-%d")

    def _load_state(self) -> None:
        """Models an earlier job already found used up today are skipped without spending a request."""
        try:
            data = json.loads(self.state_file.read_text()) if self.state_file and self.state_file.exists() else {}
        except (OSError, ValueError):
            data = {}
        if data.get("day") == self._quota_day():
            self.exhausted |= set(data.get("exhausted") or [])

    def _save_state(self) -> None:
        if not self.state_file:
            return
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps({"day": self._quota_day(), "exhausted": sorted(self.exhausted)}))
        except OSError:
            pass

    # ------------------------------------------------------------------ plumbing
    def _http(self, method: str, url: str, **kwargs):
        headers = {"x-goog-api-key": self.key, **kwargs.pop("headers", {})}
        try:
            return self.session.request(method, url, headers=headers, timeout=kwargs.pop("timeout", 300), **kwargs)
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
        """Models to try for a role: its own models, then (for smart) the lighter ones."""
        models = self.models()
        names = list(models.get(role, []))
        if role == "smart":
            names += models.get("light", [])
        elif role == "light":
            names += models.get("smart", [])
        if self.good.get(role) in names:
            names.insert(0, self.good[role])
        now = time.time()
        return [n for n in dict.fromkeys(names) if n not in self.exhausted and self.cooldown.get(n, 0) <= now]

    def _post(self, model: str, method: str, body: dict) -> dict:
        """One request with retries. Daily quota → model marked exhausted; per-minute → wait."""
        if len(self.calls) >= self.max_calls:
            raise GeminiUnavailable(f"this job's Gemini budget ({self.max_calls} requests) is spent")
        minute_waits = 0
        for attempt in range(6):
            # Space requests out (all of this job's calls share the key's per-minute limit with the other jobs).
            gap = MIN_GAP - (time.time() - self.last_call)
            if gap > 0:
                self.sleep(gap)
            started = self.last_call = time.time()
            reply = self._http("POST", f"{API}/v1beta/models/{model}:{method}", json=body)
            row = {"model": model, "method": method, "status": reply.status_code, "seconds": round(time.time() - started, 1)}
            self.calls.append(row)
            if reply.status_code == 200:
                data = reply.json()
                usage = data.get("usageMetadata") or {}
                row.update(prompt_tokens=usage.get("promptTokenCount", 0), output_tokens=usage.get("candidatesTokenCount", 0))
                return data
            text = reply.text[:4000]
            if reply.status_code == 429:
                wait, daily, why = quota_problem(text)
                row["error"], row["google_says"] = why, google_message(text)
                print(f"[gemini] {model}: {why} — Google: {row['google_says'][:300]}", file=sys.stderr, flush=True)
                if daily:  # nothing left today for this key on this model: never ask it again
                    self.exhausted.add(model)
                    self._save_state()
                    raise _Exhausted(f"{model}: {why}")
                pause = max(wait, MINUTE_WAIT) + 1
                if minute_waits < MINUTE_RETRIES and pause <= self._request_wait and self.waited + pause <= JOB_WAIT:
                    # Per-minute limit: a full minute guarantees a fresh window; then the same model again.
                    # Bounded per answer and per job, so limits can never stall a run for long.
                    minute_waits += 1
                    self._request_wait -= pause
                    self.waited += pause
                    self.sleep(pause)
                    continue
                self.cooldown[model] = time.time() + max(wait, MINUTE_WAIT)
                raise _Exhausted(f"{model}: {why}")
            if reply.status_code in (500, 502, 503, 504) and attempt < 3:
                self.sleep(4 * 2 ** attempt)
                continue
            if reply.status_code == 404:
                self.exhausted.add(model)
                raise _Exhausted(f"{model}: not available ({text[:160]})")
            raise _BadRequest(f"{model}: HTTP {reply.status_code} {text[:300]}")
        raise _Exhausted(f"{model}: no answer after retries")

    # ------------------------------------------------------------------ generation
    def generate(self, role: str, parts: list[dict], *, system: str | None = None, schema: dict | None = None,
                 temperature: float = 0.4, seed: int | None = None, tools: list | None = None,
                 low_media: bool = False) -> dict | str:
        """Text (or parsed JSON when `schema` is given) from the best model still available."""
        self._request_wait = REQUEST_WAIT
        for round_ in range(2):
            try:
                return self._generate(role, parts, system=system, schema=schema, temperature=temperature, seed=seed,
                                      tools=tools, low_media=low_media)
            except GeminiUnavailable:
                # Every model is only pausing for its per-minute limit: wait for the first one, once.
                waiting = [t for m, t in self.cooldown.items() if m not in self.exhausted and t > time.time()]
                pause = (min(waiting) - time.time() + 1) if waiting else 0
                if round_ or not waiting or pause > min(MAX_WAIT, self._request_wait) or self.waited + pause > JOB_WAIT \
                        or self.chain(role):
                    raise
                self.waited += pause
                self.sleep(pause)
        raise GeminiUnavailable("no Gemini model answered")

    def _generate(self, role, parts, *, system, schema, temperature, seed, tools, low_media):
        errors = []
        for model in self.chain(role)[:MAX_MODELS_PER_REQUEST]:
            config: dict = {"temperature": temperature}
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
                text = _text(data)
                self.calls[-1]["role"] = role
                self.good[role] = model
                return _parse_json(text) if schema is not None else text
            except (_Exhausted, _BadRequest) as exc:
                errors.append(str(exc)[:200])
                continue
        raise GeminiUnavailable("; ".join(errors) or f"no Gemini model for {role}")

    def upload(self, path: Path, mime: str = "video/mp4", wait: float = 300) -> dict:
        """Files API (free, kept 48 h): returns the file record once it is ready to use."""
        path = Path(path)
        start = self._http("POST", f"{API}/upload/v1beta/files", headers={
            "X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(path.stat().st_size),
            "X-Goog-Upload-Header-Content-Type": mime, "Content-Type": "application/json"},
            json={"file": {"display_name": path.name[:100]}})
        url = start.headers.get("x-goog-upload-url") or start.headers.get("X-Goog-Upload-URL")
        if start.status_code != 200 or not url:
            raise GeminiUnavailable(f"upload start: HTTP {start.status_code} {start.text[:160]}")
        with open(path, "rb") as handle:
            done = self._http("POST", url, headers={"X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize",
                                                    "Content-Length": str(path.stat().st_size)}, data=handle, timeout=900)
        if done.status_code != 200:
            raise GeminiUnavailable(f"upload: HTTP {done.status_code} {done.text[:160]}")
        record = done.json().get("file", {})
        deadline = time.time() + wait
        while record.get("state") == "PROCESSING" and time.time() < deadline:
            self.sleep(5)
            reply = self._http("GET", f"{API}/v1beta/{record['name']}")
            record = reply.json() if reply.status_code == 200 else record
        if record.get("state") not in (None, "ACTIVE"):
            raise GeminiUnavailable(f"uploaded file not usable: {record.get('state')}")
        return record

    def delete(self, record: dict) -> None:
        try:
            self._http("DELETE", f"{API}/v1beta/{record['name']}")
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
        return {"requests": len(self.calls), "by_model": models, "exhausted": sorted(self.exhausted), "errors": errors,
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
    """Gemini first; the local model takes over for good once Gemini is out of quota, and for
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
                self.notes.append(f"Gemini unavailable, local writer used: {str(exc)[:160]}")
                if any(k in str(exc) for k in ("daily", "limit is 0", "budget", "no Gemini model", "network")):
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


def critique(gemini: Client, video: Path, title: str, script_text: str) -> dict:
    record = gemini.upload(Path(video))
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
