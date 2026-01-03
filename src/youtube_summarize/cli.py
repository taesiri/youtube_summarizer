"""CLI entrypoint for summarizing a single YouTube video."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

from google import genai

from youtube_summarize.gemini import load_api_key, summarize_custom
from youtube_summarize.presets import DEFAULT_PRESET_ID, DEFAULT_PROMPT, load_preset_safe
from youtube_summarize.prompts import SHARED_VIDEO_PROMPT


def build_prompt(meta: Dict[str, str]) -> str:
    return f"""{SHARED_VIDEO_PROMPT}

VIDEO METADATA (use exactly):
- video_url: {meta["video_url"]}
- title: {meta.get("title","")}
- channel: {meta.get("channel","")}
- upload_date: {meta.get("upload_date","")}

Now extract:
- who the person is (if stated)
- what they built (products)
- success/failure/mixed/unknown with reasons
- metrics (spend/revenue/users/etc) ONLY if explicitly stated
- competitors ONLY if explicitly stated
- missing_info list of important fields NOT provided
"""


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Summarize a YouTube video using a custom JSON Schema.")
    ap.add_argument("video_url", help="Public YouTube video URL.")
    ap.add_argument("--title", default="", help="Optional title override.")
    ap.add_argument("--channel", default="", help="Optional channel override.")
    ap.add_argument("--upload-date", default="", help="Optional upload date override (YYYY-MM-DD).")
    ap.add_argument("--model", default="gemini-3-flash-preview", help="Gemini model name.")
    ap.add_argument("--out", default="-", help="Output path for JSON (default: stdout).")
    ap.add_argument("--schema", help="Path to JSON Schema file.")
    ap.add_argument("--schema-json", help="Inline JSON Schema string.")
    ap.add_argument("--prompt", help="Prompt override.")
    ap.add_argument("--prompt-file", help="Path to a prompt text file.")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    api_key = load_api_key()
    client = genai.Client(api_key=api_key)

    meta = {
        "video_url": args.video_url,
        "title": args.title,
        "channel": args.channel,
        "upload_date": args.upload_date,
    }
    preset_prompt = None
    if args.schema_json:
        schema = json.loads(args.schema_json)
    elif args.schema:
        payload = json.loads(Path(args.schema).read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "schema" in payload:
            preset_prompt = payload.get("prompt")
            schema = payload.get("schema")
        else:
            schema = payload
    else:
        preset = load_preset_safe(DEFAULT_PRESET_ID) or {}
        preset_prompt = preset.get("prompt")
        schema = preset.get("schema") or {
            "type": "object",
            "properties": {"summary": {"type": "string"}, "keyword": {"type": "array", "items": {"type": "string"}}},
            "required": ["summary", "keyword"],
        }

    if args.prompt_file:
        base_prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    elif args.prompt:
        base_prompt = args.prompt
    elif preset_prompt:
        base_prompt = preset_prompt
    else:
        base_prompt = DEFAULT_PROMPT
    prompt = build_prompt(meta) if base_prompt == SHARED_VIDEO_PROMPT else f"""{base_prompt}

VIDEO METADATA (use exactly):
- video_url: {meta["video_url"]}
- title: {meta.get("title","")}
- channel: {meta.get("channel","")}
- upload_date: {meta.get("upload_date","")}

Return ONLY valid JSON that matches the provided schema.
"""

    payload = summarize_custom(client=client, model=args.model, prompt=prompt, meta=meta, schema=schema)

    if args.out == "-":
        print(payload)
        return

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    main()
