import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    babel({ presets: [reactCompilerPreset()] })
  ],
  server: {
    proxy: {
      // In development the browser talks only to localhost:5173, and Vite
      // forwards these paths onward. That is the same job nginx does in
      // production, so the app never needs an absolute URL in either place.
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8081',
        ws: true,
      },
    },
  },
})
