"""CLI entrypoint for summarizing a single YouTube video."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict

from google import genai

from youtube_summarize.gemini import extraction_to_json, load_api_key, summarize_video
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
    ap = argparse.ArgumentParser(description="Summarize a YouTube video into a fixed structured JSON format.")
    ap.add_argument("video_url", help="Public YouTube video URL.")
    ap.add_argument("--title", default="", help="Optional title override.")
    ap.add_argument("--channel", default="", help="Optional channel override.")
    ap.add_argument("--upload-date", default="", help="Optional upload date override (YYYY-MM-DD).")
    ap.add_argument("--model", default="gemini-3-flash-preview", help="Gemini model name.")
    ap.add_argument("--out", default="-", help="Output path for JSON (default: stdout).")
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
    prompt = build_prompt(meta)

    extraction = summarize_video(client=client, model=args.model, prompt=prompt, meta=meta)
    payload = extraction_to_json(extraction)

    if args.out == "-":
        print(payload)
        return

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    main()
