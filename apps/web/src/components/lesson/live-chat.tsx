"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { cn } from "@/lib/utils";
import { getLiveWebSocketUrl } from "@/lib/api";
import {
  GeminiLiveOrb,
  mapToOrbState,
} from "@/components/lesson/gemini-live-orb";
import {
  AlertCircle,
  AudioLines,
  Brain,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Mic,
  MicOff,
  Sparkles,
  Volume2,
} from "lucide-react";
import type { WalkthroughState } from "@/lib/api";

export interface ComponentQuestion {
  componentId: string;
  label: string;
  timestamp: number;
}

interface LiveChatProps {
  lessonId: string;
  currentStateId?: string;
  className?: string;
  /** When embedded in the diagram, the orb stays with the canvas (and fullscreen). */
  placement?: "diagram" | "viewport";
  walkthroughStates?: WalkthroughState[];
  currentWalkthroughIndex?: number;
  onAdvanceState?: (index: number) => void;
  componentQuestion?: ComponentQuestion | null;
}

type ConnectionState = "idle" | "connecting" | "connected" | "error";
type SpeakingState = "idle" | "listening" | "thinking" | "speaking";

interface TranscriptEntry {
  role: "user" | "assistant";
  text: string;
  timestamp: number;
}

const GEMINI_OUTPUT_SAMPLE_RATE = 24000;
const TARGET_MIC_RATE = 16000;

