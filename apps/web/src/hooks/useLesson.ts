import { create } from "zustand";
import type { Lesson, Scene, ProcessingStatus, ProcessingStep, StepStatus } from "@/types";

interface LessonStore {
  currentLesson: Lesson | null;
  scenes: Scene[];
  selectedSceneId: string | null;
  processingStatus: ProcessingStatus;

  setLesson: (lesson: Lesson) => void;
  setScenes: (scenes: Scene[]) => void;
  selectScene: (sceneId: string) => void;
  updateScene: (sceneId: string, updates: Partial<Scene>) => void;
  setProcessingStatus: (status: ProcessingStatus) => void;
  reset: () => void;
}

const initialProcessingStatus: ProcessingStatus = {
  current_step: "extraction",
  steps: {
    extraction: "pending",
    planning: "pending",
    scene_compilation: "pending",
    asset_generation: "pending",
    rendering: "pending",
  },
  message: "Waiting to start...",
};

export const useLessonStore = create<LessonStore>((set) => ({
  currentLesson: null,
  scenes: [],
  selectedSceneId: null,
  processingStatus: initialProcessingStatus,

  setLesson: (lesson) => set({ currentLesson: lesson }),

  setScenes: (scenes) =>
    set({
      scenes: scenes.sort((a, b) => a.scene_order - b.scene_order),
    }),

  selectScene: (sceneId) => set({ selectedSceneId: sceneId }),

  updateScene: (sceneId, updates) =>
    set((state) => ({
      scenes: state.scenes.map((s) =>
        s.id === sceneId ? { ...s, ...updates } : s
      ),
    })),

  setProcessingStatus: (status) => set({ processingStatus: status }),

  reset: () =>
    set({
      currentLesson: null,
      scenes: [],
      selectedSceneId: null,
      processingStatus: initialProcessingStatus,
    }),
}));

const statusStepMap: Record<string, { step: ProcessingStep; status: StepStatus }[]> = {
  created: [
    { step: "extraction", status: "pending" },
  ],
  extracting: [
    { step: "extraction", status: "active" },
  ],
  planning: [
    { step: "extraction", status: "complete" },
    { step: "planning", status: "active" },
  ],
  compiling: [
    { step: "extraction", status: "complete" },
    { step: "planning", status: "complete" },
    { step: "scene_compilation", status: "active" },
  ],
  generating_assets: [
    { step: "extraction", status: "complete" },
    { step: "planning", status: "complete" },
    { step: "scene_compilation", status: "complete" },
    { step: "asset_generation", status: "active" },
  ],
  rendering: [
    { step: "extraction", status: "complete" },
    { step: "planning", status: "complete" },
    { step: "scene_compilation", status: "complete" },
    { step: "asset_generation", status: "complete" },
    { step: "rendering", status: "active" },
  ],
  completed: [
    { step: "extraction", status: "complete" },
    { step: "planning", status: "complete" },
    { step: "scene_compilation", status: "complete" },
    { step: "asset_generation", status: "complete" },
    { step: "rendering", status: "complete" },
  ],
  error: [
    { step: "extraction", status: "error" },
  ],
};

const statusMessages: Record<string, string> = {
  created: "Lesson created, ready to process...",
  extracting: "Extracting concepts from source material...",
  planning: "Creating pedagogical lesson plan...",
  compiling: "Compiling scene specifications...",
  generating_assets: "Generating narration and visual assets...",
  rendering: "Rendering video...",
  completed: "Lesson is ready!",
  error: "An error occurred during processing.",
};

export function mapLessonStatusToProcessing(status: string): ProcessingStatus {
  const steps: Record<ProcessingStep, StepStatus> = {
    extraction: "pending",
    planning: "pending",
    scene_compilation: "pending",
    asset_generation: "pending",
    rendering: "pending",
  };

  const mappings = statusStepMap[status] || [];
  for (const { step, status: stepStatus } of mappings) {
    steps[step] = stepStatus;
  }

  const allSteps: ProcessingStep[] = [
    "extraction",
    "planning",
    "scene_compilation",
    "asset_generation",
    "rendering",
  ];
  const currentStep =
    allSteps.find((s) => steps[s] === "active") ||
    allSteps.find((s) => steps[s] === "pending") ||
    "extraction";

  return {
    current_step: currentStep,
    steps,
    message: statusMessages[status] || "Processing...",
  };
}
