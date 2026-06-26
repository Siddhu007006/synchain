"use client";

import { useEffect, useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";
import { AnimatedSphere } from "./animated-sphere";
import Link from "next/link";
import { motion } from "framer-motion";

const words = ["optimize", "predict", "decide"];
const staticPrefix = "AI Supply Chain\nTwin ";

// Typing config
const TYPING_SPEED = 50;     // ms per character
const DELETING_SPEED = 30;   // ms per character
const PAUSE_DURATION = 2000; // ms before deleting word
const INITIAL_DELAY = 300;   // ms before starting

type Phase = "waiting" | "typing-full" | "pausing" | "deleting" | "typing-word";

export function HeroSection() {
  const [isVisible, setIsVisible] = useState(false);
  const [displayedText, setDisplayedText] = useState("");
  const [wordIndex, setWordIndex] = useState(0);
  const [phase, setPhase] = useState<Phase>("waiting");
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
        } else {
          setIsVisible(false);
          setDisplayedText("");
          setWordIndex(0);
          setPhase("waiting");
        }
      },
      { threshold: 0.1 }
    );

    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  // Kick off typing after initial delay
  useEffect(() => {
    if (!isVisible) return;
    const timeout = setTimeout(() => setPhase("typing-full"), INITIAL_DELAY);
    return () => clearTimeout(timeout);
  }, [isVisible]);

  // Typewriter engine – driven by phase + displayedText
  useEffect(() => {
    if (phase === "waiting") return;

    let timeout: ReturnType<typeof setTimeout>;
    const fullText = staticPrefix + words[wordIndex];

    switch (phase) {
      case "typing-full": {
        if (displayedText.length < fullText.length) {
          timeout = setTimeout(() => {
            setDisplayedText(fullText.slice(0, displayedText.length + 1));
          }, TYPING_SPEED);
        } else {
          // Finished typing full text → pause
          setPhase("pausing");
        }
        break;
      }
      case "pausing": {
        timeout = setTimeout(() => setPhase("deleting"), PAUSE_DURATION);
        break;
      }
      case "deleting": {
        if (displayedText.length > staticPrefix.length) {
          timeout = setTimeout(() => {
            setDisplayedText((prev) => prev.slice(0, -1));
          }, DELETING_SPEED);
        } else {
          // Word fully deleted → next word
          setWordIndex((prev) => (prev + 1) % words.length);
          setPhase("typing-word");
        }
        break;
      }
      case "typing-word": {
        const currentWord = words[wordIndex];
        const typedLen = displayedText.length - staticPrefix.length;
        if (typedLen < currentWord.length) {
          timeout = setTimeout(() => {
            setDisplayedText(staticPrefix + currentWord.slice(0, typedLen + 1));
          }, TYPING_SPEED);
        } else {
          // Word done → pause then delete again
          setPhase("pausing");
        }
        break;
      }
    }

    return () => clearTimeout(timeout);
  }, [phase, displayedText, wordIndex]);

  // Split displayed text into lines for rendering
  const lines = displayedText.split("\n");

  return (
    <section ref={sectionRef} className="relative min-h-screen flex flex-col justify-center overflow-hidden">
      {/* Grid lines — bottommost background layer */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-60 z-0">
        {[...Array(8)].map((_, i) => (
          <div
            key={`h-${i}`}
            className="absolute h-px bg-foreground/20"
            style={{
              top: `${12.5 * (i + 1)}%`,
              left: 0,
              right: 0,
            }}
          />
        ))}
        {[...Array(12)].map((_, i) => (
          <div
            key={`v-${i}`}
            className="absolute w-px bg-foreground/20"
            style={{
              left: `${8.33 * (i + 1)}%`,
              top: 0,
              bottom: 0,
            }}
          />
        ))}
      </div>

      {/* Animated sphere — sits on top of grid with solid bg to mask grid lines */}
      <div className="absolute right-0 top-1/2 -translate-y-1/2 w-[600px] h-[600px] lg:w-[800px] lg:h-[800px] z-[1]">
        <div className="w-full h-full rounded-full bg-background opacity-100 absolute inset-0" />
        <div className="relative w-full h-full opacity-90">
          <AnimatedSphere />
        </div>
      </div>

      <div className="relative z-10 max-w-[1400px] mx-auto px-6 lg:px-12 py-32 lg:py-40">
        {/* Eyebrow */}
        <div
          className={`mb-8 transition-all duration-700 ${isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
            }`}
        >
          <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground">
            <span className="w-8 h-px bg-foreground/30" />
            AI-Powered Supply Chain
          </span>
        </div>

        {/* Main headline with typewriter effect */}
        <div className="mb-16 lg:mb-20">
          <h1
            className={`text-[clamp(3rem,12vw,10rem)] font-display leading-[1.1] tracking-tight transition-all duration-1000 ${isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
              }`}
          >
            {lines.map((line, lineIdx) => (
              <span key={lineIdx} className="block">
                {line}
                {/* Show blinking cursor at the end of the last line */}
                {lineIdx === lines.length - 1 && (
                  <motion.span
                    className="inline-block ml-1 -mb-1"
                    style={{
                      width: "0.06em",
                      height: "0.85em",
                      backgroundColor: "currentColor",
                      verticalAlign: "baseline",
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
              </span>
            ))}

          </h1>
        </div>

        {/* Description */}
        <div className="grid lg:grid-cols-2 gap-16 lg:gap-24 items-center">
          <p
            className={`text-xl lg:text-2xl text-muted-foreground leading-relaxed max-w-xl transition-all duration-700 delay-200 ${isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
              }`}
          >
            Optimize inventory, logistics, and supply decisions using AI-powered simulations and real-time insights to reduce costs and prevent shortages.
          </p>

          {/* CTAs */}
          <div
            className={`flex flex-col sm:flex-row items-center justify-center lg:justify-end gap-4 transition-all duration-700 delay-300 ${isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
              }`}
          >
            <Link href="/form">
              <Button
                size="lg"
                className="bg-foreground hover:bg-foreground/90 text-background px-8 h-14 text-base rounded-full group"
              >
                Start Simulation
                <ArrowRight className="w-4 h-4 ml-2 transition-transform group-hover:translate-x-1" />
              </Button>
            </Link>
            <Button
              size="lg"
              variant="outline"
              className="h-14 px-8 text-base rounded-full border-foreground/20 hover:bg-foreground/5"
            >
              Learn more
            </Button>
          </div>
        </div>

      </div>

      {/* Stats marquee - full width outside container */}
      <div
        className={`absolute z-20 bottom-0 left-0 right-0 transition-all duration-700 delay-500 ${isVisible ? "opacity-100" : "opacity- 0"
          }`}
      >
        <div className="flex gap-16 marquee whitespace-nowrap">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="flex gap-16">
              {[
                { value: "35%", label: "cost reduction", company: "AVERAGE" },
                { value: "92%", label: "forecast accuracy", company: "AI-DRIVEN" },
                { value: "2.3x", label: "faster decisions", company: "SYSTEM" },
                { value: "150M", label: "inventory optimized", company: "UNITS" },
              ].map((stat) => (
                <div key={`${stat.company}-${i}`} className="flex items-baseline gap-4">
                  <span className="text-4xl lg:text-5xl font-display">{stat.value}</span>
                  <span className="text-sm text-muted-foreground">
                    {stat.label}
                    <span className="block font-mono text-xs mt-1">{stat.company}</span>
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Scroll indicator removed – now handled by ScrollCursor in layout */}

    </section>
  );
}
