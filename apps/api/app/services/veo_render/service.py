"""Multi-clip Veo (1080p) + Lyria + TTS narration, mixed and slowed to 0.75x."""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.providers.base import MusicProvider, StorageProvider, TTSProvider, VideoProvider
from app.services.diagram.service import DiagramService
from app.services.rendering.service import HEIGHT, WIDTH

logger = logging.getLogger(__name__)

_MAX_VEO_CONCURRENT = 3
# Playback slower = longer watch time; audio stretched to match.
PLAYBACK_SPEED = 0.75
# amix normalize=0: narration clearly louder than bed music.
MUSIC_VOLUME = 0.22
NARRATION_VOLUME = 1.55
# Encode: sharp 1080p master before final pass.
NORM_CRF = 17
FINAL_CRF = 17


def _ffprobe_duration(path: str) -> float:
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            return 0.0
        return float((r.stdout or "0").strip() or 0)
    except (ValueError, subprocess.TimeoutExpired, OSError):
        return 0.0


def _normalize_veo_hd(src: str, dst: str) -> bool:
    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        src,
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        str(NORM_CRF),
        "-pix_fmt",
        "yuv420p",
        "-an",
        dst,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=180)
        return r.returncode == 0 and Path(dst).is_file() and Path(dst).stat().st_size > 500
    except subprocess.TimeoutExpired:
        logger.warning("normalize_veo_hd timed out for %s", src)
        return False


def _escape_concat_path(p: str) -> str:
    return p.replace("'", "'\\''")


def _run_ffmpeg(cmd: list[str], label: str) -> bool:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        logger.warning(
            "VeoRender ffmpeg %s failed rc=%s err=%s",
            label,
            r.returncode,
            (r.stderr or "")[:600],
        )
        return False
    return True


