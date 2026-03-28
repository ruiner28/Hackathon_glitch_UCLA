# Demo topic cache (faster showcase reloads)

When a user creates a lesson whose topic matches a **homepage showcase** demo (Rate Limiter, OS Deadlock, Bottom-Up Parsing), the API can skip regenerating images, audio, Veo clips, and the final MP4 by copying from this folder.

## Layout

```
{slug}/                     # rate_limiter | os_deadlock | bottom_up_parsing
  manifest.json             # scene_count, narration_texts[], metadata
  scenes/0/image.png
  scenes/0/narration.wav
  scenes/0/video.mp4        # optional
  scenes/1/...
  output/lesson.mp4         # optional but recommended (skips FFmpeg)
  output/subtitles.srt      # optional
```

## Populate once per demo machine

1. Create a lesson from the UI with the exact showcase topic (e.g. **Rate Limiter**).
2. Run the full pipeline through **generate assets** and **render preview** (or final).
3. Export:

```bash
cd apps/api && source venv/bin/activate
python -m app.utils.populate_demo_cache --lesson-id <LESSON_UUID> --slug rate_limiter
```

Repeat for `os_deadlock` and `bottom_up_parsing` with lessons that match those topics.

## Configuration

`DEMO_CACHE_PATH` in `.env` (default: `./storage/demo_cache`).

If the cache folder for a slug is missing or incomplete, behavior falls back to normal AI generation.
