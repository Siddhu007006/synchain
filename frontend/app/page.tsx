import { Navigation } from "@/components/landing/navigation";
import { HeroSection } from "@/components/landing/hero-section";
import { FeaturesSection } from "@/components/landing/features-section";
import { HowItWorksSection } from "@/components/landing/how-it-works-section";
import { FooterSection } from "@/components/landing/footer-section";
import { ScrollCursor } from "@/components/landing/scroll-icon";

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-x-hidden noise-overlay">
      <ScrollCursor />
      <Navigation />
      <HeroSection />
      <HowItWorksSection />
      <FeaturesSection />
      <FooterSection />
    </main>
  );
}
