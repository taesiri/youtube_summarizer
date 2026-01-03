Got it — you want startup case-study extraction across a whole channel: what they built, whether it worked, traction/financials/users/competitors when explicitly mentioned, and otherwise a clean “not stated”.

The good news: Gemini can take public YouTube URLs directly (no downloading needed)  ￼, and you can enforce strict JSON Schema output  ￼. We’ll keep yt-dlp only for “list all videos” (still no YouTube API). --flat-playlist exists specifically to list playlist entries without fully extracting videos.  ￼

Below is a complete setup: shared prompt + structured schema + full Python script.

⸻

Shared prompt (use for every video)

This is designed to prevent hallucinated metrics:

You are extracting structured startup case-study facts from a YouTube video.

HARD RULES:
- Only extract facts that are explicitly stated or shown in the video.
- Do NOT infer numbers (revenue, users, spend, funding, etc.). If not stated, set the field to null and add it to missing_info.
- If a figure is approximate ("~", "about", "around"), keep it and mark confidence="medium".
- If a figure is unclear/ambiguous, set value=null and explain in notes + missing_info.
- Success/failure classification:
  - "success" only if the video clearly claims meaningful success (e.g., profitable, significant revenue/users, acquisition, strong growth).
  - "failure" only if the video clearly states it failed, shut down, ran out of money, or couldn’t find product-market fit.
  - Otherwise use "mixed" or "unknown" with explanation.
- Competitors: only include competitors explicitly mentioned.

EVIDENCE:
- For every important claim (metrics, success/failure, competitors, key decisions), include at least one evidence item with a timestamp MM:SS and a short snippet (<= 20 words).
- If you cannot reliably provide timestamps, use "N/A" and note why in limitations.

OUTPUT:
- Return ONLY valid JSON matching the provided schema.


⸻

A schema that fits your use case

Instead of many rigid numeric fields (which models sometimes struggle with), we use a flexible metrics[] array with explicit type + value + unit + timeframe + evidence, and we allow null values.

Key behaviors:
	•	Metrics not stated → absent (or present with value: null, your choice; below we use missing_info to list what’s missing).
	•	Outcome is an enum: success | failure | mixed | unknown
	•	Every “important” extraction includes evidence snippets.

⸻

Full working Python (no YouTube API, no downloading videos)

Install

pip install --upgrade google-genai pydantic yt-dlp
export GEMINI_API_KEY="YOUR_GEMINI_KEY"

Script: startup_channel_summarizer.py

import argparse
import json
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

import yt_dlp
from pydantic import BaseModel, Field

from google import genai
from google.genai import types


# -------------------------
# Shared prompt for ALL videos
# -------------------------
SHARED_VIDEO_PROMPT = """You are extracting structured startup case-study facts from a YouTube video.

HARD RULES:
- Only extract facts that are explicitly stated or shown in the video.
- Do NOT infer numbers (revenue, users, spend, funding, etc.). If not stated, set the field to null and add it to missing_info.
- If a figure is approximate ("~", "about", "around"), keep it and mark confidence="medium".
- If a figure is unclear/ambiguous, set value=null and explain in notes + missing_info.
- Success/failure classification:
  - "success" only if the video clearly claims meaningful success (e.g., profitable, significant revenue/users, acquisition, strong growth).
  - "failure" only if the video clearly states it failed, shut down, ran out of money, or couldn’t find product-market fit.
  - Otherwise use "mixed" or "unknown" with explanation.
- Competitors: only include competitors explicitly mentioned.

EVIDENCE:
- For every important claim (metrics, success/failure, competitors, key decisions), include at least one evidence item with a timestamp MM:SS and a short snippet (<= 20 words).
- If you cannot reliably provide timestamps, use "N/A" and note why in limitations.

OUTPUT:
- Return ONLY valid JSON matching the provided schema.
"""


# -------------------------
# Schemas (structured outputs)
# -------------------------
Outcome = Literal["success", "failure", "mixed", "unknown"]
Confidence = Literal["high", "medium", "low"]


class Evidence(BaseModel):
    timestamp: str = Field(description="MM:SS, HH:MM:SS, or 'N/A' if not available.")
    snippet: str = Field(description="<= 20 words from the video (paraphrase allowed).")
    note: Optional[str] = Field(default=None, description="Extra context if needed.")


class Metric(BaseModel):
    metric_type: Literal[
        "revenue", "profit", "spend", "burn", "funding", "valuation",
        "users", "paying_customers", "mau", "dau", "downloads",
        "price", "arr", "mrr", "growth_rate", "churn", "cac", "ltv",
        "other"
    ]
    value: Optional[float] = Field(default=None, description="Numeric value if explicitly stated; else null.")
    unit: Optional[str] = Field(default=None, description="e.g., USD, users, %, downloads, etc.")
    time_frame: Optional[str] = Field(default=None, description="e.g., 'per month', 'ARR', 'as of 2025', etc.")
    confidence: Confidence = Field(description="high if exact, medium if approximate, low if uncertain")
    evidence: List[Evidence] = Field(description="At least one evidence item for this metric.")


