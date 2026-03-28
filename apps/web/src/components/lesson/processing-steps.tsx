"use client";

import {
  CheckCircle2,
  Circle,
  Loader2,
  AlertCircle,
  FileSearch,
  LayoutList,
  GitBranch,
  Layers,
  Image,
  Film,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ProcessingStep, StepStatus } from "@/types";

interface Step {
  key: ProcessingStep;
  label: string;
  description: string;
  icon: React.ElementType;
}

const STEPS: Step[] = [
  {
    key: "extraction",
    label: "Extraction",
    description: "Extracting content from source materials",
    icon: FileSearch,
  },
  {
    key: "planning",
    label: "Planning",
    description: "Creating lesson plan and scene structure",
    icon: LayoutList,
  },
  {
    key: "diagram_generation",
    label: "Diagram Generation",
    description: "Generating primary architecture diagram",
    icon: GitBranch,
  },
  {
    key: "scene_compilation",
    label: "Scene Compilation",
    description: "Compiling narration and visual descriptions",
    icon: Layers,
  },
  {
    key: "asset_generation",
    label: "Asset Generation",
    description: "Generating visual assets for scenes",
    icon: Image,
  },
  {
    key: "rendering",
    label: "Rendering",
    description: "Rendering the final lesson video",
    icon: Film,
  },
];

function StatusIcon({ status }: { status: StepStatus }) {
  switch (status) {
    case "complete":
      return <CheckCircle2 className="h-6 w-6 text-green-600" />;
    case "active":
      return <Loader2 className="h-6 w-6 text-primary animate-spin" />;
    case "error":
      return <AlertCircle className="h-6 w-6 text-destructive" />;
    default:
      return <Circle className="h-6 w-6 text-muted-foreground/40" />;
  }
}

interface ProcessingStepsProps {
  steps: Record<ProcessingStep, StepStatus>;
  message: string;
}

export function ProcessingSteps({ steps, message }: ProcessingStepsProps) {
  return (
    <div className="space-y-2">
      {STEPS.map((step, index) => {
        const status = steps[step.key];
        const isLast = index === STEPS.length - 1;

        return (
          <div key={step.key} className="flex gap-4">
            <div className="flex flex-col items-center">
              <StatusIcon status={status} />
              {!isLast && (
                <div
                  className={cn(
                    "w-0.5 flex-1 min-h-[2rem]",
                    status === "complete" ? "bg-green-600" : "bg-muted"
                  )}
                />
              )}
            </div>

            <div
              className={cn(
                "flex-1 pb-6 rounded-lg",
                status === "active" && "animate-pulse-slow"
              )}
            >
              <div className="flex items-center gap-2">
                <step.icon
                  className={cn(
                    "h-4 w-4",
                    status === "active"
                      ? "text-primary"
                      : status === "complete"
                      ? "text-green-600"
                      : "text-muted-foreground"
                  )}
                />
                <h4
                  className={cn(
                    "text-sm font-semibold",
                    status === "active"
                      ? "text-primary"
                      : status === "complete"
                      ? "text-green-700"
                      : "text-muted-foreground"
                  )}
                >
                  {step.label}
                </h4>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {status === "active" ? message : step.description}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
