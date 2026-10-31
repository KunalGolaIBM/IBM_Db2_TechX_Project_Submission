import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    target: 'es2022',
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.indexOf('node_modules') === -1) return
          if (id.indexOf('@react-three/postprocessing') !== -1 || id.indexOf('/postprocessing/') !== -1) return 'postfx'
          if (id.indexOf('@react-three/drei') !== -1 || id.indexOf('/maath/') !== -1) return 'scene-utils'
          if (id.indexOf('/three/') !== -1 || id.indexOf('@react-three/fiber') !== -1) return 'three-stack'
        },
      },
    },
  },
})
