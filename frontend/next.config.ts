import type { NextConfig } from "next";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export', //指示 Next.js 進行靜態匯出
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
