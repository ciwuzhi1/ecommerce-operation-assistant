import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 课堂使用 127.0.0.1；允许本机来源加载开发脚本及连接热更新服务。
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
