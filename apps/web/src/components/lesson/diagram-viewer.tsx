"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import {
  getDiagramData,
  getDiagramSvgUrl,
  type DiagramData,
  type WalkthroughState,
} from "@/lib/api";
import {
  ChevronLeft,
  ChevronRight,
  Play,
  Pause,
  RotateCcw,
  Maximize2,
  Minimize2,
} from "lucide-react";

interface DiagramViewerProps {
  lessonId: string;
  className?: string;
}

export function DiagramViewer({ lessonId, className }: DiagramViewerProps) {
  const [data, setData] = useState<DiagramData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentStateIndex, setCurrentStateIndex] = useState(-1);
  const [svgContent, setSvgContent] = useState<string>("");
  const [isPlaying, setIsPlaying] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getDiagramData(lessonId)
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Failed to load diagram");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [lessonId]);

  const loadSvg = useCallback(
    async (stateId?: string) => {
      try {
        const url = getDiagramSvgUrl(lessonId, stateId);
        const res = await fetch(url);
        if (!res.ok) throw new Error("SVG fetch failed");
        const text = await res.text();
        setSvgContent(text);
      } catch {
        setSvgContent("");
      }
    },
    [lessonId]
  );

  useEffect(() => {
    if (!data) return;
    const states = data.walkthrough_states;
    if (currentStateIndex < 0 || currentStateIndex >= states.length) {
      loadSvg();
    } else {
      loadSvg(states[currentStateIndex].state_id);
    }
  }, [data, currentStateIndex, loadSvg]);

  useEffect(() => {
    if (!isPlaying || !data) return;
    const states = data.walkthrough_states;
    if (currentStateIndex >= states.length - 1) {
      setIsPlaying(false);
      return;
    }
    const currentDuration =
      currentStateIndex >= 0
        ? states[currentStateIndex].duration_sec * 1000
        : 3000;
    timerRef.current = setTimeout(() => {
      setCurrentStateIndex((prev) => prev + 1);
    }, currentDuration);
    return () => clearTimeout(timerRef.current);
  }, [isPlaying, currentStateIndex, data]);

  const states = data?.walkthrough_states ?? [];
  const currentState: WalkthroughState | null =
    currentStateIndex >= 0 && currentStateIndex < states.length
      ? states[currentStateIndex]
      : null;

  const handlePrev = () => {
    setIsPlaying(false);
    setCurrentStateIndex((p) => Math.max(-1, p - 1));
  };

  const handleNext = () => {
    setIsPlaying(false);
    setCurrentStateIndex((p) => Math.min(states.length - 1, p + 1));
  };

  const handlePlayPause = () => {
    if (isPlaying) {
      setIsPlaying(false);
    } else {
      if (currentStateIndex >= states.length - 1) {
        setCurrentStateIndex(0);
      } else if (currentStateIndex < 0) {
        setCurrentStateIndex(0);
      }
      setIsPlaying(true);
    }
  };

  const handleReset = () => {
    setIsPlaying(false);
    setCurrentStateIndex(-1);
  };

  const toggleFullscreen = () => {
    if (!isFullscreen && containerRef.current) {
      containerRef.current.requestFullscreen?.();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen?.();
      setIsFullscreen(false);
    }
  };

  useEffect(() => {
    const handler = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", handler);
    return () => document.removeEventListener("fullscreenchange", handler);
  }, []);

  if (loading) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-xl border bg-muted/30 p-12",
          className
        )}
      >
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Loading diagram...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return null;
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        "flex flex-col rounded-xl border bg-white shadow-sm overflow-hidden",
        isFullscreen && "fixed inset-0 z-50 rounded-none",
        className
      )}
    >
      <div className="relative flex-1 min-h-0 bg-white flex items-center justify-center p-4">
        {svgContent ? (
          <div
            className="w-full h-full flex items-center justify-center [&>svg]:max-w-full [&>svg]:max-h-full [&>svg]:w-auto [&>svg]:h-auto"
            dangerouslySetInnerHTML={{ __html: svgContent }}
          />
        ) : (
          <div className="text-muted-foreground text-sm">
            No diagram available
          </div>
        )}

        <button
          onClick={toggleFullscreen}
          className="absolute top-3 right-3 p-1.5 rounded-md bg-white/80 hover:bg-white border shadow-sm transition-colors"
          title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
        >
          {isFullscreen ? (
            <Minimize2 className="h-4 w-4" />
          ) : (
            <Maximize2 className="h-4 w-4" />
          )}
        </button>
      </div>

      {currentState && (
        <div className="px-5 py-3 bg-slate-50 border-t">
          <h4 className="font-semibold text-sm text-slate-900">
            {currentState.title}
          </h4>
          <p className="text-sm text-slate-600 mt-1 leading-relaxed">
            {currentState.narration}
          </p>
          {currentState.user_question_hooks &&
            currentState.user_question_hooks.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {currentState.user_question_hooks.map((q, i) => (
                  <span
                    key={i}
                    className="inline-block text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded-full"
                  >
                    {q}
                  </span>
                ))}
              </div>
            )}
        </div>
      )}

      {states.length > 0 && (
        <div className="flex items-center gap-2 px-4 py-3 border-t bg-white">
          <button
            onClick={handleReset}
            className="p-1.5 rounded-md hover:bg-slate-100 transition-colors"
            title="Reset"
          >
            <RotateCcw className="h-4 w-4 text-slate-500" />
          </button>

          <button
            onClick={handlePrev}
            disabled={currentStateIndex <= -1}
            className="p-1.5 rounded-md hover:bg-slate-100 transition-colors disabled:opacity-30"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>

          <button
            onClick={handlePlayPause}
            className="p-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            {isPlaying ? (
              <Pause className="h-4 w-4" />
            ) : (
              <Play className="h-4 w-4" />
            )}
          </button>

          <button
            onClick={handleNext}
            disabled={currentStateIndex >= states.length - 1}
            className="p-1.5 rounded-md hover:bg-slate-100 transition-colors disabled:opacity-30"
          >
            <ChevronRight className="h-4 w-4" />
          </button>

          <div className="flex-1 flex items-center gap-1 mx-2">
            {states.map((s, i) => (
              <button
                key={s.state_id}
                onClick={() => {
                  setIsPlaying(false);
                  setCurrentStateIndex(i);
                }}
                className={cn(
                  "flex-1 h-1.5 rounded-full transition-all",
                  i === currentStateIndex
                    ? "bg-primary"
                    : i < currentStateIndex
                    ? "bg-primary/40"
                    : "bg-slate-200"
                )}
                title={s.title}
              />
            ))}
          </div>

          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {currentStateIndex >= 0
              ? `${currentStateIndex + 1}/${states.length}`
              : `Overview`}
          </span>
        </div>
      )}
    </div>
  );
}

interface WalkthroughStateListProps {
  states: WalkthroughState[];
  currentIndex: number;
  onSelect: (index: number) => void;
}

export function WalkthroughStateList({
  states,
  currentIndex,
  onSelect,
}: WalkthroughStateListProps) {
  return (
    <div className="space-y-1">
      {states.map((state, i) => (
        <button
          key={state.state_id}
          onClick={() => onSelect(i)}
          className={cn(
            "w-full text-left px-3 py-2 rounded-lg text-sm transition-colors",
            i === currentIndex
              ? "bg-primary/10 text-primary font-medium"
              : "hover:bg-slate-50 text-slate-600"
          )}
        >
          <span className="text-xs text-muted-foreground mr-2">{i + 1}.</span>
          {state.title}
        </button>
      ))}
    </div>
  );
}