function downsampleBuffer(
  buffer: Float32Array,
  inputRate: number,
  outputRate: number,
): Int16Array {
  if (inputRate === outputRate) {
    const result = new Int16Array(buffer.length);
    for (let i = 0; i < buffer.length; i++) {
      const s = Math.max(-1, Math.min(1, buffer[i]));
      result[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return result;
  }

  const ratio = inputRate / outputRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Int16Array(newLength);

  for (let i = 0; i < newLength; i++) {
    const srcIdx = i * ratio;
    const low = Math.floor(srcIdx);
    const high = Math.min(low + 1, buffer.length - 1);
    const frac = srcIdx - low;
    const sample = buffer[low] * (1 - frac) + buffer[high] * frac;
    const clamped = Math.max(-1, Math.min(1, sample));
    result[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
  }

  return result;
}

export function LiveChat({
  lessonId,
  currentStateId: _unusedCurrentStateId,
  className,
  placement = "diagram",
  walkthroughStates,
  currentWalkthroughIndex,
  onAdvanceState,
  componentQuestion,
}: LiveChatProps) {
  void _unusedCurrentStateId;
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("idle");
  const [speakingState, setSpeakingState] = useState<SpeakingState>("idle");
  const guidedPendingRef = useRef(false);
  const sendNarrateStateRef = useRef<(idx: number) => void>(() => {});
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const muteGainRef = useRef<GainNode | null>(null);
  const isPlayingRef = useRef(false);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const nextPlayTimeRef = useRef(0);
  const micGateRef = useRef(false);
  const liveSessionRef = useRef(0);

  const scrollToBottom = useCallback(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(scrollToBottom, [transcript, scrollToBottom]);

  const schedulePlayback = useCallback((pcmFloat: Float32Array) => {
    const ctx = audioContextRef.current;
    if (!ctx || ctx.state === "closed") return;

    if (ctx.state === "suspended") {
      ctx.resume().catch(() => {});
    }

    const buffer = ctx.createBuffer(
      1,
      pcmFloat.length,
      GEMINI_OUTPUT_SAMPLE_RATE,
    );
    buffer.getChannelData(0).set(pcmFloat);
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(ctx.destination);

    const now = ctx.currentTime;
    const startTime = Math.max(now, nextPlayTimeRef.current);
    src.start(startTime);
    nextPlayTimeRef.current = startTime + buffer.duration;

    src.onended = () => {
      if (ctx.currentTime >= nextPlayTimeRef.current - 0.05) {
        isPlayingRef.current = false;
      }
    };
  }, []);

  const playAudioChunk = useCallback(
    (pcmB64: string) => {
      micGateRef.current = false;

      const raw = atob(pcmB64);
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) {
        bytes[i] = raw.charCodeAt(i);
      }

      const int16 = new Int16Array(bytes.buffer);
      const float32 = new Float32Array(int16.length);
      for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768;
      }

      if (!isPlayingRef.current) {
        isPlayingRef.current = true;
        nextPlayTimeRef.current = 0;
        setSpeakingState("speaking");
      }

      schedulePlayback(float32);
    },
    [schedulePlayback],
  );

  const stopMic = useCallback(() => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (muteGainRef.current) {
      muteGainRef.current.disconnect();
      muteGainRef.current = null;
    }
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    liveSessionRef.current += 1;
    stopMic();
    if (wsRef.current) {
      try {
        wsRef.current.send(JSON.stringify({ type: "end" }));
      } catch {
        /* ignore */
      }
      wsRef.current.close();
      wsRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    isPlayingRef.current = false;
    nextPlayTimeRef.current = 0;
    micGateRef.current = false;
    setConnectionState("idle");
    setSpeakingState("idle");
  }, [stopMic]);

  const connect = useCallback(async () => {
    const sessionId = ++liveSessionRef.current;
    setError(null);
    setConnectionState("connecting");
    setTranscript([]);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      if (sessionId !== liveSessionRef.current) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      streamRef.current = stream;

      const audioCtx = new AudioContext();
      if (sessionId !== liveSessionRef.current) {
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        audioCtx.close().catch(() => {});
        return;
      }
      audioContextRef.current = audioCtx;
      const nativeRate = audioCtx.sampleRate;

      const wsUrl = getLiveWebSocketUrl(lessonId);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (sessionId !== liveSessionRef.current) return;
        const ctx = audioContextRef.current;
        if (!ctx || ctx.state === "closed") return;

        setConnectionState("connected");

        const source = ctx.createMediaStreamSource(stream);
        sourceRef.current = source;

        const processor = ctx.createScriptProcessor(4096, 1, 1);
        processorRef.current = processor;

        const muteGain = ctx.createGain();
        muteGain.gain.value = 0;
        muteGainRef.current = muteGain;

        processor.onaudioprocess = (e: AudioProcessingEvent) => {
          if (ws.readyState !== WebSocket.OPEN) return;
          if (!micGateRef.current) return;
          const inputData = e.inputBuffer.getChannelData(0);
          const downsampled = downsampleBuffer(
            inputData,
            nativeRate,
            TARGET_MIC_RATE,
          );
          ws.send(downsampled.buffer);
        };

        source.connect(processor);
        processor.connect(muteGain);
        muteGain.connect(ctx.destination);
      };

      ws.onmessage = (event) => {
        if (typeof event.data !== "string") return;
        try {
          const msg = JSON.parse(event.data);

          switch (msg.type) {
            case "audio":
              playAudioChunk(msg.data);
              break;

            case "transcript":
              if (msg.text) {
                setTranscript((prev) => {
                  const last = prev[prev.length - 1];
                  if (last && last.role === "assistant") {
                    return [
                      ...prev.slice(0, -1),
                      { ...last, text: last.text + msg.text },
                    ];
                  }
                  return [
                    ...prev,
                    {
                      role: "assistant",
                      text: msg.text,
                      timestamp: Date.now(),
                    },
                  ];
                });
              }
              break;

            case "input_transcript":
              if (msg.text) {
                setTranscript((prev) => {
                  const last = prev[prev.length - 1];
                  if (last && last.role === "user") {
                    return [
                      ...prev.slice(0, -1),
                      { ...last, text: last.text + msg.text },
                    ];
                  }
                  return [
                    ...prev,
                    { role: "user", text: msg.text, timestamp: Date.now() },
                  ];
                });
                setSpeakingState("thinking");
              }
              break;

            case "turn_complete":
              setSpeakingState("thinking");
              break;

            case "session_ready": {
              const ctx = audioContextRef.current;
              const remaining = ctx
                ? Math.max(0, nextPlayTimeRef.current - ctx.currentTime)
                : 0;
              const delay = Math.max(300, remaining * 1000 + 300);

              if (guidedPendingRef.current) {
                guidedPendingRef.current = false;
                setTimeout(() => {
                  sendNarrateStateRef.current(0);
                }, delay);
              } else {
                setTimeout(() => {
                  if (wsRef.current?.readyState === WebSocket.OPEN) {
                    micGateRef.current = true;
                    setSpeakingState("listening");
                  }
                }, delay);
              }
              break;
            }

            case "error":
              setError(msg.message || "Connection error");
              disconnect();
              break;

            case "connected":
              break;
          }
        } catch {
          /* ignore malformed */
        }
      };

      ws.onerror = () => {
        setError(
          "WebSocket connection failed. Make sure the API is running on port 8000.",
        );
        setConnectionState("error");
      };

      ws.onclose = () => {
        setConnectionState("idle");
        setSpeakingState("idle");
        stopMic();
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to connect";
      if (msg.includes("Permission") || msg.includes("NotAllowed")) {
        setError(
          "Microphone access denied. Please allow mic access and try again.",
        );
      } else {
        setError(msg);
      }
      setConnectionState("error");
    }
  }, [lessonId, disconnect, stopMic, playAudioChunk]);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  const sendTextMessage = useCallback((text: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      micGateRef.current = false;
      wsRef.current.send(JSON.stringify({ type: "text", text }));
      setTranscript((prev) => [
        ...prev,
        { role: "user", text, timestamp: Date.now() },
      ]);
      setSpeakingState("thinking");
    }
  }, []);

  const sendNarrateState = useCallback(
    (stateIdx: number) => {
      if (!walkthroughStates || !wsRef.current) return;
      const state = walkthroughStates[stateIdx];
      if (!state) return;

      const payload = {
        type: "narrate_state",
        state: {
          title: state.title,
          narration: state.narration,
          step_number: stateIdx + 1,
          total_steps: walkthroughStates.length,
          focus_regions: state.focus_regions || [],
          highlight_paths: state.highlight_paths || [],
        },
      };

      micGateRef.current = false;
      wsRef.current.send(JSON.stringify(payload));
      setTranscript((prev) => [
        ...prev,
        {
          role: "user",
          text: `[Step ${stateIdx + 1}/${walkthroughStates.length}: ${state.title}]`,
          timestamp: Date.now(),
        },
      ]);
      setSpeakingState("thinking");
    },
    [walkthroughStates],
  );

  useEffect(() => {
    sendNarrateStateRef.current = sendNarrateState;
  }, [sendNarrateState]);

  const startGuidedTour = useCallback(async () => {
    if (!walkthroughStates?.length) return;
    guidedPendingRef.current = true;
    onAdvanceState?.(0);

    if (connectionState !== "connected") {
      await connect();
    } else {
      sendNarrateStateRef.current(0);
      guidedPendingRef.current = false;
    }
  }, [walkthroughStates, connectionState, connect, onAdvanceState]);

  const handleGuidedNext = () => {
    if (
      !walkthroughStates ||
      currentWalkthroughIndex === undefined ||
      speakingState === "speaking"
    )
      return;
    const next = Math.min(
      walkthroughStates.length - 1,
      currentWalkthroughIndex + 1,
    );
    onAdvanceState?.(next);
    sendNarrateState(next);
  };

  const handleGuidedPrev = () => {
    if (
      !walkthroughStates ||
      currentWalkthroughIndex === undefined ||
      speakingState === "speaking"
    )
      return;
    const prev = Math.max(0, currentWalkthroughIndex - 1);
    onAdvanceState?.(prev);
    sendNarrateState(prev);
  };

  const lastComponentQuestionTs = useRef(0);

  useEffect(() => {
    if (
      !componentQuestion ||
      componentQuestion.timestamp <= lastComponentQuestionTs.current
    )
      return;
    lastComponentQuestionTs.current = componentQuestion.timestamp;

    const question = `Tell me about the "${componentQuestion.label}" component — what role does it play and how does it work?`;

    if (connectionState === "connected") {
      sendTextMessage(question);
    } else if (connectionState === "idle" || connectionState === "error") {
      const origConnect = connect;
      (async () => {
        if (walkthroughStates?.length) {
          await startGuidedTour();
        } else {
          await origConnect();
        }
        const waitForReady = () =>
          new Promise<void>((resolve) => {
            const check = setInterval(() => {
              if (wsRef.current?.readyState === WebSocket.OPEN) {
                clearInterval(check);
                resolve();
              }
            }, 100);
            setTimeout(() => {
              clearInterval(check);
              resolve();
            }, 5000);
          });
        await waitForReady();
        setTimeout(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: "text", text: question }));
            setTranscript((prev) => [
              ...prev,
              { role: "user", text: question, timestamp: Date.now() },
            ]);
            setSpeakingState("thinking");
          }
        }, 500);
      })();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [componentQuestion]);

  const handleOrbClick = () => {
    if (connectionState === "connected") {
      disconnect();
    } else if (connectionState !== "connecting") {
      if (walkthroughStates?.length) {
        void startGuidedTour();
      } else {
        void connect();
      }
    }
  };

  const statusUi = (() => {
    if (connectionState === "connecting") {
      return {
        icon: <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2.5} />,
        title: "Connecting",
        subtitle: "Session & microphone",
        pill: "border-amber-200/90 bg-gradient-to-br from-amber-50 via-white to-orange-50/90 text-amber-950 shadow-md shadow-amber-100/40",
        iconWrap: "bg-amber-100 text-amber-700 ring-2 ring-amber-300/40",
        activity: null as ReactNode,
      };
    }
    if (connectionState === "error") {
      return {
        icon: <AlertCircle className="h-3.5 w-3.5" strokeWidth={2.5} />,
        title: "Connection issue",
        subtitle: "Check API or try again",
        pill: "border-red-200/90 bg-gradient-to-br from-red-50 to-rose-50/95 text-red-900 shadow-md shadow-red-100/30",
        iconWrap: "bg-red-100 text-red-700 ring-2 ring-red-300/35",
        activity: null as ReactNode,
      };
    }
    if (connectionState === "idle") {
      const guided = !!walkthroughStates?.length;
      return {
        icon: guided ? (
          <Sparkles className="h-3.5 w-3.5" strokeWidth={2.5} />
        ) : (
          <Mic className="h-3.5 w-3.5" strokeWidth={2.5} />
        ),
        title: guided ? "Guided tour" : "Voice chat",
        subtitle: guided ? "Tap the orb to begin" : "Tap the orb to talk",
        pill: guided
          ? "border-indigo-200/90 bg-gradient-to-br from-indigo-50 via-violet-50/80 to-white text-indigo-950 shadow-md shadow-indigo-100/35"
          : "border-slate-200/90 bg-gradient-to-br from-slate-50 to-white text-slate-800 shadow-md shadow-slate-200/30",
        iconWrap: guided
          ? "bg-indigo-100 text-indigo-700 ring-2 ring-indigo-300/35"
          : "bg-slate-100 text-slate-600 ring-2 ring-slate-200/50",
        activity: null as ReactNode,
      };
    }
    if (connectionState === "connected") {
      if (speakingState === "listening") {
        return {
          icon: <AudioLines className="h-3.5 w-3.5" strokeWidth={2.5} />,
          title: "Listening",
          subtitle: "Speak when you're ready",
          pill: "border-emerald-200/90 bg-gradient-to-br from-emerald-50 via-teal-50/70 to-white text-emerald-950 shadow-md shadow-emerald-100/40",
          iconWrap:
            "bg-emerald-100 text-emerald-700 ring-2 ring-emerald-400/45",
          activity: (
            <span className="flex h-3.5 items-end gap-0.5" aria-hidden>
              <span className="h-1.5 w-0.5 animate-pulse rounded-sm bg-emerald-600/90 [animation-duration:1s]" />
              <span className="h-2.5 w-0.5 animate-pulse rounded-sm bg-emerald-600/90 [animation-duration:1s] [animation-delay:140ms]" />
              <span className="h-3.5 w-0.5 animate-pulse rounded-sm bg-emerald-600/90 [animation-duration:1s] [animation-delay:280ms]" />
            </span>
          ),
        };
      }
      if (speakingState === "thinking") {
        return {
          icon: <Brain className="h-3.5 w-3.5" strokeWidth={2.5} />,
          title: "Thinking",
          subtitle: "Working on a response",
          pill: "border-amber-200/90 bg-gradient-to-br from-amber-50 via-amber-50/50 to-orange-50/80 text-amber-950 shadow-md shadow-amber-100/35",
          iconWrap:
            "bg-amber-100 text-amber-700 ring-2 ring-amber-400/40 animate-pulse",
          activity: (
            <span className="flex gap-1">
              <span className="h-1 w-1 rounded-full bg-amber-500 animate-bounce [animation-duration:1s]" />
              <span className="h-1 w-1 rounded-full bg-amber-500 animate-bounce [animation-duration:1s] [animation-delay:150ms]" />
              <span className="h-1 w-1 rounded-full bg-amber-500 animate-bounce [animation-duration:1s] [animation-delay:300ms]" />
            </span>
          ),
        };
      }
      if (speakingState === "speaking") {
        return {
          icon: <Volume2 className="h-3.5 w-3.5" strokeWidth={2.5} />,
          title: "Speaking",
          subtitle: "Gemini is responding",
          pill: "border-violet-200/90 bg-gradient-to-br from-violet-50 via-fuchsia-50/60 to-white text-violet-950 shadow-md shadow-violet-100/40",
          iconWrap:
            "bg-violet-100 text-violet-700 ring-2 ring-violet-400/45 shadow-sm",
          activity: (
            <span className="flex h-3.5 items-end gap-0.5" aria-hidden>
              <span className="h-3.5 w-0.5 animate-pulse rounded-sm bg-violet-600/90 [animation-duration:0.75s]" />
              <span className="h-2.5 w-0.5 animate-pulse rounded-sm bg-violet-600/90 [animation-duration:0.75s] [animation-delay:100ms]" />
              <span className="h-1.5 w-0.5 animate-pulse rounded-sm bg-violet-600/90 [animation-duration:0.75s] [animation-delay:200ms]" />
            </span>
          ),
        };
      }
      return {
        icon: <Sparkles className="h-3.5 w-3.5" strokeWidth={2.5} />,
        title: "Live",
        subtitle: "Session active",
        pill: "border-sky-200/90 bg-gradient-to-br from-sky-50 to-white text-sky-950 shadow-md shadow-sky-100/30",
        iconWrap: "bg-sky-100 text-sky-700 ring-2 ring-sky-300/40",
        activity: null as ReactNode,
      };
    }
    return {
      icon: <Mic className="h-3.5 w-3.5 opacity-50" />,
      title: "",
      subtitle: "",
      pill: "border-slate-200 bg-white/90 text-slate-600",
      iconWrap: "bg-slate-100 text-slate-500",
      activity: null as ReactNode,
    };
  })();

  const rootPlacement =
    placement === "viewport"
      ? "fixed bottom-6 right-6 z-50"
      : "relative";

  return (
    <div
      className={cn(
        rootPlacement,
        "flex flex-col items-end gap-2 text-left",
        className,
      )}
    >
      <div
        role="status"
        aria-live="polite"
        className={cn(
          "flex max-w-[17rem] items-center gap-2.5 rounded-2xl border px-2.5 py-2 text-left shadow-sm backdrop-blur-md transition-all duration-300",
          statusUi.pill,
        )}
      >
        <span
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl",
            statusUi.iconWrap,
          )}
        >
          {statusUi.icon}
        </span>
        <div className="min-w-0 flex-1">
          {connectionState === "connected" && walkthroughStates?.length ? (
            <span className="mb-0.5 block text-[10px] font-semibold uppercase tracking-[0.14em] text-indigo-600/95">
              Guided
            </span>
          ) : null}
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <span className="text-sm font-semibold leading-tight tracking-tight">
              {statusUi.title}
            </span>
            {statusUi.activity}
          </div>
          {statusUi.subtitle ? (
            <span className="mt-0.5 block text-[11px] font-medium leading-snug text-current/70">
              {statusUi.subtitle}
            </span>
          ) : null}
        </div>
      </div>

      <div className="flex items-center gap-2">
        {connectionState === "connected" &&
          walkthroughStates &&
          walkthroughStates.length > 0 &&
          currentWalkthroughIndex !== undefined && (
            <>
              <button
                type="button"
                onClick={handleGuidedPrev}
                disabled={
                  currentWalkthroughIndex <= 0 || speakingState === "speaking"
                }
                className="rounded-full border border-slate-200 bg-white/95 p-2 shadow-sm backdrop-blur-sm transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                title="Previous step"
              >
                <ChevronLeft className="h-4 w-4 text-slate-700" />
              </button>
            </>
          )}

        <button
          type="button"
          onClick={handleOrbClick}
          disabled={connectionState === "connecting"}
          className={cn(
            "flex h-[4.25rem] w-[4.25rem] shrink-0 items-center justify-center rounded-full border-0 bg-transparent p-0 shadow-none outline-none",
            "transition-transform hover:scale-[1.04] active:scale-[0.98] disabled:opacity-70",
            "focus-visible:ring-2 focus-visible:ring-violet-400 focus-visible:ring-offset-2",
          )}
          title={
            connectionState === "connected"
              ? "End voice session"
              : walkthroughStates?.length
                ? "Start guided diagram tour — Gemini Live"
                : "Talk to your diagram — Gemini Live"
          }
        >
          <GeminiLiveOrb
            state={mapToOrbState(connectionState, speakingState)}
            size={52}
          />
        </button>

        {connectionState === "connected" &&
          walkthroughStates &&
          walkthroughStates.length > 0 &&
          currentWalkthroughIndex !== undefined && (
            <>
              <button
                type="button"
                onClick={handleGuidedNext}
                disabled={
                  currentWalkthroughIndex >= walkthroughStates.length - 1 ||
                  speakingState === "speaking"
                }
                className="rounded-full border border-slate-200 bg-white/95 p-2 shadow-sm backdrop-blur-sm transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                title="Next step"
              >
                <ChevronRight className="h-4 w-4 text-slate-700" />
              </button>
            </>
          )}
      </div>

      {connectionState === "connected" &&
        walkthroughStates &&
        currentWalkthroughIndex !== undefined && (
          <div className="w-full max-w-[16rem] rounded-xl border border-indigo-200/80 bg-indigo-50/90 px-2.5 py-2 text-xs text-indigo-900 shadow-sm backdrop-blur-sm">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="font-semibold">
                Step {currentWalkthroughIndex + 1}/{walkthroughStates.length}
              </span>
              <span className="truncate text-indigo-600">
                {walkthroughStates[currentWalkthroughIndex]?.title}
              </span>
            </div>
            <div className="flex gap-0.5">
              {walkthroughStates.map((_, i) => (
                <div
                  key={i}
                  className={cn(
                    "h-1 flex-1 rounded-full transition-colors",
                    i <= currentWalkthroughIndex
                      ? "bg-indigo-500"
                      : "bg-indigo-200",
                  )}
                />
              ))}
            </div>
          </div>
        )}

      {error ? (
        <div className="max-w-[16rem] rounded-lg border border-red-200 bg-red-50/95 px-2.5 py-1.5 text-[11px] text-red-800 shadow-sm backdrop-blur-sm">
          {error}
        </div>
      ) : null}

      {transcript.length > 0 && (
        <details className="w-full max-w-[min(100%,18rem)] rounded-xl border border-slate-200/90 bg-white/95 shadow-sm backdrop-blur-sm">
          <summary className="cursor-pointer select-none px-3 py-2 text-xs font-medium text-slate-600">
            Transcript ({transcript.length})
          </summary>
          <div className="max-h-[220px] space-y-2 overflow-y-auto border-t border-slate-100 px-3 py-2">
            {transcript.map((entry, i) => (
              <div
                key={i}
                className={cn(
                  "flex",
                  entry.role === "user" ? "justify-end" : "justify-start",
                )}
              >
                <div
                  className={cn(
                    "max-w-[95%] rounded-2xl px-2.5 py-1.5 text-[11px] leading-relaxed",
                    entry.role === "user"
                      ? "bg-primary text-primary-foreground rounded-br-md"
                      : "bg-slate-100 text-slate-800 rounded-bl-md",
                  )}
                >
                  {entry.text}
                </div>
              </div>
            ))}
            <div ref={transcriptEndRef} />
          </div>
        </details>
      )}

      {connectionState === "connecting" && (
        <p className="text-[11px] text-slate-500">Preparing microphone…</p>
      )}

      {connectionState === "connected" && (
        <button
          type="button"
          onClick={() => disconnect()}
          className="inline-flex items-center gap-1.5 rounded-full border border-red-200 bg-red-50/95 px-3 py-1 text-[11px] font-medium text-red-800 shadow-sm backdrop-blur-sm hover:bg-red-100/90"
        >
          <MicOff className="h-3 w-3" />
          End {walkthroughStates?.length ? "tour" : "session"}
        </button>
      )}
    </div>
  );
}
