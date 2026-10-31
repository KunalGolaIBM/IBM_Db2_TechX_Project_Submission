import { useEffect, useRef } from 'react'

export default function DotGrid({ scrollProgress }: { scrollProgress: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const scrollRef = useRef(scrollProgress)

  useEffect(() => {
    scrollRef.current = scrollProgress
  }, [scrollProgress])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d', { alpha: false })
    if (!ctx) return

    let animationFrameId: number
    const spacing = 35
    const dotRadius = 1.2
    
    let mouseX = -1000
    let mouseY = -1000
    
    const handleMouseMove = (e: MouseEvent) => {
      mouseX = e.clientX
      mouseY = e.clientY
    }
    window.addEventListener('mousemove', handleMouseMove)

    const getNoise = (x: number, y: number) => {
      return (Math.sin(x * 0.01 + y * 0.02) * 0.5 + 0.5 + Math.cos(x * 0.05) * 0.5) / 2
    }

    const resize = () => {
      canvas.width = window.innerWidth * window.devicePixelRatio
      canvas.height = window.innerHeight * window.devicePixelRatio
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
    }
    
    window.addEventListener('resize', resize)
    resize()

    const render = () => {
      ctx.fillStyle = '#030107'
      ctx.fillRect(0, 0, window.innerWidth, window.innerHeight)
      
      const cols = Math.ceil(window.innerWidth / spacing) + 1
      const rows = Math.ceil(window.innerHeight / spacing) + 1
      
      const currentScroll = scrollRef.current
      const maxDistance = 140

      for (let i = 0; i < cols; i++) {
        for (let j = 0; j < rows; j++) {
          const x = i * spacing
          const y = j * spacing
          
          const dx = x - mouseX
          const dy = y - mouseY
          const distance = Math.sqrt(dx * dx + dy * dy)
          
          let intensity = 0.15
          let r = dotRadius
          if (distance < maxDistance) {
            const factor = 1 - distance / maxDistance
            intensity += factor * 0.85
            r += factor * 1.0
          }
          
          const noise = getNoise(x, y)
          let isPurple = false
          let purpleProgress = 0
          if (currentScroll > 0) {
             const transitionThreshold = currentScroll * 1.5 - noise
             if (transitionThreshold > 0) {
               isPurple = true
               purpleProgress = Math.min(1, transitionThreshold * 2.5)
             }
          }
          
          const rColor = isPurple ? Math.round(255 - (255 - 168) * purpleProgress) : 255
          const gColor = isPurple ? Math.round(255 - (255 - 101) * purpleProgress) : 255
          const bColor = isPurple ? Math.round(255 - (255 - 255) * purpleProgress) : 255
          
          ctx.beginPath()
          ctx.arc(x, y, r, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(${rColor}, ${gColor}, ${bColor}, ${intensity})`
          ctx.fill()
        }
      }
      
      animationFrameId = requestAnimationFrame(render)
    }
    
    render()
    
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('resize', resize)
      cancelAnimationFrame(animationFrameId)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        zIndex: 1,
        pointerEvents: 'none'
      }}
    />
  )
}
