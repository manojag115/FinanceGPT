"use client";

import { CTAHomepage } from "@/components/homepage/cta";
import { FeaturesBentoGrid } from "@/components/homepage/features-bento-grid";
import { FeaturesCards } from "@/components/homepage/features-card";
import { HeroSection } from "@/components/homepage/hero-section";
import ExternalIntegrations from "@/components/homepage/integrations";
// import { StatsSection } from "@/components/homepage/stats-section";

export default function HomePage() {
	return (
		<main className="min-h-screen overflow-x-hidden bg-white dark:bg-gray-950">
			<HeroSection />
			{/* <StatsSection /> */}
			<ExternalIntegrations />
			<FeaturesCards />
			{/* <CTAHomepage /> */}
		</main>
	);
}
