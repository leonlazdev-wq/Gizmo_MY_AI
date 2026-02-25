"""Backend logic for the YouTube Video Summarizer feature."""

from __future__ import annotations

import re
from typing import Optional


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def fetch_transcript(video_id: str, language: str = 'en') -> dict:
    """Fetch transcript with metadata.

    Returns a dict with keys:
        segments: list of {"text": str, "start": float, "duration": float}
        full_text: str
    On error returns {"error": str}.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
    except ImportError:
        return {"error": "youtube-transcript-api is not installed. Run: pip install youtube-transcript-api"}

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcript_list.find_transcript([language])
        except NoTranscriptFound:
            # Fall back to auto-generated transcript in any language
            transcript = transcript_list.find_generated_transcript(
                [t.language_code for t in transcript_list]
            )
        segments = transcript.fetch()
        full_text = " ".join(s["text"] for s in segments)
        return {"segments": segments, "full_text": full_text}
    except TranscriptsDisabled:
        return {"error": "Transcripts are disabled for this video."}
    except Exception as exc:
        return {"error": str(exc)}


def get_video_metadata(video_id: str) -> dict:
    """Get title, channel, duration and thumbnail URL.

    Tries pytube first; falls back to a minimal oEmbed fetch.
    Returns a dict with keys: title, channel, duration, thumbnail_url, error (optional).
    """
    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    try:
        from pytube import YouTube  # type: ignore
        yt = YouTube(f"https://www.youtube.com/watch?v={video_id}")
        length_s = yt.length or 0
        minutes, seconds = divmod(length_s, 60)
        return {
            "title": yt.title or "Unknown",
            "channel": yt.author or "Unknown",
            "duration": f"{minutes}:{seconds:02d}",
            "thumbnail_url": yt.thumbnail_url or thumbnail_url,
        }
    except Exception:
        pass

    # Minimal fallback via oEmbed (no auth required)
    try:
        import urllib.request
        import json as _json
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        with urllib.request.urlopen(oembed_url, timeout=5) as resp:
            data = _json.loads(resp.read())
        return {
            "title": data.get("title", "Unknown"),
            "channel": data.get("author_name", "Unknown"),
            "duration": "N/A",
            "thumbnail_url": thumbnail_url,
        }
    except Exception as exc:
        return {
            "title": "Unknown",
            "channel": "Unknown",
            "duration": "N/A",
            "thumbnail_url": thumbnail_url,
            "error": str(exc),
        }


def build_summary_prompt(transcript: str, style: str, question: Optional[str] = None) -> str:
    """Build a prompt for the AI model based on the desired style."""
    style_instructions = {
        "Brief (1 paragraph)": "Summarize the following video transcript in a single concise paragraph.",
        "Detailed (bullet points)": "Summarize the following video transcript using detailed bullet points covering all major topics.",
        "Study Notes": "Convert the following video transcript into structured study notes with headings and key facts.",
        "Key Takeaways": "List the key takeaways and most important insights from the following video transcript.",
        "Timeline/Chapters": "Create a chapter-by-chapter timeline summary of the following video transcript.",
    }
    instruction = style_instructions.get(style, style_instructions["Brief (1 paragraph)"])

    if question:
        prompt = f"Using the following video transcript, answer this question: {question}\n\nTranscript:\n{transcript}"
    else:
        prompt = f"{instruction}\n\nTranscript:\n{transcript}"
    return prompt


def _chunk_transcript(full_text: str, max_chars: int = 12000) -> list[str]:
    """Split transcript into chunks for map-reduce summarisation."""
    words = full_text.split()
    chunks, current = [], []
    current_len = 0
    for word in words:
        current.append(word)
        current_len += len(word) + 1
        if current_len >= max_chars:
            chunks.append(" ".join(current))
            current, current_len = [], 0
    if current:
        chunks.append(" ".join(current))
    return chunks


def summarize_video(url: str, style: str, language: str = 'en', question: Optional[str] = None) -> dict:
    """High-level helper: extract ID → fetch transcript → build prompt.

    Returns dict with keys:
        video_id, metadata, transcript_segments, prompt, error (optional)
    """
    video_id = extract_video_id(url)
    if not video_id:
        return {"error": "Could not extract a valid YouTube video ID from the URL."}

    metadata = get_video_metadata(video_id)
    transcript_data = fetch_transcript(video_id, language)
    if "error" in transcript_data:
        return {"video_id": video_id, "metadata": metadata, "error": transcript_data["error"]}

    full_text = transcript_data["full_text"]
    # Map-reduce if transcript is very long
    chunks = _chunk_transcript(full_text)
    if len(chunks) > 1:
        # Summarise each chunk briefly first, then combine
        combined = "\n\n".join(f"[Part {i+1}]\n{c}" for i, c in enumerate(chunks[:8]))
        prompt = build_summary_prompt(combined, style, question)
    else:
        prompt = build_summary_prompt(full_text, style, question)

    return {
        "video_id": video_id,
        "metadata": metadata,
        "transcript_segments": transcript_data["segments"],
        "full_text": full_text,
        "prompt": prompt,
    }
