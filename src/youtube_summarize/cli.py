"""CLI entrypoint for summarizing a single YouTube video."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable
from urllib.parse import parse_qs, urlparse

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
    ap.add_argument("video_url", nargs="?", help="Public YouTube video URL.")
    ap.add_argument("--input-file", help="Path to a .txt file with one YouTube URL or ID per line.")
    ap.add_argument("--title", default="", help="Optional title override.")
    ap.add_argument("--channel", default="", help="Optional channel override.")
    ap.add_argument("--upload-date", default="", help="Optional upload date override (YYYY-MM-DD).")
    ap.add_argument("--model", default="gemini-3-flash-preview", help="Gemini model name.")
    ap.add_argument("--out", default="-", help="Output path for JSON (default: stdout).")
    ap.add_argument("--outdir", help="Output directory for batch mode (writes one file per video).")
    ap.add_argument("--schema", help="Path to JSON Schema file.")
    ap.add_argument("--schema-json", help="Inline JSON Schema string.")
    ap.add_argument("--prompt", help="Prompt override.")
    ap.add_argument("--prompt-file", help="Path to a prompt text file.")
    return ap.parse_args()


def normalize_video_url(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        if parsed.netloc in {"youtu.be", "www.youtu.be"}:
            video_id = parsed.path.lstrip("/")
            return f"https://www.youtube.com/watch?v={video_id}"
        if parsed.netloc in {"www.youtube.com", "youtube.com"}:
            qs = parse_qs(parsed.query)
            video_id = qs.get("v", [""])[0]
            if video_id:
                return f"https://www.youtube.com/watch?v={video_id}"
        return raw
    return f"https://www.youtube.com/watch?v={raw}"


def extract_video_id(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        if parsed.netloc in {"youtu.be", "www.youtu.be"}:
            return parsed.path.lstrip("/")
        if parsed.netloc in {"www.youtube.com", "youtube.com"}:
            qs = parse_qs(parsed.query)
            return qs.get("v", [""])[0]
    return raw


def load_inputs(args: argparse.Namespace) -> Iterable[str]:
    if args.input_file:
        path = Path(args.input_file)
        lines = path.read_text(encoding="utf-8").splitlines()
        return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    if args.video_url:
        return [args.video_url]
    return []

def render_progress(index: int, total: int, video_id: str) -> None:
    if total <= 1:
        return
    width = 24
    filled = int((index / total) * width)
    bar = "#" * filled + "-" * (width - filled)
    msg = f"[{index}/{total}] [{bar}] {video_id}"
    print(msg, file=sys.stderr)


def main() -> None:
    args = parse_args()
    inputs = load_inputs(args)
    if not inputs:
        raise SystemExit("Provide a video URL/ID or --input-file.")
    if args.input_file and not args.outdir and args.out == "-":
        raise SystemExit("Batch mode requires --outdir to write results per video.")

    api_key = load_api_key()
    client = genai.Client(api_key=api_key)

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
    base_prompt = base_prompt.strip()
    prompt_template = SHARED_VIDEO_PROMPT if base_prompt == SHARED_VIDEO_PROMPT else base_prompt

    def render_prompt(meta: Dict[str, str]) -> str:
        return f"""{prompt_template}

VIDEO METADATA (use exactly):
- video_url: {meta["video_url"]}
- title: {meta.get("title","")}
- channel: {meta.get("channel","")}
- upload_date: {meta.get("upload_date","")}

Return ONLY valid JSON that matches the provided schema.
"""

    outdir = Path(args.outdir) if args.outdir else None
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)

    total = len(inputs)
    for idx, raw_input in enumerate(inputs, start=1):
        video_url = normalize_video_url(raw_input)
        meta = {
            "video_url": video_url,
            "title": args.title,
            "channel": args.channel,
            "upload_date": args.upload_date,
        }
        video_id = extract_video_id(video_url) or f"video_{idx}"
        render_progress(idx, total, video_id)
        prompt = render_prompt(meta)
        payload = summarize_custom(client=client, model=args.model, prompt=prompt, meta=meta, schema=schema)

        if outdir:
            out_path = outdir / f"{video_id}.json"
            out_path.write_text(payload, encoding="utf-8")
            continue

        if args.out == "-":
            print(payload)
            continue

        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        break


if __name__ == "__main__":
    main()
