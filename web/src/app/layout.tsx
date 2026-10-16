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
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