class VeoRenderService:
    """Plan chunks, Veo 1080p clips, TTS narration, Lyria bed, mix, 0.75x output."""

    def __init__(
        self,
        video_provider: VideoProvider,
        music_provider: MusicProvider,
        storage: StorageProvider,
        diagram: DiagramService,
        tts: TTSProvider,
    ) -> None:
        self.video = video_provider
        self.music = music_provider
        self.storage = storage
        self.diagram = diagram
        self.tts = tts

    async def generate_animation(
        self,
        lesson_id: str,
        topic: str,
        diagram_spec: dict,
        walkthrough_states: list[dict],
    ) -> str:
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise RuntimeError("ffmpeg and ffprobe are required on PATH.")

        clear_trace = getattr(self.video, "clear_generation_trace", None)
        if callable(clear_trace):
            clear_trace()

        plan = await self.diagram.plan_animation_chunks(
            topic, diagram_spec, walkthrough_states
        )
        chunks = plan["chunks"]
        music_prompt = plan["music_prompt"]
        est_video_sec = sum(int(c.get("duration_sec", 8)) for c in chunks)

        sem = asyncio.Semaphore(_MAX_VEO_CONCURRENT)

        async def one_chunk(idx: int, chunk: dict) -> tuple[int, bytes]:
            async with sem:
                dur = float(chunk.get("duration_sec", 8))
                prompt = str(chunk.get("veo_prompt", ""))
                data = await self.video.generate_from_text(prompt, dur)
                return idx, data

        music_task = asyncio.create_task(
            self.music.generate_track(
                music_prompt,
                max(float(est_video_sec) * 1.4, 48.0),
            )
        )
        veo_results = await asyncio.gather(
            *[one_chunk(i, c) for i, c in enumerate(chunks)]
        )
        music_bytes = await music_task

        veo_results.sort(key=lambda x: x[0])
        valid_items: list[tuple[int, bytes]] = [
            (idx, b) for idx, b in veo_results if b and len(b) > 500
        ]
        if not valid_items:
            hint = ""
            prov = type(self.video).__name__
            if "Mock" in prov:
                hint = (
                    " VIDEO_PROVIDER is mock: install ffmpeg on the API host, or set "
                    "VIDEO_PROVIDER=google with a valid GEMINI_API_KEY for real Veo clips."
                )
            elif prov == "VeoVideoProvider":
                summary = getattr(self.video, "generation_trace_summary", None)
                trace = summary() if callable(summary) else ""
                if trace:
                    hint = f" Veo trace: {trace[:1200]}"
            raise RuntimeError(
                "All Veo chunk generations failed or returned empty video." + hint
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            norm_paths: list[str] = []
            meta_indices: list[int] = []

            for i, (orig_idx, raw) in enumerate(valid_items):
                raw_path = tmp_path / f"chunk_{i:03d}.mp4"
                raw_path.write_bytes(raw)
                norm_path = tmp_path / f"norm_{i:03d}.mp4"
                if _normalize_veo_hd(str(raw_path), str(norm_path)):
                    norm_paths.append(str(norm_path))
                    meta_indices.append(orig_idx)
                else:
                    logger.warning("VeoRender: HD normalize failed for chunk orig_idx=%s", orig_idx)

            if not norm_paths:
                raise RuntimeError("No Veo clips could be normalized")

            segment_durs: list[float] = []
            for p in norm_paths:
                d = _ffprobe_duration(p)
                segment_durs.append(max(d, 0.1))

            concat_list = tmp_path / "concat.txt"
            with open(concat_list, "w", encoding="utf-8") as f:
                for p in norm_paths:
                    f.write(f"file '{_escape_concat_path(p)}'\n")

            slideshow = tmp_path / "slideshow.mp4"
            cmd_v = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                str(NORM_CRF),
                "-pix_fmt",
                "yuv420p",
                str(slideshow),
            ]
            if not _run_ffmpeg(cmd_v, "concat_video"):
                raise RuntimeError("FFmpeg concat failed")

            total_d = _ffprobe_duration(str(slideshow))
            if total_d <= 0:
                total_d = sum(segment_durs)

            narr_texts: list[str] = []
            for orig_idx, seg_dur in zip(meta_indices, segment_durs):
                ch = chunks[orig_idx] if orig_idx < len(chunks) else {}
                t = str(ch.get("narration_text", "")).strip()
                if not t:
                    t = str(ch.get("title", "")).strip() or f"Segment on {topic}."
                narr_texts.append(t[:1200])

            narr_wavs = await asyncio.gather(
                *[self.tts.synthesize(txt) for txt in narr_texts]
            )

            segment_wavs: list[str] = []
            for i, (wav_bytes, seg_dur) in enumerate(zip(narr_wavs, segment_durs)):
                seg_in = tmp_path / f"narr_raw_{i:03d}.wav"
                seg_out = tmp_path / f"narr_seg_{i:03d}.wav"
                seg_in.write_bytes(wav_bytes)
                apad_d = max(0.1, seg_dur)
                trim_pad = (
                    f"atrim=duration={apad_d:.3f},"
                    f"apad=whole_dur={apad_d:.3f}"
                )
                cmd_pad = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(seg_in),
                    "-af",
                    trim_pad,
                    "-ar",
                    "48000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(seg_out),
                ]
                if not _run_ffmpeg(cmd_pad, f"narr_pad_{i}"):
                    shutil.copy(seg_in, seg_out)
                segment_wavs.append(str(seg_out))

            narr_list = tmp_path / "narr_concat.txt"
            with open(narr_list, "w", encoding="utf-8") as f:
                for p in segment_wavs:
                    f.write(f"file '{_escape_concat_path(p)}'\n")

            narr_full = tmp_path / "narration_full.wav"
            cmd_nc = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(narr_list),
                "-ar",
                "48000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(narr_full),
            ]
            if not _run_ffmpeg(cmd_nc, "narr_concat"):
                raise RuntimeError("Failed to concatenate narration audio")

            narr_fit = tmp_path / "narration_fit.wav"
            af_fit = f"atrim=0:{total_d:.3f},apad=whole_dur={total_d:.3f}"
            cmd_nf = [
                "ffmpeg",
                "-y",
                "-i",
                str(narr_full),
                "-af",
                af_fit,
                "-ar",
                "48000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(narr_fit),
            ]
            if not _run_ffmpeg(cmd_nf, "narr_fit"):
                shutil.copy(narr_full, narr_fit)

            music_raw = tmp_path / "music_raw.bin"
            music_raw.write_bytes(music_bytes if music_bytes and len(music_bytes) > 50 else b"")
            music_path = tmp_path / "music_input.wav"
            from app.providers.mock_music import _silent_wav

            if music_raw.stat().st_size < 50:
                music_path.write_bytes(_silent_wav(max(total_d, 32.0)))
            else:
                cmd_dec = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(music_raw),
                    "-ar",
                    "48000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(music_path),
                ]
                if not _run_ffmpeg(cmd_dec, "music_decode"):
                    music_path.write_bytes(_silent_wav(max(total_d, 32.0)))

            music_looped = tmp_path / "music_looped.wav"
            cmd_ml = [
                "ffmpeg",
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                str(music_path),
                "-t",
                f"{total_d:.3f}",
                "-af",
                f"volume={2.2}",
                "-ar",
                "48000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(music_looped),
            ]
            if not _run_ffmpeg(cmd_ml, "music_loop"):
                shutil.copy(music_path, music_looped)

            mixed_audio = tmp_path / "mixed.wav"
            mix_filter = (
                f"[0:a]volume={MUSIC_VOLUME}[m];"
                f"[1:a]volume={NARRATION_VOLUME}[n];"
                f"[m][n]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[out]"
            )
            cmd_mix = [
                "ffmpeg",
                "-y",
                "-i",
                str(music_looped),
                "-i",
                str(narr_fit),
                "-filter_complex",
                mix_filter,
                "-map",
                "[out]",
                "-t",
                f"{total_d:.3f}",
                "-ar",
                "48000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(mixed_audio),
            ]
            if not _run_ffmpeg(cmd_mix, "amix"):
                shutil.copy(narr_fit, mixed_audio)

            muxed = tmp_path / "muxed.mp4"
            cmd_mux = [
                "ffmpeg",
                "-y",
                "-i",
                str(slideshow),
                "-i",
                str(mixed_audio),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(muxed),
            ]
            if not _run_ffmpeg(cmd_mux, "mux"):
                raise RuntimeError("Failed to mux video and audio")

            final_tmp = tmp_path / "final.mp4"
            inv_speed = 1.0 / PLAYBACK_SPEED
            vf = f"setpts={inv_speed}*PTS"
            af = f"atempo={PLAYBACK_SPEED}"
            cmd_slow = [
                "ffmpeg",
                "-y",
                "-i",
                str(muxed),
                "-vf",
                vf,
                "-af",
                af,
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                str(FINAL_CRF),
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(final_tmp),
            ]
            if not _run_ffmpeg(cmd_slow, "slow_final"):
                shutil.copy(muxed, final_tmp)

            if not final_tmp.is_file() or final_tmp.stat().st_size < 512:
                raise RuntimeError("Final animation file missing or empty")

            out_bytes = final_tmp.read_bytes()

        rel = f"output/{lesson_id}/lesson.mp4"
        url = await self.storage.put_file(rel, out_bytes, "video/mp4")
        logger.info(
            "VeoRenderService: lesson=%s clips=%d speed=%sx -> %s",
            lesson_id,
            len(norm_paths),
            PLAYBACK_SPEED,
            url,
        )
        return url
