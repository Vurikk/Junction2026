import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': process.env.SBANK_API_TARGET || 'http://127.0.0.1:8000' },
  },
});
