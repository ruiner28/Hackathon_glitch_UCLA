"""WebSocket endpoint for Gemini Live API voice interaction with diagrams.

Architecture: Browser <-> FastAPI WebSocket <-> Gemini Live API
- Browser sends raw PCM audio (16-bit, 16kHz, mono) as binary frames
- Browser sends JSON text frames for control messages
- Server forwards audio to Gemini Live and streams responses back
- Diagram context is injected as system instruction
- Gemini session is reconnected between turns with conversation history
  in the system instruction, because the Gemini Live API doesn't reliably
  process audio after the first turn_complete within a single session.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_async_session_factory
from app.models.lesson import Lesson
from app.models.lesson_plan import LessonPlan

router = APIRouter()
logger = logging.getLogger(__name__)

_LIVE_MODEL = "gemini-2.5-flash-native-audio-latest"

try:
    from google.genai import live as _genai_live_module
    _original_ws_connect = _genai_live_module.ws_connect

    class _PatchedWsConnect(_original_ws_connect):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("ping_timeout", None)
            kwargs.setdefault("ping_interval", 30)
            kwargs.setdefault("close_timeout", 120)
            kwargs.setdefault("max_size", 2**24)
            super().__init__(*args, **kwargs)

    _genai_live_module.ws_connect = _PatchedWsConnect
except Exception:
    pass


def _build_system_instruction(
    topic: str,
    diagram_spec: dict | None,
    walkthrough_states: list[dict] | None,
    conversation_history: list[dict] | None = None,
    narration_state: dict | None = None,
) -> str:
    if narration_state:
        parts: list[str] = [
            f"You are a live narrator guiding a student through an interactive diagram about '{topic}'.",
            "IMPORTANT: Always respond in English only.",
            f"You are currently explaining step {narration_state.get('step_number', '?')} of {narration_state.get('total_steps', '?')}.",
            f"The concept to explain: {narration_state.get('title', 'Unknown')}.",
            f"Key points to cover: {narration_state.get('narration', '')}",
            "",
            "NARRATION GUIDELINES:",
            "- Explain this concept as if teaching it live to a student who can see the diagram.",
            "- Be conversational, engaging, and concise — aim for 20-30 seconds of speech.",
            "- Reference the specific components highlighted in the diagram.",
            "- Use analogies when helpful.",
            "- After explaining, naturally invite the student to ask questions or continue.",
            "- If the student asks a question, answer it thoroughly before they move on.",
        ]
    else:
        parts: list[str] = [
            f"You are an expert, friendly computer science tutor helping a student understand '{topic}'.",
            "IMPORTANT: Always respond in English only, regardless of what language the user speaks or what language you detect. All your responses must be entirely in English.",
            "The student is viewing an interactive system-design diagram while you talk.",
            "Answer questions conversationally — be concise but thorough.",
            "Reference specific components, connections, and concepts from the diagram.",
            "If the student seems confused, simplify your explanation and use analogies.",
            "Keep responses under 30 seconds of speech unless the student asks for more detail.",
        ]

    if diagram_spec:
        components = diagram_spec.get("components", [])
        if components:
            comp_desc = ", ".join(
                f"{c.get('label', c.get('id', '?'))}" for c in components
            )
            parts.append(f"\nThe diagram shows these components (left to right): {comp_desc}.")

        connections = diagram_spec.get("connections", [])
        if connections:
            conn_lines: list[str] = []
            comp_map = {c["id"]: c.get("label", c["id"]) for c in components}
            for conn in connections:
                fr = comp_map.get(conn.get("from", ""), conn.get("from", "?"))
                to = comp_map.get(conn.get("to", ""), conn.get("to", "?"))
                label = conn.get("label", "")
                line = f"  {fr} → {to}"
                if label:
                    line += f" ({label})"
                conn_lines.append(line)
            parts.append("\nConnections:\n" + "\n".join(conn_lines))

        flow_paths = diagram_spec.get("flow_paths", {})
        if flow_paths:
            for fp_id, fp in flow_paths.items():
                parts.append(
                    f"\nFlow path '{fp.get('label', fp_id)}': {fp.get('description', '')}"
                )

        overlays = diagram_spec.get("algorithm_overlays", {})
        if overlays:
            parts.append("\nAlgorithm overlays available:")
            for ov_id, ov in overlays.items():
                parts.append(f"  - {ov.get('label', ov_id)}: {ov.get('description', '')}")

        side_panel = diagram_spec.get("side_panel")
        if side_panel:
            items = side_panel.get("items", [])
            if items:
                parts.append(f"\nInternal logic steps ({side_panel.get('title', 'Logic')}):")
                for item in items:
                    parts.append(f"  {item}")

    if walkthrough_states:
        parts.append("\nWalkthrough states available:")
        for ws_item in walkthrough_states[:3]:
            parts.append(f"  - {ws_item.get('title', '?')}: {ws_item.get('narration', '')[:80]}...")

    if conversation_history:
        parts.append("\n\n--- Previous conversation ---")
        for entry in conversation_history[-6:]:
            role = entry.get("role", "user").upper()
            text = entry.get("text", "")
            if text:
                parts.append(f"{role}: {text}")
        parts.append("--- Continue the conversation naturally. Do not repeat previous answers. ---")

    return "\n".join(parts)


async def _load_diagram_context(lesson_id: str) -> tuple[str, dict | None, list[dict] | None]:
    factory = get_async_session_factory()
    async with factory() as db:
        lesson_result = await db.execute(
            select(Lesson).where(Lesson.id == UUID(lesson_id))
        )
        lesson = lesson_result.scalar_one_or_none()
        if not lesson:
            return "Unknown Topic", None, None

        topic = lesson.input_topic or lesson.title or "Computer Science"

        plan_result = await db.execute(
            select(LessonPlan).where(LessonPlan.lesson_id == UUID(lesson_id))
        )
        plan = plan_result.scalar_one_or_none()
        if not plan:
            return topic, None, None

        return topic, plan.diagram_spec_json, plan.walkthrough_states_json


async def _run_single_turn(
    websocket: WebSocket,
    session,
    turn_number: int,
) -> tuple[str, str] | None:
    """Run one turn: stream audio to Gemini, stream response back.

    Returns (user_transcript, assistant_transcript) or None if disconnected.
    """
    stop = asyncio.Event()
    user_parts: list[str] = []
    asst_parts: list[str] = []
    frame_count = 0
    got_response = False

    async def forward_client():
        nonlocal frame_count
        try:
            while not stop.is_set():
                msg = await websocket.receive()

                if msg.get("type") == "websocket.disconnect":
                    stop.set()
                    return "disconnect"

                if "bytes" in msg:
                    frame_count += 1
                    if frame_count % 100 == 1:
                        print(f"[LIVE] T{turn_number} frame#{frame_count}", flush=True)
                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=msg["bytes"],
                            mime_type="audio/pcm;rate=16000",
                        )
                    )
                elif "text" in msg:
                    try:
                        data = json.loads(msg["text"])
                    except json.JSONDecodeError:
                        continue
                    mt = data.get("type", "")
                    if mt == "text":
                        txt = data.get("text", "")
                        print(f"[LIVE] T{turn_number} text: {txt!r}", flush=True)
                        user_parts.append(txt)
                        await session.send_client_content(
                            turns=types.Content(
                                role="user",
                                parts=[types.Part(text=txt)],
                            ),
                            turn_complete=True,
                        )
                    elif mt == "narrate_state":
                        state_data = data.get("state", {})
                        txt = f"Please explain this concept: {state_data.get('title', '')}. Cover these points: {state_data.get('narration', '')}"
                        print(f"[LIVE] T{turn_number} narrate_state: {state_data.get('title', '?')!r}", flush=True)
                        user_parts.append(txt)
                        await session.send_client_content(
                            turns=types.Content(
                                role="user",
                                parts=[types.Part(text=txt)],
                            ),
                            turn_complete=True,
                        )
                    elif mt == "end":
                        stop.set()
                        return "end"
        except WebSocketDisconnect:
            stop.set()
            return "disconnect"
        except Exception as exc:
            print(f"[LIVE] T{turn_number} fwd error: {exc}", flush=True)
            stop.set()
            return "error"

    async def forward_gemini():
        nonlocal got_response
        try:
            async for resp in session.receive():
                if stop.is_set():
                    return

                sc = resp.server_content
                if not sc:
                    continue

                if sc.model_turn:
                    got_response = True
                    for part in sc.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            await websocket.send_json({
                                "type": "audio",
                                "data": base64.b64encode(part.inline_data.data).decode("ascii"),
                            })
                        if part.text:
                            await websocket.send_json({"type": "text", "text": part.text})

                if sc.output_transcription and sc.output_transcription.text:
                    asst_parts.append(sc.output_transcription.text)
                    await websocket.send_json({
                        "type": "transcript",
                        "text": sc.output_transcription.text,
                    })

                if sc.input_transcription and sc.input_transcription.text:
                    user_parts.append(sc.input_transcription.text)
                    print(f"[LIVE] T{turn_number} heard: {sc.input_transcription.text!r}", flush=True)
                    await websocket.send_json({
                        "type": "input_transcript",
                        "text": sc.input_transcription.text,
                    })

                if sc.turn_complete:
                    print(f"[LIVE] T{turn_number} complete, frames={frame_count}", flush=True)
                    stop.set()
                    return

        except Exception as exc:
            if not stop.is_set():
                print(f"[LIVE] T{turn_number} gemini error: {exc}", flush=True)
            stop.set()

    client_task = asyncio.create_task(forward_client())
    gemini_task = asyncio.create_task(forward_gemini())

    done, pending = await asyncio.wait(
        [client_task, gemini_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    for task in done:
        try:
            result = task.result()
            if result == "disconnect":
                return None
        except Exception:
            pass

    if not got_response and frame_count == 0:
        return None

    return "".join(user_parts).strip(), "".join(asst_parts).strip()


@router.websocket("/api/lessons/{lesson_id}/live")
async def live_chat(websocket: WebSocket, lesson_id: str):
    await websocket.accept()

    settings = get_settings()
    api_key = (settings.GEMINI_API_KEY or "").strip()
    if not api_key:
        await websocket.send_json({"type": "error", "message": "GEMINI_API_KEY not configured"})
        await websocket.close()
        return

    topic, diagram_spec, walkthrough_states = await _load_diagram_context(lesson_id)
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(api_version="v1alpha"),
    )

    await websocket.send_json({"type": "connected", "topic": topic})

    conversation_history: list[dict] = []
    turn = 0
    current_narration_state: dict | None = None

    try:
        while True:
            sys_text = _build_system_instruction(
                topic, diagram_spec, walkthrough_states,
                conversation_history=conversation_history or None,
                narration_state=current_narration_state,
            )

            config = types.LiveConnectConfig(
                response_modalities=[types.Modality.AUDIO],
                system_instruction=types.Content(
                    parts=[types.Part(text=sys_text)]
                ),
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                    )
                ),
                output_audio_transcription=types.AudioTranscriptionConfig(),
                input_audio_transcription=types.AudioTranscriptionConfig(),
            )

            print(f"[LIVE] Opening Gemini session for turn {turn} (history={len(conversation_history)})", flush=True)

            try:
                async with client.aio.live.connect(model=_LIVE_MODEL, config=config) as session:
                    await websocket.send_json({"type": "session_ready", "model": _LIVE_MODEL})

                    result = await _run_single_turn(websocket, session, turn)

                    if result is None:
                        break

                    user_text, asst_text = result
                    if user_text:
                        conversation_history.append({"role": "user", "text": user_text})
                    if asst_text:
                        conversation_history.append({"role": "assistant", "text": asst_text})

                    turn += 1
                    await websocket.send_json({"type": "turn_complete"})
                    print(f"[LIVE] Turn {turn - 1} done, reconnecting...", flush=True)

                    current_narration_state = None
                    try:
                        msg = await asyncio.wait_for(websocket.receive(), timeout=0.1)
                        if "text" in msg:
                            data = json.loads(msg["text"])
                            if data.get("type") == "set_narration_state":
                                current_narration_state = data.get("state")
                                print(f"[LIVE] Narration state set: {current_narration_state.get('title', '?') if current_narration_state else 'None'}", flush=True)
                    except (asyncio.TimeoutError, Exception):
                        pass

            except Exception as exc:
                print(f"[LIVE] Session error: {exc}", flush=True)
                try:
                    await websocket.send_json({"type": "error", "message": f"Session error: {exc}"})
                except Exception:
                    pass
                break

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"[LIVE] Fatal: {exc}", flush=True)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
