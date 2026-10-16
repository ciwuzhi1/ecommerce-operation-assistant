"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";


/** 渲染 AgentTaskAutoRefresh 组件，集中展示Agent任务自动刷新所需的数据、状态和操作入口。 */
export function AgentTaskAutoRefresh({ active }: { active: boolean }) {
  const router = useRouter();

  useEffect(() => {
    if (!active) {
      return;
    }
    const timer = window.setInterval(() => router.refresh(), 2000);
    return () => window.clearInterval(timer);
  }, [active, router]);

  return null;
}
