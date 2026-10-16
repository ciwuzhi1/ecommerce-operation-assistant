"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** 渲染 GenerationJobAutoRefresh 组件，集中展示生成任务任务自动刷新所需的数据、状态和操作入口。 */
export function GenerationJobAutoRefresh({ active }: { active: boolean }) {
  const router = useRouter();

  useEffect(() => {
    if (!active) {
      return;
    }

    // 只在存在 pending/running 任务时刷新服务端数据；任务结束后停止轮询，避免工作台长期空转。
    const timer = window.setInterval(() => {
      router.refresh();
    }, 5000);

    return () => window.clearInterval(timer);
  }, [active, router]);

  return null;
}
