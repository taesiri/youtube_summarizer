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
from youtube_summarize.presets import (
    DEFAULT_PRESET_ID,
    DEFAULT_PROMPT,
    list_presets,
    load_preset,
    load_preset_safe,
    sanitize_preset_id,
    save_preset,
)
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
    preset = load_preset_safe(DEFAULT_PRESET_ID)
    if preset and isinstance(preset.get("schema"), dict):
        return json.dumps(preset["schema"], indent=2)
    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "keyword": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "keyword"],
    }
    return json.dumps(schema, indent=2)




@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    default_preset = load_preset_safe(DEFAULT_PRESET_ID) or {}
    context = {
        "request": request,
        "default_prompt": default_preset.get("prompt", DEFAULT_PROMPT),
        "default_schema": default_schema_json(),
        "default_model": "gemini-3-flash-preview",
        "presets": list_presets(),
        "default_preset_id": DEFAULT_PRESET_ID,
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


@app.get("/api/presets")
async def presets_list() -> JSONResponse:
    return JSONResponse(content={"presets": list_presets()})


@app.get("/api/presets/{preset_id}")
async def presets_get(preset_id: str) -> JSONResponse:
    safe_id = sanitize_preset_id(preset_id)
    try:
        preset = load_preset(safe_id)
    except FileNotFoundError:
        return JSONResponse(status_code=404, content={"error": "Preset not found."})
    return JSONResponse(content=preset)


@app.post("/api/presets")
async def presets_save(payload: Dict[str, Any]) -> JSONResponse:
    name = str(payload.get("name", "")).strip()
    prompt = payload.get("prompt")
    schema = payload.get("schema")

    if not name:
        return JSONResponse(status_code=400, content={"error": "Preset name is required."})
    if not isinstance(schema, dict):
        return JSONResponse(status_code=400, content={"error": "Schema must be a JSON object."})
    if not isinstance(prompt, str):
        return JSONResponse(status_code=400, content={"error": "Prompt must be a string."})

    preset_id = sanitize_preset_id(name)
    if not preset_id:
        return JSONResponse(status_code=400, content={"error": "Preset name has no valid characters."})

    save_preset(preset_id, {"name": name, "prompt": prompt, "schema": schema})
    return JSONResponse(content={"id": preset_id, "name": name})


def run() -> None:
    import uvicorn

    uvicorn.run("youtube_summarize.webapp:app", host="127.0.0.1", port=8000, reload=True)