class Product(BaseModel):
    name: Optional[str] = Field(default=None, description="Product/company name if stated.")
    what_it_does: str = Field(description="What the product does.")
    target_customer: Optional[str] = None
    business_model: Optional[str] = None  # subscription, ads, one-time, services, etc.
    outcome: Outcome
    outcome_reasoning: str = Field(description="Why the outcome label was chosen (based on video statements).")
    status: Optional[Literal["active", "shutdown", "acquired", "pivoted", "unknown"]] = "unknown"
    competitors: List[str] = Field(default_factory=list, description="Only explicit mentions.")
    metrics: List[Metric] = Field(default_factory=list)
    key_lessons: List[str] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list, description="Evidence for product description/outcome/competitors.")


class FounderStory(BaseModel):
    people: List[str] = Field(default_factory=list, description="Founders/guests names if stated.")
    background: Optional[str] = None
    attempts: List[str] = Field(default_factory=list, description="Prior attempts / pivots described in the video.")
    themes: List[str] = Field(default_factory=list, description="Recurring themes from this story (e.g., distribution, PMF).")


class VideoExtraction(BaseModel):
    video_url: str
    title: Optional[str] = ""
    channel: Optional[str] = ""
    upload_date: Optional[str] = Field(default="", description="YYYY-MM-DD if known else empty string.")
    story: FounderStory
    products: List[Product]
    top_takeaways: List[str]
    missing_info: List[str] = Field(
        default_factory=list,
        description="List important fields the video did not provide (e.g., 'revenue', 'user count')."
    )
    limitations: List[str] = Field(default_factory=list, description="Any caveats: timestamps missing, unclear audio, etc.")


class ChannelRollup(BaseModel):
    channel_url: str
    channel_title: str
    coverage: str
    success_patterns: List[str]
    failure_patterns: List[str]
    common_metrics_seen: List[str]  # e.g. "MRR, users, funding"
    notable_competitors: List[str]
    products_index: List[Dict[str, Any]] = Field(
        description="Compact index: {product_name, video_url, outcome, key_metric_highlights}"
    )
    missing_data_overview: List[str] = Field(description="Most commonly missing info across the channel.")
    suggested_queries: List[str] = Field(description="Questions to ask or filters to apply to the dataset.")


# -------------------------
# yt-dlp: enumerate videos (no API, no downloads)
# -------------------------
def normalize_upload_date(yyyymmdd: Optional[str]) -> str:
    if not yyyymmdd or len(yyyymmdd) != 8 or not yyyymmdd.isdigit():
        return ""
    return f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def list_channel_videos(channel_url: str, max_videos: Optional[int] = None) -> Dict[str, Any]:
    # Flat extraction lists entries without fully extracting each video page
    # (helps speed, and still no downloads). --flat-playlist behavior is documented.  [oai_citation:3‡Arch Manual Pages](https://man.archlinux.org/man/extra/yt-dlp/yt-dlp.1.en?utm_source=chatgpt.com)
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": "in_playlist",  # maps to flat playlist behavior in Python usage patterns  [oai_citation:4‡GitHub](https://github.com/yt-dlp/yt-dlp/issues/4853?utm_source=chatgpt.com)
        "ignoreerrors": True,
        "noplaylist": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    entries = info.get("entries") or []
    out = []
    for e in entries:
        if not e:
            continue
        vid = e.get("id") or e.get("url")
        if not vid:
            continue

        video_url = e.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}"
        out.append(
            {
                "video_url": video_url,
                "title": e.get("title") or "",
                "channel": e.get("uploader") or e.get("channel") or "",
                "upload_date": normalize_upload_date(e.get("upload_date")),
            }
        )
        if max_videos and len(out) >= max_videos:
            break

    channel_title = info.get("title") or info.get("uploader") or ""
    return {"channel_title": channel_title, "videos": out}


# -------------------------
# Gemini helpers
# -------------------------
def backoff_sleep(attempt: int, base: float = 1.0, cap: float = 20.0) -> None:
    t = min(cap, base * (2 ** attempt))
    t *= 0.7 + random.random() * 0.6
    time.sleep(t)


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

    last_err = None
    for attempt in range(max_retries):
        try:
            resp = client.models.generate_content(model=model, contents=contents, config=cfg)
            return resp.text
        except Exception as e:
            last_err = e
            backoff_sleep(attempt)

    raise RuntimeError(f"Gemini failed after retries: {last_err!r}")


