"use client";

import { useEffect, useRef, useState } from "react";
import { TypewriterText } from "./typewriter-text";
import { FlipCard } from "./flip-card";

const features = [
  {
    number: "01",
    title: "Demand Forecasting",
    description: "Predict customer demand with AI models that learn from historical patterns and market trends.",
    details: [
      "Machine learning models trained on historical sales data",
      "Seasonal trend detection and adjustment",
      "External factor integration (weather, events, economy)",
      "Real-time accuracy tracking and model retraining",
    ],
    visual: "deploy",
  },
  {
    number: "02",
    title: "Inventory Optimization",
    description: "Calculate optimal stock levels across warehouses to minimize costs while preventing shortages.",
    details: [
      "Multi-echelon inventory optimization",
      "Safety stock calculation with demand variability",
      "ABC/XYZ classification and segmentation",
      "Automated reorder point and quantity suggestions",
    ],
    visual: "ai",
  },
  {
    number: "03",
    title: "Logistics Planning",
    description: "Plan efficient routes and shipping strategies to reduce delivery times and costs.",
    details: [
      "Multi-modal transport optimization",
      "Dynamic route planning with real-time constraints",
      "Carrier selection and rate comparison",
      "Last-mile delivery optimization algorithms",
    ],
    visual: "collab",
  },
  {
    number: "04",
    title: "Risk Analysis",
    description: "Identify supply chain vulnerabilities and simulate scenarios to mitigate disruptions.",
    details: [
      "Monte Carlo simulation for risk scenarios",
      "Supplier reliability scoring and monitoring",
      "Disruption impact assessment and contingency plans",
      "Real-time risk heat maps across the supply network",
    ],
    visual: "security",
  },
];

function DeployVisual() {
  return (
    <svg viewBox="0 0 200 160" className="w-full h-full">
      <defs>
        <clipPath id="deployClip">
          <rect x="30" y="20" width="140" height="120" rx="4" />
        </clipPath>
      </defs>
      
      <rect x="30" y="20" width="140" height="120" rx="4" fill="none" stroke="currentColor" strokeWidth="2" />
      
      <g clipPath="url(#deployClip)">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <rect
            key={i}
            x="40"
            y={35 + i * 16}
            width="120"
            height="10"
            rx="2"
            fill="currentColor"
            opacity="0.15"
          >
            <animate
              attributeName="opacity"
              values="0.15;0.8;0.15"
              dur="2s"
              begin={`${i * 0.15}s`}
              repeatCount="indefinite"
            />
            <animate
              attributeName="width"
              values="20;120;20"
              dur="2s"
              begin={`${i * 0.15}s`}
              repeatCount="indefinite"
            />
          </rect>
        ))}
      </g>
      
      <circle cx="100" cy="155" r="3" fill="currentColor" opacity="0.3">
        <animate attributeName="opacity" values="0.3;1;0.3" dur="1s" repeatCount="indefinite" />
      </circle>
    </svg>
  );
}

function AIVisual() {
  return (
    <svg viewBox="0 0 200 160" className="w-full h-full">
      <circle cx="100" cy="80" r="12" fill="currentColor">
        <animate attributeName="r" values="12;14;12" dur="2s" repeatCount="indefinite" />
      </circle>
      
      {[0, 1, 2, 3, 4, 5].map((i) => {
        const angle = (i * 60) * (Math.PI / 180);
        const radius = 50;
        const x = Number((100 + Math.cos(angle) * radius).toFixed(3));
        const y = Number((80 + Math.sin(angle) * radius).toFixed(3));
        return (
          <g key={i}>
            <line
              x1="100"
              y1="80"
              x2={x}
              y2={y}
              stroke="currentColor"
              strokeWidth="1"
              opacity="0.3"
            >
              <animate
                attributeName="opacity"
                values="0.3;0.8;0.3"
                dur="2s"
                begin={`${i * 0.3}s`}
                repeatCount="indefinite"
              />
            </line>
            
            <circle
              cx={x}
              cy={y}
              r="6"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <animate
                attributeName="r"
                values="6;8;6"
                dur="2s"
                begin={`${i * 0.3}s`}
                repeatCount="indefinite"
              />
            </circle>
          </g>
        );
      })}
      
      <circle cx="100" cy="80" r="30" fill="none" stroke="currentColor" strokeWidth="1" opacity="0">
        <animate attributeName="r" values="20;60" dur="2s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.5;0" dur="2s" repeatCount="indefinite" />
      </circle>
    </svg>
  );
}

function CollabVisual() {
  return (
    <svg viewBox="0 0 200 160" className="w-full h-full">
      <g>
        <rect x="30" y="50" width="50" height="60" rx="4" fill="none" stroke="currentColor" strokeWidth="2" />
        <text x="55" y="85" textAnchor="middle" fontSize="20" fontFamily="monospace" fill="currentColor">A</text>
        <circle cx="55" cy="35" r="12" fill="none" stroke="currentColor" strokeWidth="2" />
      </g>
      
      <g>
        <rect x="120" y="50" width="50" height="60" rx="4" fill="none" stroke="currentColor" strokeWidth="2" />
        <text x="145" y="85" textAnchor="middle" fontSize="20" fontFamily="monospace" fill="currentColor">B</text>
        <circle cx="145" cy="35" r="12" fill="none" stroke="currentColor" strokeWidth="2" />
      </g>
      
      <line x1="80" y1="80" x2="120" y2="80" stroke="currentColor" strokeWidth="2" strokeDasharray="4 4">
        <animate attributeName="stroke-dashoffset" values="0;-8" dur="0.5s" repeatCount="indefinite" />
      </line>
      
      <circle r="4" fill="currentColor">
        <animateMotion dur="1.5s" repeatCount="indefinite">
          <mpath href="#dataPath" />
        </animateMotion>
      </circle>
      <path id="dataPath" d="M 80 80 L 120 80" fill="none" />
      
      <g transform="translate(100, 130)">
        <circle r="6" fill="none" stroke="currentColor" strokeWidth="2">
          <animate attributeName="r" values="6;10;6" dur="1s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="1;0.3;1" dur="1s" repeatCount="indefinite" />
        </circle>
      </g>
    </svg>
  );
}

