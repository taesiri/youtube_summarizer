"""Prompt templates for Gemini summarization."""

SHARED_VIDEO_PROMPT = """You are extracting structured startup case-study facts from a YouTube video.

HARD RULES:
- Only extract facts that are explicitly stated or shown in the video.
- Do NOT infer numbers (revenue, users, spend, funding, etc.). If not stated, set the field to null and add it to missing_info.
- If a figure is approximate ("~", "about", "around"), keep it and mark confidence="medium".
- If a figure is unclear/ambiguous, set value=null and explain in notes + missing_info.
- Success/failure classification:
  - "success" only if the video clearly claims meaningful success (e.g., profitable, significant revenue/users, acquisition, strong growth).
- "failure" only if the video clearly states it failed, shut down, ran out of money, or could not find product-market fit.
  - Otherwise use "mixed" or "unknown" with explanation.
- Competitors: only include competitors explicitly mentioned.

EVIDENCE:
- For every important claim (metrics, success/failure, competitors, key decisions), include at least one evidence item with a timestamp MM:SS and a short snippet (<= 20 words).
- If you cannot reliably provide timestamps, use "N/A" and note why in limitations.

OUTPUT:
- Return ONLY valid JSON matching the provided schema.
"""
