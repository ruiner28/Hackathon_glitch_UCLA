import type { Scene, SceneRenderMode } from "@/types";

/** Effective output: whether the pipeline will try Veo for this scene. */
export function sceneWillUseVeo(scene: Scene): boolean {
  const spec = scene.scene_spec_json;
  if (!spec) return false;
  const rm = (spec.render_mode as string) || "auto";
  if (rm === "force_static") return false;
  if (rm === "force_veo") return true;
  return !!(spec.veo_eligible);
}

export function sceneRenderMode(scene: Scene): SceneRenderMode {
  const rm = scene.scene_spec_json?.render_mode as SceneRenderMode | undefined;
  if (rm === "force_static" || rm === "force_veo") return rm;
  return "auto";
}
