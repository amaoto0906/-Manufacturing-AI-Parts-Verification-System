import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base は環境で切替:
//  - 既定 "/ui/" : FastAPI が /ui で配信するローカル/オンプレ構成
//  - Vercel 等で単体配信する場合は環境変数 VITE_BASE=/ を設定する
// 開発時(npm run dev)は /api・/health をバックエンド(8077)へプロキシする。
export default defineConfig({
  base: process.env.VITE_BASE ?? "/ui/",
  plugins: [react()],
  build: {
    outDir: "dist",
    assetsDir: "static", // 画像アセット(assets/generated)と衝突させない
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8077",
      "/health": "http://127.0.0.1:8077",
    },
  },
});