function SecurityVisual() {
  return (
    <svg viewBox="0 0 200 160" className="w-full h-full">
      <path
        d="M 100 20 L 150 40 L 150 90 Q 150 130 100 145 Q 50 130 50 90 L 50 40 Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
      
      <path
        d="M 100 35 L 135 50 L 135 85 Q 135 115 100 128 Q 65 115 65 85 L 65 50 Z"
        fill="currentColor"
        opacity="0.1"
      >
        <animate attributeName="opacity" values="0.1;0.2;0.1" dur="2s" repeatCount="indefinite" />
      </path>
      
      <rect x="85" y="70" width="30" height="25" rx="3" fill="currentColor" />
      <path
        d="M 90 70 L 90 60 Q 90 50 100 50 Q 110 50 110 60 L 110 70"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
      
      <circle cx="100" cy="80" r="4" fill="white" />
      <rect x="98" y="82" width="4" height="8" fill="white" />
      
      <line x1="60" y1="60" x2="140" y2="60" stroke="currentColor" strokeWidth="1" opacity="0">
        <animate attributeName="y1" values="40;120;40" dur="3s" repeatCount="indefinite" />
        <animate attributeName="y2" values="40;120;40" dur="3s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0;0.5;0" dur="3s" repeatCount="indefinite" />
      </line>
    </svg>
  );
}

function AnimatedVisual({ type }: { type: string }) {
  switch (type) {
    case "deploy":
      return <DeployVisual />;
    case "ai":
      return <AIVisual />;
    case "collab":
      return <CollabVisual />;
    case "security":
      return <SecurityVisual />;
    default:
      return <DeployVisual />;
  }
}

function FeatureFlipCard({ feature, index }: { feature: typeof features[0]; index: number }) {
  const [isVisible, setIsVisible] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setIsVisible(true);
      },
      { threshold: 0.2 }
    );

    if (cardRef.current) observer.observe(cardRef.current);
    return () => observer.disconnect();
  }, []);

  const frontContent = (
    <div className="w-full h-full flex flex-col items-center justify-center bg-card border border-border p-6 lg:p-8">
      {/* SVG Visual */}
      <div className="w-28 h-24 lg:w-36 lg:h-28 text-foreground mb-5">
        <AnimatedVisual type={feature.visual} />
      </div>
      
      {/* Number + Title */}
      <span className="font-mono text-xs text-muted-foreground mb-2">{feature.number}</span>
      <h3 className="text-xl lg:text-2xl font-display text-center tracking-tight">
        {feature.title}
      </h3>
    </div>
  );

  const backContent = (
    <div className="w-full h-full flex flex-col justify-between bg-foreground text-background p-6 lg:p-8">
      {/* Header */}
      <div>
        <span className="font-mono text-xs opacity-50 mb-2 block">{feature.number}</span>
        <h3 className="text-lg lg:text-xl font-display mb-3">{feature.title}</h3>
        <p className="text-sm leading-relaxed opacity-70 mb-4">{feature.description}</p>
      </div>

      {/* Detail bullets */}
      <ul className="space-y-2">
        {feature.details.map((detail, i) => (
          <li key={i} className="flex items-start gap-2 text-xs opacity-80">
            <span className="mt-1 w-1 h-1 rounded-full bg-current shrink-0" />
            {detail}
          </li>
        ))}
      </ul>
    </div>
  );

  return (
    <div
      ref={cardRef}
      className={`transition-all duration-700 ${
        isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-12"
      }`}
      style={{ transitionDelay: `${index * 120}ms` }}
    >
      <FlipCard
        frontContent={frontContent}
        backContent={backContent}
        flipTrigger="hover"
        animationDuration={0.6}
        perspective={1000}
        borderRadius={12}
        shadow={true}
        className="w-full h-[320px] lg:h-[360px]"
      />
    </div>
  );
}

export function FeaturesSection() {
  const [isVisible, setIsVisible] = useState(false);
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setIsVisible(true);
      },
      { threshold: 0.1 }
    );

    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <section
      id="features"
      ref={sectionRef}
      className="relative py-24 lg:py-32"
    >
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        {/* Header */}
        <div className="mb-16 lg:mb-24">
          <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-6">
            <span className="w-8 h-px bg-foreground/30" />
            System Capabilities
          </span>
          <h2
            className={`text-4xl lg:text-6xl font-display tracking-tight transition-all duration-700 ${
              isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
            }`}
          >
            <TypewriterText
              text={"Everything you need.\nFor better decisions."}
              secondLineClassName="text-muted-foreground"
            />
          </h2>
        </div>

        {/* Flip Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature, index) => (
            <FeatureFlipCard key={feature.number} feature={feature} index={index} />
          ))}
        </div>
      </div>
    </section>
  );
}
