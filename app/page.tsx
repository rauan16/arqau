import Navbar from "@/components/landing/Navbar";
import Hero from "@/components/landing/Hero";
import DifferenceSection from "@/components/landing/DifferenceSection";
import HowItWorks from "@/components/landing/HowItWorks";
import ProductShowcase from "@/components/landing/ProductShowcase";
import RecommendationSection from "@/components/landing/RecommendationSection";
import WhatIfSimulator from "@/components/landing/WhatIfSimulator";
import AIAssistant from "@/components/landing/AIAssistant";
import EmployerSection from "@/components/landing/EmployerSection";
import BrandStatement from "@/components/landing/BrandStatement";
import FinalCTA from "@/components/landing/FinalCTA";
import Footer from "@/components/landing/Footer";

export default function Home() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <DifferenceSection />
        <HowItWorks />
        <ProductShowcase />
        <RecommendationSection />
        <WhatIfSimulator />
        <AIAssistant />
        <EmployerSection />
        <BrandStatement />
        <FinalCTA />
      </main>
      <Footer />
    </>
  );
}
