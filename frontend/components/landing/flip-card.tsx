"use client"

import { useState, useCallback, useEffect, useRef } from "react"

interface FlipCardProps {
  frontContent: React.ReactNode
  backContent: React.ReactNode
  flipDirection?: "horizontal" | "vertical"
  flipTrigger?: "hover" | "click"
  animationDuration?: number
  perspective?: number
  borderRadius?: number
  shadow?: boolean
  autoFlip?: boolean
  autoFlipInterval?: number
  className?: string
}

export function FlipCard({
  frontContent,
  backContent,
  flipDirection = "horizontal",
  flipTrigger = "hover",
  animationDuration = 0.6,
  perspective = 1000,
  borderRadius = 12,
  shadow = true,
  autoFlip = false,
  autoFlipInterval = 3,
  className = "",
}: FlipCardProps) {
  const [isFlipped, setIsFlipped] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const handleClick = useCallback(() => {
    if (flipTrigger === "click") {
      setIsFlipped((prev) => !prev)
    }
  }, [flipTrigger])

  const handleMouseEnter = useCallback(() => {
    if (flipTrigger === "hover") {
      setIsFlipped(true)
    }
  }, [flipTrigger])

  const handleMouseLeave = useCallback(() => {
    if (flipTrigger === "hover") {
      setIsFlipped(false)
    }
  }, [flipTrigger])

  useEffect(() => {
    if (autoFlip && flipTrigger === "click") {
      intervalRef.current = setInterval(() => {
        setIsFlipped((prev) => !prev)
      }, autoFlipInterval * 1000)
      return () => {
        if (intervalRef.current) clearInterval(intervalRef.current)
      }
    }
  }, [autoFlip, autoFlipInterval, flipTrigger])

  const isHorizontal = flipDirection === "horizontal"

  const frontTransform = isFlipped
    ? isHorizontal
      ? "rotateY(-180deg)"
      : "rotateX(-180deg)"
    : "rotateY(0deg)"

  const backTransform = isFlipped
    ? isHorizontal
      ? "rotateY(0deg)"
      : "rotateX(0deg)"
    : isHorizontal
      ? "rotateY(180deg)"
      : "rotateX(180deg)"

  return (
    <div
      className={className}
      style={{
        perspective: `${perspective}px`,
        cursor: flipTrigger === "click" ? "pointer" : "default",
      }}
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          transformStyle: "preserve-3d",
        }}
      >
        {/* Front */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            backfaceVisibility: "hidden",
            WebkitBackfaceVisibility: "hidden",
            borderRadius: `${borderRadius}px`,
            boxShadow: shadow ? "0 4px 20px rgba(0, 0, 0, 0.08)" : "none",
            overflow: "hidden",
            transform: frontTransform,
            transition: `transform ${animationDuration}s ease-in-out`,
            willChange: "transform",
          }}
        >
          {frontContent}
        </div>

        {/* Back */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            backfaceVisibility: "hidden",
            WebkitBackfaceVisibility: "hidden",
            borderRadius: `${borderRadius}px`,
            boxShadow: shadow ? "0 4px 20px rgba(0, 0, 0, 0.08)" : "none",
            overflow: "hidden",
            transform: backTransform,
            transition: `transform ${animationDuration}s ease-in-out`,
            willChange: "transform",
          }}
        >
          {backContent}
        </div>
      </div>
    </div>
  )
}
