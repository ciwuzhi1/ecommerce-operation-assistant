import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "电商运营助手",
  description: "AI 单品运营工作台",
};

/** 渲染 RootLayout 组件，集中展示根布局所需的数据、状态和操作入口。 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className="h-full antialiased"
    >
      <body className="min-h-full flex flex-col"><aside className="border-b border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">第 03 篇：基础业务体验。AI 自动生成、模型设置和 Agent 尚未接入；点击这些入口将看到阶段说明。请先完成建店、建商品、库存与经营数据录入。</aside>{children}</body>
    </html>
  );
}
