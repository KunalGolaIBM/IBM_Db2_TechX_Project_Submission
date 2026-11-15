import { useScrollReveal } from '../hooks/useScrollReveal';
import LandingNav from '../components/landing/LandingNav';
import HeroSection from '../components/landing/HeroSection';
import CoreLoopSection from '../components/landing/CoreLoopSection';
import ExperienceSection from '../components/landing/ExperienceSection';
import FinalCTASection from '../components/landing/FinalCTASection';
import CosmicAtmosphere from '../components/landing/CosmicAtmosphere';

export default function Landing() {
  const scrollRef = useScrollReveal<HTMLDivElement>();

  return (
    <div
      ref={scrollRef}
      className="landing-page w-full relative"
      style={{
        overflowX: 'hidden',
        backgroundColor: 'var(--color-ody-bg)',
      }}
    >
      {/* Global atmospheric layer — behind everything */}
      <CosmicAtmosphere />

      {/* Page content — all rendered above z-index:0 canvas */}
      <div className="relative" style={{ zIndex: 1 }}>
        <LandingNav />
        <HeroSection />
        <CoreLoopSection />
        <ExperienceSection />
        <FinalCTASection />
      </div>
    </div>
  );
}
