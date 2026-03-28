"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { getLiveWebSocketUrl } from "@/lib/api";
import { Mic, MicOff, X, MessageCircle, Volume2 } from "lucide-react";

interface LiveChatProps {
  lessonId: string;
  currentStateId?: string;
  className?: string;
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
  currentStateId,
  className,
}: LiveChatProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("idle");
  const [speakingState, setSpeakingState] = useState<SpeakingState>("idle");
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const isPlayingRef = useRef(false);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const nextPlayTimeRef = useRef(0);
  const micGateRef = useRef(false);

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
    stopMic();
    if (wsRef.current) {
      try {
        wsRef.current.send(JSON.stringify({ type: "end" }));
      } catch {}
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
      streamRef.current = stream;

      const audioCtx = new AudioContext();
      audioContextRef.current = audioCtx;
      const nativeRate = audioCtx.sampleRate;

      const wsUrl = getLiveWebSocketUrl(lessonId);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionState("connected");

        const source = audioCtx.createMediaStreamSource(stream);
        sourceRef.current = source;

        const processor = audioCtx.createScriptProcessor(4096, 1, 1);
        processorRef.current = processor;

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
        processor.connect(audioCtx.destination);
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
              setTimeout(() => {
                if (wsRef.current?.readyState === WebSocket.OPEN) {
                  micGateRef.current = true;
                  setSpeakingState("listening");
                }
              }, delay);
              break;
            }

            case "error":
              setError(msg.message || "Connection error");
              disconnect();
              break;

            case "connected":
              break;
          }
        } catch {}
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

  const handleToggle = () => {
    if (isOpen && connectionState === "connected") {
      disconnect();
    }
    setIsOpen((o) => !o);
  };

  const handleConnect = () => {
    if (connectionState === "connected") {
      disconnect();
    } else {
      connect();
    }
  };

  const sendTextMessage = (text: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      micGateRef.current = false;
      wsRef.current.send(JSON.stringify({ type: "text", text }));
      setTranscript((prev) => [
        ...prev,
        { role: "user", text, timestamp: Date.now() },
      ]);
      setSpeakingState("thinking");
    }
  };

  const stateColors: Record<SpeakingState, string> = {
    idle: "bg-slate-400",
    listening: "bg-green-500",
    thinking: "bg-yellow-500",
    speaking: "bg-blue-500",
  };

  const stateLabels: Record<SpeakingState, string> = {
    idle: "Not connected",
    listening: "Listening...",
    thinking: "Reconnecting...",
    speaking: "Speaking...",
  };

  return (
    <>
      <button
        onClick={handleToggle}
        className={cn(
          "fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full shadow-lg transition-all hover:scale-105",
          connectionState === "connected"
            ? "bg-green-600 text-white animate-pulse"
            : "bg-primary text-primary-foreground",
        )}
        title="Talk to your diagram"
      >
        {connectionState === "connected" ? (
          <Volume2 className="h-6 w-6" />
        ) : (
          <MessageCircle className="h-6 w-6" />
        )}
      </button>

      {isOpen && (
        <div
          className={cn(
            "fixed bottom-24 right-6 z-50 flex w-96 flex-col rounded-2xl border bg-white shadow-2xl overflow-hidden",
            "max-h-[70vh]",
            className,
          )}
        >
          <div className="flex items-center justify-between border-b bg-slate-50 px-4 py-3">
            <div className="flex items-center gap-2">
              <div
                className={cn(
                  "h-2.5 w-2.5 rounded-full transition-colors",
                  stateColors[speakingState],
                )}
              />
              <span className="text-sm font-semibold text-slate-800">
                Ask about the diagram
              </span>
            </div>
            <button
              onClick={handleToggle}
              className="rounded-md p-1 hover:bg-slate-200 transition-colors"
            >
              <X className="h-4 w-4 text-slate-500" />
            </button>
          </div>

          <div className="flex items-center gap-2 border-b bg-slate-50/50 px-4 py-2">
            <span className="text-xs text-slate-500">
              {stateLabels[speakingState]}
            </span>
            {speakingState === "listening" && (
              <div className="flex gap-0.5">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="h-3 w-1 rounded-full bg-green-500"
                    style={{
                      animation: `pulse 1s ease-in-out ${i * 0.15}s infinite`,
                    }}
                  />
                ))}
              </div>
            )}
            {speakingState === "speaking" && (
              <div className="flex gap-0.5">
                {[0, 1, 2, 3, 4].map((i) => (
                  <div
                    key={i}
                    className="h-3 w-1 rounded-full bg-blue-500"
                    style={{
                      animation: `pulse 0.6s ease-in-out ${i * 0.1}s infinite`,
                    }}
                  />
                ))}
              </div>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-[200px] max-h-[400px]">
            {connectionState === "idle" && transcript.length === 0 && (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Mic className="h-10 w-10 text-slate-300 mb-3" />
                <p className="text-sm text-slate-500 font-medium">
                  Voice chat with Gemini
                </p>
                <p className="text-xs text-slate-400 mt-1 max-w-[240px]">
                  Ask questions about the diagram in real-time. Gemini can see
                  what you&apos;re viewing and explain it.
                </p>
              </div>
            )}

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
                    "max-w-[85%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed",
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

          {error && (
            <div className="mx-4 mb-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">
              {error}
            </div>
          )}

          {connectionState === "connected" && (
            <div className="border-t px-3 py-2 flex flex-wrap gap-1.5">
              {[
                "Explain this simpler",
                "What happens next?",
                "Why is this important?",
                "Give me an example",
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => sendTextMessage(q)}
                  className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1 rounded-full transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          )}

          <div className="border-t px-4 py-3 bg-slate-50">
            <button
              onClick={handleConnect}
              disabled={connectionState === "connecting"}
              className={cn(
                "w-full flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold transition-all",
                connectionState === "connected"
                  ? "bg-red-100 text-red-700 hover:bg-red-200"
                  : connectionState === "connecting"
                    ? "bg-slate-200 text-slate-400 cursor-wait"
                    : "bg-primary text-primary-foreground hover:bg-primary/90",
              )}
            >
              {connectionState === "connecting" ? (
                <>
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Connecting...
                </>
              ) : connectionState === "connected" ? (
                <>
                  <MicOff className="h-4 w-4" />
                  End Conversation
                </>
              ) : (
                <>
                  <Mic className="h-4 w-4" />
                  Start Talking
                </>
              )}
            </button>
          </div>
        </div>
      )}

      <style jsx global>{`
        @keyframes pulse {
          0%,
          100% {
            transform: scaleY(0.4);
          }
          50% {
            transform: scaleY(1);
          }
        }
      `}</style>
    </>
  );
}
