"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";

export function ScrollCursor() {
  const [mousePos, setMousePos] = useState({ x: -100, y: -100 });
  const [isScrolling, setIsScrolling] = useState(false);
  const [scrollDir, setScrollDir] = useState<"down" | "up">("down");
  const scrollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastScrollY = useRef(0);
  const styleRef = useRef<HTMLStyleElement | null>(null);

  // Track mouse position
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  // Track scroll events – detect direction and active scrolling
  const handleScroll = useCallback(() => {
    const currentY = window.scrollY;
    setScrollDir(currentY > lastScrollY.current ? "down" : "up");
    lastScrollY.current = currentY;

    setIsScrolling(true);

    if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current);
    scrollTimeoutRef.current = setTimeout(() => {
      setIsScrolling(false);
    }, 600);
  }, []);

  useEffect(() => {
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [handleScroll]);

  // Hide/show cursor by injecting a <style> tag into <head>
  useEffect(() => {
    if (!styleRef.current) {
      const style = document.createElement("style");
      style.setAttribute("data-scroll-cursor", "");
      document.head.appendChild(style);
      styleRef.current = style;
    }

    if (isScrolling) {
      styleRef.current.textContent = "*, *::before, *::after { cursor: none !important; }";
    } else {
      styleRef.current.textContent = "";
    }

    return () => {
      if (styleRef.current) {
        styleRef.current.textContent = "";
      }
    };
  }, [isScrolling]);

  // Dot animation direction
  const dotY = scrollDir === "down" ? [0, 8, 0] : [0, -8, 0];

  return (
    <>
      {/* Custom cursor that follows the mouse */}
      <AnimatePresence>
        {isScrolling && (
          <motion.div
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.5 }}
            transition={{ duration: 0.2 }}
            style={{
              position: "fixed",
              left: mousePos.x,
              top: mousePos.y,
              transform: "translate(-50%, -50%)",
              pointerEvents: "none",
              zIndex: 99999,
            }}
          >
            {/* Mouse outline shape */}
            <div
              style={{
                width: 26,
                height: 42,
                border: "1.5px solid currentColor",
                borderRadius: 16,
                display: "flex",
                justifyContent: "center",
                paddingTop: 10,
                opacity: 0.8,
              }}
            >
              {/* Animated dot */}
              <motion.div
                key={scrollDir}
                style={{
                  width: 4,
                  height: 4,
                  borderRadius: "50%",
                  backgroundColor: "currentColor",
                }}
                animate={{ y: dotY }}
                transition={{
                  duration: 0.8,
                  repeat: Infinity,
                  ease: "easeInOut",
                }}
              />
            </div>

            {/* Directional arrow below/above the icon */}
            <motion.div
              key={`arrow-${scrollDir}`}
              initial={{ opacity: 0, y: scrollDir === "down" ? -4 : 4 }}
              animate={{ opacity: 0.6, y: 0 }}
              style={{
                display: "flex",
                justifyContent: "center",
                marginTop: scrollDir === "down" ? 4 : 0,
                marginBottom: scrollDir === "up" ? 4 : 0,
                fontSize: 10,
                order: scrollDir === "up" ? -1 : 1,
              }}
            >
              {scrollDir === "down" ? "▼" : "▲"}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
