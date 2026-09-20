"use client";

import { useEffect, useRef } from "react";
import { useMotionValue, useSpring, useTransform, animate } from "framer-motion";

interface AnimatedCounterProps {
  value: number;
  duration?: number; // in seconds
  formatter?: (value: number) => string;
}

export function AnimatedCounter({
  value,
  duration = 1.5,
  formatter = (v) => Math.round(v).toLocaleString(),
}: AnimatedCounterProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const motionValue = useMotionValue(0);
  const springValue = useSpring(motionValue, {
    stiffness: 75,
    damping: 18,
  });
  const displayValue = useTransform(springValue, (current) => formatter(current));

  useEffect(() => {
    const controls = animate(motionValue, value, {
      duration,
      ease: "easeOut",
    });

    return () => controls.stop();
  }, [value, motionValue, duration]);

  useEffect(() => {
    const unsubscribe = displayValue.on("change", (latest) => {
      if (ref.current) {
        ref.current.textContent = latest;
      }
    });

    return () => unsubscribe();
  }, [displayValue]);

  return <span ref={ref}>0</span>;
}
