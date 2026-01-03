# Youtube Summarizer

Summarize YouTube videos into structured JSON with Gemini 3.0. Includes a web UI for building schemas, prompt editing,
and previewing results.


![Web Interface](assets/imgs/interface.png)

## Features

- Prompt editor + schema inference using Gemini
- Schema builder with one nested level + list support
- JSON output preview with optional raw JSON view
- Export JSON
- Preset load/save (file-based, no database)
- CLI with custom JSON Schema and prompt support

## Environment

Use a `.env` file for API keys and secrets. Copy `.env.example` to `.env` and fill in values.

## Install

```bash
uv sync
```

## CLI

Run with `uv`:

```bash
uv run youtube-summarize "https://www.youtube.com/watch?v=VIDEO_ID" --out out/summary.json
```

Use a saved UI preset (prompt + schema):

```bash
uv run youtube-summarize "https://www.youtube.com/watch?v=VIDEO_ID" \
  --schema src/data/presets/summary_keywords.json \
  --out out/summary.json
```

Provide a custom schema:

```bash
uv run youtube-summarize "https://www.youtube.com/watch?v=VIDEO_ID" \
  --schema path/to/schema.json \
  --out out/summary.json
```

## Web app (FastAPI)

Start the server:

```bash
uv run youtube-summarize-web
```

Open `http://127.0.0.1:8000` in your browser.

### Web UI overview


- Enter a YouTube URL or ID
- Edit the prompt
- Build a schema or click "Infer Schema"
- Click "Summarize" to get JSON + preview
- Click "Export JSON" to download results

## Structured output

This tool summarizes the video content into a structured JSON format defined by your schema so results are consistent
and easy to parse.

![Output Preview](assets/imgs/output.png)

## Presets (file-based)

Presets live in `src/data/presets` as JSON files:

```json
{
  "name": "Summary + Keywords",
  "prompt": "Summarize the YouTube video.",
  "schema": { "type": "object", "properties": { "summary": { "type": "string" } } }
}
```

Use the Presets dropdown to load or save new ones (no database required).



## API endpoints

- `POST /api/summarize` expects: `video_input`, `prompt`, `schema`, `model`
- `POST /api/infer-schema` expects: `prompt`, `model`
- `GET /api/presets` list presets
- `GET /api/presets/{id}` load preset
- `POST /api/presets` save preset (`name`, `prompt`, `schema`)