def summarize_video(client: genai.Client, model: str, meta: Dict[str, str]) -> VideoExtraction:
    # Gemini supports passing YouTube URLs directly as video input (preview).  [oai_citation:5‡Google AI for Developers](https://ai.google.dev/gemini-api/docs/video-understanding)
    prompt = f"""{SHARED_VIDEO_PROMPT}

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
        # Gemini 3 supports thinking_level controls.  [oai_citation:6‡Google AI for Developers](https://ai.google.dev/gemini-api/docs/gemini-3)
        thinking_level="low",
    )
    return VideoExtraction.model_validate_json(raw)


def rollup_channel(client: genai.Client, model: str, channel_url: str, channel_title: str, videos: List[VideoExtraction]) -> ChannelRollup:
    prompt = f"""You are creating a channel-level rollup from structured per-video extractions.

RULES:
- Only use information present in the input JSON.
- Summarize patterns in successes vs failures.
- Build products_index as compact objects:
  {{product_name, video_url, outcome, key_metric_highlights}}
- missing_data_overview should list the most common missing fields across videos.

Channel:
- channel_url: {channel_url}
- channel_title: {channel_title}
"""

    payload = [v.model_dump() for v in videos]

    contents = types.Content(parts=[types.Part(text=prompt), types.Part(text=json.dumps(payload, ensure_ascii=False))])

    raw = gemini_json(
        client=client,
        model=model,
        schema=ChannelRollup.model_json_schema(),
        contents=contents,
        thinking_level="high",
    )
    return ChannelRollup.model_validate_json(raw)


# -------------------------
# IO helpers (resume)
# -------------------------
def load_done(jsonl_path: Path) -> Dict[str, VideoExtraction]:
    done: Dict[str, VideoExtraction] = {}
    if not jsonl_path.exists():
        return done
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = VideoExtraction.model_validate_json(line)
            done[obj.video_url] = obj
        except Exception:
            continue
    return done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel_url", required=True, help="e.g., https://www.youtube.com/@handle/videos")
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--max_videos", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.25)
    ap.add_argument("--video_model", default="gemini-3-flash-preview")
    ap.add_argument("--rollup_model", default="gemini-3-pro-preview")
    args = ap.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY (or GOOGLE_API_KEY).")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    jsonl_path = outdir / "video_extractions.jsonl"
    rollup_path = outdir / "channel_rollup.json"

    listing = list_channel_videos(args.channel_url, max_videos=(args.max_videos or None))
    channel_title = listing["channel_title"]
    videos_meta = listing["videos"]

    print(f"Found {len(videos_meta)} videos. Channel title: {channel_title!r}")

    client = genai.Client(api_key=api_key)

    done = load_done(jsonl_path)
    all_results: List[VideoExtraction] = list(done.values())

    with jsonl_path.open("a", encoding="utf-8") as f:
        for i, meta in enumerate(videos_meta, start=1):
            url = meta["video_url"]
            if url in done:
                continue

            print(f"[{i}/{len(videos_meta)}] Extracting: {meta.get('title','')[:90]}")
            try:
                ve = summarize_video(client, args.video_model, meta)
                f.write(ve.model_dump_json() + "\n")
                f.flush()
                done[url] = ve
                all_results.append(ve)
            except Exception as e:
                print(f"  !! Failed for {url}  err={e!r}")

            time.sleep(max(0.0, args.sleep))

    if not all_results:
        raise SystemExit("No video extractions produced; cannot roll up.")

    rollup = rollup_channel(client, args.rollup_model, args.channel_url, channel_title, all_results)
    rollup_path.write_text(rollup.model_dump_json(indent=2), encoding="utf-8")

    print(f"Done.\n- {jsonl_path}\n- {rollup_path}")


if __name__ == "__main__":
    main()


⸻

Run it

python startup_channel_summarizer.py \
  --channel_url "https://www.youtube.com/@SomeHandle/videos" \
  --outdir out \
  --max_videos 0


⸻

Why this matches your requirements
	•	No YouTube API: video listing is via yt-dlp “flat playlist” style enumeration  ￼
	•	No downloading videos: Gemini reads public YouTube URLs directly (preview feature)  ￼
	•	Strict structured extraction with JSON Schema  ￼
	•	“Not present” handling: enforced via missing_info + null metric values + explicit rules in the shared prompt
	•	Startup-focused fields: outcome + metrics + competitors + products + patterns

⸻

If you want, I can tweak the schema to better match your end goal, e.g.:
	•	one row per product (better for exporting to a spreadsheet),
	•	strict separation between stated facts vs interpretation,
	•	a normalized metrics dictionary (ARR/MRR/users/etc) instead of a list.