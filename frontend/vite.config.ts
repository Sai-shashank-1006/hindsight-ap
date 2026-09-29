import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// With VITE_API_URL empty, the app calls its own origin and these proxies forward to FastAPI.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: true, // the backend's CORS allows :3000, so never drift to another port
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
      '/docs': { target: 'http://localhost:8000', changeOrigin: true },
      '/openapi.json': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  preview: {
    port: 3000,
  },
});
