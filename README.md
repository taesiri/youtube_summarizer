# youtube-summarize

Web app that summarizes YouTube videos into a user-provided structured format using Gemini.

## Project status

Initial CLI only. Web app not implemented yet.

## Environment

Use a `.env` file for API keys and secrets. Copy `.env.example` to `.env` and fill in values.

## CLI (single video)

Run with `uv`:

```bash
uv run youtube-summarize "https://www.youtube.com/watch?v=VIDEO_ID" --out out/summary.json
```

## Web app (FastAPI)

Start the server:

```bash
uv run youtube-summarize-web
```

Open `http://127.0.0.1:8000` in your browser to use the schema builder, prompt editor, and JSON preview.
