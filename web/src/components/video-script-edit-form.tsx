import type { CreativePlan } from "@/types";

type VideoScriptEditFormProps = {
  productId: number;
  script: CreativePlan;
};

/** 渲染 VideoScriptEditForm 组件，集中展示视频script编辑表单所需的数据、状态和操作入口。 */
export function VideoScriptEditForm({ productId, script }: VideoScriptEditFormProps) {
  return (
    <form
      action={`/products/${productId}/creative-plans/${script.id}/video-script/update`}
      method="post"
      className="mt-4 grid gap-3 border-t border-slate-200 pt-4"
    >
      <label className="grid gap-1.5">
        <span className="text-xs font-medium text-slate-500">脚本标题</span>
        <input
          name="title"
          defaultValue={script.title}
          className="h-10 rounded-md border border-slate-200 px-3 text-sm outline-none focus:border-slate-400"
        />
      </label>

      <label className="grid gap-1.5">
        <span className="text-xs font-medium text-slate-500">测试角度</span>
        <textarea
          name="angle"
          defaultValue={planText(script.content, "angle")}
          rows={2}
          className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
        />
      </label>

      <div className="grid gap-3 md:grid-cols-[1fr_140px]">
        <label className="grid gap-1.5">
          <span className="text-xs font-medium text-slate-500">开头钩子</span>
          <input
            name="hook"
            defaultValue={planText(script.content, "hook")}
            className="h-10 rounded-md border border-slate-200 px-3 text-sm outline-none focus:border-slate-400"
          />
        </label>
        <label className="grid gap-1.5">
          <span className="text-xs font-medium text-slate-500">时长/秒</span>
          <input
            name="duration_seconds"
            type="number"
            min={15}
            max={60}
            defaultValue={planValue(script.content, "duration_seconds")}
            className="h-10 rounded-md border border-slate-200 px-3 text-sm outline-none focus:border-slate-400"
          />
        </label>
      </div>

      <label className="grid gap-1.5">
        {/* 分镜用 JSON 编辑是为了保留结构化镜头数据，后端会解析并写回 content.scenes。 */}
        <span className="text-xs font-medium text-slate-500">镜头分镜 JSON</span>
        <textarea
          name="scenes_json"
          defaultValue={JSON.stringify(planScenes(script.content), null, 2)}
          rows={10}
          className="resize-y rounded-md border border-slate-200 px-3 py-2 font-mono text-xs leading-5 outline-none focus:border-slate-400"
        />
      </label>

      <label className="grid gap-1.5">
        <span className="text-xs font-medium text-slate-500">卖点证明</span>
        <textarea
          name="selling_point_proof"
          defaultValue={planList(script.content, "selling_point_proof").join("\n")}
          rows={3}
          className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
        />
      </label>

      <label className="grid gap-1.5">
        <span className="text-xs font-medium text-slate-500">转化引导</span>
        <textarea
          name="cta"
          defaultValue={planText(script.content, "cta")}
          rows={2}
          className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
        />
      </label>

      <label className="grid gap-1.5">
        <span className="text-xs font-medium text-slate-500">视频生成提示词</span>
        <textarea
          name="video_prompt"
          defaultValue={planText(script.content, "video_prompt")}
          rows={3}
          className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
        />
      </label>

      <label className="grid gap-1.5">
        {/* 参考图、字幕、配音和剪辑备注都走可编辑字段，避免视频生成变成只读黑盒。 */}
        <span className="text-xs font-medium text-slate-500">参考图 URL</span>
        <textarea
          name="reference_images"
          defaultValue={planList(script.content, "reference_images").join("\n")}
          rows={3}
          placeholder="每行一张参考图，用于图生视频或保持商品外观一致"
          className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
        />
      </label>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="grid gap-1.5">
          <span className="text-xs font-medium text-slate-500">字幕</span>
          <textarea
            name="subtitle_lines"
            defaultValue={planList(script.content, "subtitle_lines").join("\n")}
            rows={4}
            className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
          />
        </label>
        <label className="grid gap-1.5">
          <span className="text-xs font-medium text-slate-500">配音文案</span>
          <textarea
            name="voiceover_text"
            defaultValue={planText(script.content, "voiceover_text")}
            rows={4}
            className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
          />
        </label>
      </div>

      <label className="grid gap-1.5">
        <span className="text-xs font-medium text-slate-500">剪辑备注</span>
        <textarea
          name="edit_notes"
          defaultValue={planText(script.content, "edit_notes")}
          rows={3}
          className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
        />
      </label>

      <button
        type="submit"
        className="inline-flex h-10 w-fit items-center justify-center rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
      >
        保存修改
      </button>
    </form>
  );
}

/** 方案文本，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function planText(content: Record<string, unknown>, key: string): string {
  const value = content[key];
  return typeof value === "string" ? value : "";
}

/** 方案值，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function planValue(content: Record<string, unknown>, key: string): string {
  const value = content[key];
  if (typeof value === "number") {
    return String(value);
  }
  return typeof value === "string" ? value : "";
}

/** 方案列表，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function planList(content: Record<string, unknown>, key: string): string[] {
  const value = content[key];
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

/** 方案scenes，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function planScenes(content: Record<string, unknown>): Array<{
  shot: string;
  visual: string;
  voiceover: string;
}> {
  // 分镜 content 可能为空或格式不完整，表单只渲染可安全编辑的 shot/visual/voiceover 字段。
  const scenes = content.scenes;
  if (!Array.isArray(scenes)) {
    return [];
  }

  return scenes
    .filter((scene): scene is Record<string, unknown> => Boolean(scene) && typeof scene === "object")
    .map((scene) => ({
      shot: typeof scene.shot === "string" ? scene.shot : "",
      visual: typeof scene.visual === "string" ? scene.visual : "",
      voiceover: typeof scene.voiceover === "string" ? scene.voiceover : "",
    }));
}
