"""Gemini client helpers."""

from __future__ import annotations

import json
import os
import random
import time
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

from youtube_summarize.schemas import VideoExtraction


def load_api_key() -> str:
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY (or GOOGLE_API_KEY) in your environment or .env file.")
    return api_key


def backoff_sleep(attempt: int, base: float = 1.0, cap: float = 20.0) -> None:
    delay = min(cap, base * (2**attempt))
    delay *= 0.7 + random.random() * 0.6
    time.sleep(delay)


def gemini_json(
    client: genai.Client,
    model: str,
    schema: Dict[str, Any],
    contents: types.Content,
    thinking_level: Optional[str] = None,
    max_retries: int = 6,
) -> str:
    cfg = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=schema,
        thinking_config=types.ThinkingConfig(thinking_level=thinking_level) if thinking_level else None,
    )

    last_err: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            resp = client.models.generate_content(model=model, contents=contents, config=cfg)
            return resp.text
        except Exception as exc:
            last_err = exc
            backoff_sleep(attempt)

    raise RuntimeError(f"Gemini failed after retries: {last_err!r}")


def summarize_video(
    client: genai.Client,
    model: str,
    prompt: str,
    meta: Dict[str, str],
    thinking_level: Optional[str] = "low",
) -> VideoExtraction:
    contents = types.Content(
        parts=[
            types.Part(file_data=types.FileData(file_uri=meta["video_url"])),
            types.Part(text=prompt),
        ]
    )

    raw = gemini_json(
        client=client,
        model=model,
        schema=VideoExtraction.model_json_schema(),
        contents=contents,
        thinking_level=thinking_level,
    )
    return VideoExtraction.model_validate_json(raw)


def summarize_custom(
    client: genai.Client,
    model: str,
    prompt: str,
    meta: Dict[str, str],
    schema: Dict[str, Any],
    thinking_level: Optional[str] = "low",
) -> str:
    contents = types.Content(
        parts=[
            types.Part(file_data=types.FileData(file_uri=meta["video_url"])),
            types.Part(text=prompt),
        ]
    )

    return gemini_json(
        client=client,
        model=model,
        schema=schema,
        contents=contents,
        thinking_level=thinking_level,
    )


def extraction_to_json(extraction: VideoExtraction) -> str:
    return json.dumps(extraction.model_dump(), indent=2)


def infer_schema_from_prompt(
    client: genai.Client,
    model: str,
    prompt_text: str,
    thinking_level: Optional[str] = "low",
) -> Dict[str, Any]:
    instruction = f"""You are generating a JSON Schema for a structured summary.

Use the user's prompt as guidance and return ONLY a JSON Schema object:
- Must be a single JSON object with type="object".
- Use properties with string/number/boolean/array/object types.
- For arrays, default items to string unless the prompt implies objects.
- Keep nesting to one level deep.
- Include a required list for fields that are essential.

User prompt:
{prompt_text}
"""

    contents = types.Content(parts=[types.Part(text=instruction)])
    raw = gemini_json(
        client=client,
        model=model,
        schema={"type": "object"},
        contents=contents,
        thinking_level=thinking_level,
    )
    return json.loads(raw)
