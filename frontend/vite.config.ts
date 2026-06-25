import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// ビルド成果物は FastAPI が /ui で配信するため base を /ui/ に固定。
// 開発時(npm run dev)は /api・/health をバックエンド(8077)へプロキシする。
export default defineConfig({
  base: "/ui/",
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
