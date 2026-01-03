"""FastAPI app for summarizing a single YouTube video."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google import genai

from youtube_summarize.gemini import infer_schema_from_prompt, load_api_key, summarize_custom
from youtube_summarize.prompts import SHARED_VIDEO_PROMPT

APP_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = APP_ROOT / "web" / "templates"
STATIC_DIR = APP_ROOT / "web" / "static"

app = FastAPI(title="YouTube Summarize")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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


def build_prompt(base_prompt: str, meta: Dict[str, str]) -> str:
    return f"""{base_prompt}

VIDEO METADATA (use exactly):
- video_url: {meta["video_url"]}
- title: {meta.get("title","")}
- channel: {meta.get("channel","")}
- upload_date: {meta.get("upload_date","")}

Return ONLY valid JSON that matches the provided schema.
"""


def default_schema_json() -> str:
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "key_points": {"type": "array", "items": {"type": "string"}},
            "action_items": {"type": "array", "items": {"type": "string"}},
            "people": {"type": "array", "items": {"type": "string"}},
            "outcome": {"type": "string"},
            "metrics": {
                "type": "object",
                "properties": {
                    "revenue": {"type": "string"},
                    "users": {"type": "string"},
                    "funding": {"type": "string"},
                },
            },
        },
        "required": ["summary"],
    }
    return json.dumps(schema, indent=2)


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    context = {
        "request": request,
        "default_prompt": SHARED_VIDEO_PROMPT,
        "default_schema": default_schema_json(),
        "default_model": "gemini-3-flash-preview",
        "result_json": None,
        "error": None,
        "video_input": "",
    }
    return templates.TemplateResponse("index.html", context)


@app.post("/summarize", response_class=HTMLResponse)
def summarize(
    request: Request,
    video_input: str = Form(...),
    prompt: str = Form(...),
    schema_json: str = Form(...),
    model: str = Form("gemini-3-flash-preview"),
) -> HTMLResponse:
    video_url = normalize_video_url(video_input)
    if not video_url:
        context = {
            "request": request,
            "default_prompt": prompt,
            "default_schema": schema_json,
            "default_model": model,
            "result_json": None,
            "error": "Provide a YouTube URL or video id.",
            "video_input": video_input,
        }
        return templates.TemplateResponse("index.html", context)

    try:
        schema = json.loads(schema_json)
        if not isinstance(schema, dict):
            raise ValueError("Schema must be a JSON object.")
    except Exception as exc:
        context = {
            "request": request,
            "default_prompt": prompt,
            "default_schema": schema_json,
            "default_model": model,
            "result_json": None,
            "error": f"Invalid schema JSON: {exc}",
            "video_input": video_input,
        }
        return templates.TemplateResponse("index.html", context)

    api_key = load_api_key()
    client = genai.Client(api_key=api_key)
    meta = {"video_url": video_url, "title": "", "channel": "", "upload_date": ""}
    full_prompt = build_prompt(prompt, meta)

    try:
        raw = summarize_custom(client=client, model=model, prompt=full_prompt, meta=meta, schema=schema)
        parsed = json.loads(raw)
        result_json = json.dumps(parsed, indent=2)
    except Exception as exc:
        context = {
            "request": request,
            "default_prompt": prompt,
            "default_schema": schema_json,
            "default_model": model,
            "result_json": None,
            "error": f"Summarization failed: {exc}",
            "video_input": video_input,
        }
        return templates.TemplateResponse("index.html", context)

    context = {
        "request": request,
        "default_prompt": prompt,
        "default_schema": schema_json,
        "default_model": model,
        "result_json": result_json,
        "error": None,
        "video_input": video_input,
    }
    return templates.TemplateResponse("index.html", context)


@app.post("/api/summarize")
async def summarize_api(payload: Dict[str, Any]) -> JSONResponse:
    video_input = str(payload.get("video_input", "")).strip()
    prompt = str(payload.get("prompt", SHARED_VIDEO_PROMPT))
    schema = payload.get("schema")
    model = str(payload.get("model", "gemini-3-flash-preview"))

    if not isinstance(schema, dict):
        return JSONResponse(status_code=400, content={"error": "schema must be a JSON object"})

    video_url = normalize_video_url(video_input)
    if not video_url:
        return JSONResponse(status_code=400, content={"error": "Provide a YouTube URL or video id."})

    api_key = load_api_key()
    client = genai.Client(api_key=api_key)
    meta = {"video_url": video_url, "title": "", "channel": "", "upload_date": ""}
    full_prompt = build_prompt(prompt, meta)

    raw = summarize_custom(client=client, model=model, prompt=full_prompt, meta=meta, schema=schema)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return JSONResponse(status_code=502, content={"error": "Model returned invalid JSON", "raw": raw})

    return JSONResponse(content=parsed)


@app.post("/api/infer-schema")
async def infer_schema(payload: Dict[str, Any]) -> JSONResponse:
    prompt = str(payload.get("prompt", "")).strip()
    model = str(payload.get("model", "gemini-3-flash-preview"))

    if not prompt:
        return JSONResponse(status_code=400, content={"error": "Prompt is required."})

    api_key = load_api_key()
    client = genai.Client(api_key=api_key)

    try:
        schema = infer_schema_from_prompt(client=client, model=model, prompt_text=prompt)
    except Exception as exc:
        return JSONResponse(status_code=502, content={"error": f"Schema inference failed: {exc}"})

    if not isinstance(schema, dict) or schema.get("type") != "object":
        return JSONResponse(status_code=502, content={"error": "Invalid schema returned by model.", "schema": schema})

    return JSONResponse(content=schema)


def run() -> None:
    import uvicorn

    uvicorn.run("youtube_summarize.webapp:app", host="127.0.0.1", port=8000, reload=True)
