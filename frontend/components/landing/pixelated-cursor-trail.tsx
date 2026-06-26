"use client"

import { useEffect, useState, useRef, startTransition } from "react"

interface TrailPoint {
  x: number
  y: number
  vx: number
  vy: number
}

interface PixelatedCursorTrailProps {
  pixelCount?: number
  pixelSize?: number
  trailColor?: string
  fadeOut?: boolean
  trailSpacing?: number
  stiffness?: number
  damping?: number
  pixelShape?: "square" | "circle"
  blur?: number
  scaleVariation?: boolean
  trailDuration?: number
  trailStyle?: "solid" | "dashed" | "dotted" | "wave" | "zigzag"
  animationPreset?: "none" | "fadeInOut" | "pulse" | "strobe" | "rainbow" | "wave"
  presetSpeed?: number
}

export function PixelatedCursorTrail({
  pixelCount = 30,
  pixelSize = 8,
  trailColor = "#000000",
  fadeOut = true,
  trailSpacing = 15,
  stiffness = 0.2,
  damping = 0.5,
  pixelShape = "square",
  blur = 0,
  scaleVariation = true,
  trailDuration = 5,
  trailStyle = "solid",
  animationPreset = "none",
  presetSpeed = 1,
}: PixelatedCursorTrailProps) {
  const [trail, setTrail] = useState<TrailPoint[]>([])
  const cursorPos = useRef({ x: -1000, y: -1000 })
  const lastCursorPos = useRef({ x: -1000, y: -1000 })
  const animationFrameId = useRef<number | null>(null)
  const lastMoveTime = useRef(Date.now())
  const activityLevel = useRef(1)
  const animationTime = useRef(0)

  useEffect(() => {
    if (typeof window === "undefined") return

    const handleMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - lastCursorPos.current.x
      const dy = e.clientY - lastCursorPos.current.y
      const distance = Math.sqrt(dx * dx + dy * dy)

      cursorPos.current = { x: e.clientX, y: e.clientY }
      lastCursorPos.current = { x: e.clientX, y: e.clientY }

      if (distance > 0.5) {
        lastMoveTime.current = Date.now()
      }
    }

    window.addEventListener("mousemove", handleMouseMove)
    return () => window.removeEventListener("mousemove", handleMouseMove)
  }, [])

  useEffect(() => {
    if (typeof window === "undefined") return

    const initialTrail: TrailPoint[] = []
    for (let i = 0; i < pixelCount; i++) {
      initialTrail.push({
        x: cursorPos.current.x,
        y: cursorPos.current.y,
        vx: 0,
        vy: 0,
      })
    }
    setTrail(initialTrail)

    const animate = () => {
      animationTime.current += 0.016 * presetSpeed
      const timeSinceMove = Date.now() - lastMoveTime.current
      const isMoving = timeSinceMove < 100

      const targetLevel = isMoving ? 1 : 0
      const step = isMoving ? 0.016 / 0.2 : 0.016 / trailDuration

      if (activityLevel.current < targetLevel) {
        activityLevel.current = Math.min(targetLevel, activityLevel.current + step)
      } else if (activityLevel.current > targetLevel) {
        activityLevel.current = Math.max(targetLevel, activityLevel.current - step)
      }

      startTransition(() => {
        setTrail((prevTrail) => {
          const newTrail = prevTrail.map((point) => ({ ...point }))

          if (newTrail.length > 0) {
            const dx = cursorPos.current.x - newTrail[0].x
            const dy = cursorPos.current.y - newTrail[0].y
            newTrail[0].vx += dx * stiffness
            newTrail[0].vy += dy * stiffness
            newTrail[0].vx *= damping
            newTrail[0].vy *= damping
            newTrail[0].x += newTrail[0].vx
            newTrail[0].y += newTrail[0].vy
          }

          for (let i = 1; i < newTrail.length; i++) {
            const prev = newTrail[i - 1]
            const curr = newTrail[i]
            const dx = prev.x - curr.x
            const dy = prev.y - curr.y
            const dist = Math.sqrt(dx * dx + dy * dy)

            curr.vx += dx * stiffness
            curr.vy += dy * stiffness
            curr.vx *= damping
            curr.vy *= damping
            curr.x += curr.vx
            curr.y += curr.vy

            if (dist > trailSpacing) {
              const diff = dist - trailSpacing
              const ratio = diff / dist
              const offsetX = dx * ratio * 0.5
              const offsetY = dy * ratio * 0.5
              curr.x += offsetX
              curr.y += offsetY
            }
          }

          return newTrail
        })
      })

      animationFrameId.current = requestAnimationFrame(animate)
    }

    animationFrameId.current = requestAnimationFrame(animate)
    return () => {
      if (animationFrameId.current !== null) {
        cancelAnimationFrame(animationFrameId.current)
      }
    }
  }, [pixelCount, trailSpacing, stiffness, damping, presetSpeed, trailDuration, pixelSize])

  if (typeof document === "undefined" || !document.body) return null

  const fadeMultiplier = activityLevel.current

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        pointerEvents: "none",
        zIndex: 9999,
      }}
    >
      {trail.map((point, index) => {
        const progress = index / pixelCount
        let opacity = fadeOut ? 1 - progress : 1
        let scale = scaleVariation ? 1 - progress * 0.5 : 1

        opacity *= fadeMultiplier
        scale *= fadeMultiplier

        let backgroundColor = trailColor

        if (animationPreset !== "none") {
          const time = animationTime.current
          const indexOffset = index * 0.1

          switch (animationPreset) {
            case "fadeInOut":
              opacity *= (Math.sin(time + indexOffset) + 1) / 2
              break
            case "pulse":
              scale *= 1 + Math.sin(time + indexOffset) * 0.3
              break
            case "strobe":
              opacity *= Math.sin(time * 5 + indexOffset) > 0 ? 1 : 0.2
              break
            case "rainbow": {
              const hue = (time * 50 + index * 10) % 360
              backgroundColor = `hsl(${hue}, 70%, 60%)`
              break
            }
            case "wave": {
              const waveValue = (Math.sin(time + indexOffset * 2) + 1) / 2
              opacity *= 0.3 + waveValue * 0.7
              scale *= 0.7 + waveValue * 0.6
              break
            }
          }
        }

        let isVisible = true
        if (trailStyle === "dashed") {
          isVisible = index % 5 < 3
        } else if (trailStyle === "dotted") {
          isVisible = index % 3 === 0
        }

        let offsetX = 0
        let offsetY = 0

        if (trailStyle === "wave" && index > 0) {
          const prev = trail[index - 1]
          const dx = point.x - prev.x
          const dy = point.y - prev.y
          const length = Math.sqrt(dx * dx + dy * dy)
          if (length > 0) {
            const perpX = -dy / length
            const perpY = dx / length
            const waveOffset = Math.sin(index * 0.3) * pixelSize * 2
            offsetX = perpX * waveOffset
            offsetY = perpY * waveOffset
          }
        } else if (trailStyle === "zigzag" && index > 0) {
          const prev = trail[index - 1]
          const dx = point.x - prev.x
          const dy = point.y - prev.y
          const length = Math.sqrt(dx * dx + dy * dy)
          if (length > 0) {
            const perpX = -dy / length
            const perpY = dx / length
            const zigzagOffset = (index % 2 === 0 ? 1 : -1) * pixelSize * 1.5
            offsetX = perpX * zigzagOffset
            offsetY = perpY * zigzagOffset
          }
        }

        if (!isVisible || opacity < 0.01) return null

        return (
          <div
            key={index}
            style={{
              position: "absolute",
              left: `${point.x + offsetX}px`,
              top: `${point.y + offsetY}px`,
              width: `${pixelSize * scale}px`,
              height: `${pixelSize * scale}px`,
              backgroundColor,
              opacity,
              transform: "translate(-50%, -50%)",
              imageRendering: "pixelated",
              borderRadius: pixelShape === "circle" ? "50%" : "0",
              filter: blur > 0 ? `blur(${blur}px)` : "none",
            }}
          />
        )
      })}
    </div>
  )
}
