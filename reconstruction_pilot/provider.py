"""Native Anthropic REST calls with no implicit generation retries."""

from dataclasses import dataclass
import json
import os
import re
import urllib.error
import urllib.request

from .study import schema_for


class ProviderError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.http_status = status


def post_json(url, body, headers, timeout):
    request = urllib.request.Request(url, json.dumps(body).encode(),
                                    {"Content-Type":"application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        # The server error body is useful for debugging. Never include headers or keys.
        try:
            payload = json.loads(exc.read(8192))
            detail = payload.get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            detail = ""
        key = headers.get("x-api-key", "")
        if key:
            detail = str(detail).replace(key, "[REDACTED]")
        raise ProviderError(f"HTTP {exc.code}: {str(detail)[:1000]}", exc.code) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ProviderError(f"Transport/JSON error: {type(exc).__name__}") from None


def parse_output(text, kind):
    """One terminal JSON object; tolerate prose/fences, reject ambiguity and duplicate keys."""
    start = re.search(r"(?m)^[ \t]*(?=\{|```)", text.strip())
    if start is None:
        return None
    text = text.strip()
    if any(marker in text[:start.start()] for marker in ("{", "}", "```")):
        return None
    text = text[start.start():].strip()
    fence = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    try:
        result = json.loads(text, object_pairs_hook=unique,
                            parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
    except (ValueError, TypeError):
        return None
    if not isinstance(result, dict):
        return None
    if kind == "solve":
        ok = (set(result) == {"reason","answer"} and isinstance(result["reason"],str)
              and type(result["answer"]) is int)
    elif kind == "grade":
        ok = (set(result) == {"reason","verdict"} and isinstance(result["reason"],str)
              and result["verdict"] in ("valid","invalid"))
    elif kind == "probe":
        ok = set(result) == set("ABC") and all(
            isinstance(v,dict) and set(v)=={"present","quote"}
            and type(v["present"]) is bool and isinstance(v["quote"],str) for v in result.values())
    else:
        raise ValueError("Unknown schema")
    return result if ok else None


def token_int(value):
    return value if type(value) is int and value >= 0 else None


@dataclass
class Result:
    status: str
    parsed: dict | None
    text: str
    input_tokens: int | None
    output_tokens: int | None
    raw: dict
    stop: str | None = None
    cache_tokens: int = 0


def decode(raw, kind):
    try:
        text = "".join(b.get("text", "") for b in raw.get("content", []) if b.get("type")=="text")
        stop = raw.get("stop_reason")
        usage = raw.get("usage", {})
        inp, out = token_int(usage.get("input_tokens")), token_int(usage.get("output_tokens"))
        cache = sum(token_int(usage.get(k,0)) or 0 for k in ("cache_creation_input_tokens", "cache_read_input_tokens"))
        status = {"end_turn":"valid", "max_tokens":"truncated", "refusal":"refusal"}.get(stop,"incomplete_response")
        parsed = parse_output(text, kind) if status=="valid" else None
        if status=="valid" and parsed is None:
            status = "invalid_format"
        return Result(status, parsed, text, inp, out, raw, stop, cache)
    except (AttributeError, TypeError, KeyError):
        return Result("malformed_response", None, "", None, None, raw)


class Anthropic:
    def __init__(self, config, transport=post_json):
        self.config, self.transport = config, transport
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("Set ANTHROPIC_API_KEY before using --execute. See README.md.")
        self.headers = {"x-api-key":key, "anthropic-version":"2023-06-01"}
        self.base = "https://api.anthropic.com/v1/messages"

    def body(self, messages, kind, max_tokens=None):
        body = dict(model=self.config["model"], messages=messages, thinking={"type":"adaptive"},
                    output_config={"effort":self.config["effort"],
                                   "format":{"type":"json_schema", "schema":schema_for(kind)}})
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        return body

    def count(self, messages, kind):
        raw = self.transport(self.base+"/count_tokens", self.body(messages,kind),
                             self.headers,self.config["timeout_seconds"])
        count = token_int(raw.get("input_tokens")) if isinstance(raw,dict) else None
        if count is None:
            raise ProviderError("Token counter returned no count; no generation was sent")
        return count

    def generate(self, messages, kind, max_tokens):
        raw = self.transport(self.base, self.body(messages,kind,max_tokens),
                             self.headers,self.config["timeout_seconds"])
        return decode(raw,kind)
