"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

interface TypewriterTextProps {
  text: string;
  typingSpeed?: number;
  className?: string;
  /** If provided, this part of the text will have this class (used for dimmed second line) */
  secondLineClassName?: string;
  cursorColor?: string;
}

/**
 * A reusable typewriter component that types text character-by-character
 * when it scrolls into view. Supports a two-line layout via \n in the text.
 */
export function TypewriterText({
  text,
  typingSpeed = 50,
  className = "",
  secondLineClassName = "",
  cursorColor,
}: TypewriterTextProps) {
  const [displayedText, setDisplayedText] = useState("");
  const [hasStarted, setHasStarted] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Start typing when element scrolls into view
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setHasStarted(true);
        } else {
          setHasStarted(false);
          setDisplayedText("");
        }
      },
      { threshold: 0.3 }
    );
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Typewriter engine
  useEffect(() => {
    if (!hasStarted) return;
    if (displayedText.length >= text.length) return;

    const timeout = setTimeout(() => {
      setDisplayedText(text.slice(0, displayedText.length + 1));
    }, typingSpeed);

    return () => clearTimeout(timeout);
  }, [hasStarted, displayedText, text, typingSpeed]);

  // Split by newline to render lines
  const lines = displayedText.split("\n");
  const fullLines = text.split("\n");

  return (
    <span ref={containerRef} className={className}>
      {lines.map((line, idx) => (
        <span key={idx}>
          <span className={idx > 0 && secondLineClassName ? secondLineClassName : ""}>
            {line}
          </span>
          {/* Blinking cursor at the end of the last line */}
          {idx === lines.length - 1 && displayedText.length < text.length && (
            <motion.span
              className="inline-block ml-0.5 align-baseline"
              style={{
                width: "0.06em",
                height: "0.75em",
                backgroundColor: cursorColor || "currentColor",
              }}
              animate={{ opacity: [1, 0] }}
              transition={{
                duration: 0.5,
                repeat: Infinity,
                repeatType: "reverse",
                ease: "easeInOut",
              }}
            />
          )}
          {/* Add line break if not the last full line */}
          {idx < fullLines.length - 1 && <br />}
        </span>
      ))}
    </span>
  );
}
