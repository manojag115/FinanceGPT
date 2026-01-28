import { Sliders, Users, Workflow } from "lucide-react";
import type { ReactNode } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export function FeaturesCards() {
	return (
		<section className="py-4 md:py-12 dark:bg-transparent">
			<div className="@container mx-auto max-w-7xl">
				<div className="text-center">
					<h2 className="text-balance text-4xl font-semibold lg:text-5xl">
						Personal Finance Made Intelligent
					</h2>
					<p className="mt-4">
						Powerful AI features to help you track spending, optimize credit cards, and grow your wealth.
					</p>
				</div>
				<div className="@min-4xl:max-w-full @min-4xl:grid-cols-3 mx-auto mt-8 grid max-w-sm gap-6 *:text-center md:mt-16">
					<Card className="group shadow-black-950/5">
						<CardHeader className="pb-3">
							<CardDecorator>
								<Workflow className="size-6" aria-hidden />
							</CardDecorator>

							<h3 className="mt-6 font-medium">Connected Finances</h3>
						</CardHeader>

						<CardContent>
							<p className="text-sm">
								Securely connect all your bank accounts, credit cards, and investments in one place.
								See your complete financial picture at a glance.
							</p>
						</CardContent>
					</Card>

					<Card className="group shadow-black-950/5">
						<CardHeader className="pb-3">
							<CardDecorator>
								<Users className="size-6" aria-hidden />
							</CardDecorator>

							<h3 className="mt-6 font-medium">Smart AI Insights</h3>
						</CardHeader>

						<CardContent>
							<p className="text-sm">
								Chat with your finances using natural language. Find subscriptions, track spending patterns,
								and get personalized recommendations.
							</p>
						</CardContent>
					</Card>

					<Card className="group shadow-black-950/5">
						<CardHeader className="pb-3">
							<CardDecorator>
								<Sliders className="size-6" aria-hidden />
							</CardDecorator>

							<h3 className="mt-6 font-medium">Maximize Rewards</h3>
						</CardHeader>

						<CardContent>
							<p className="text-sm">
								Optimize credit card rewards based on your spending. Never miss out on cashback
								or points again.
							</p>
						</CardContent>
					</Card>
				</div>
			</div>
		</section>
	);
}

const CardDecorator = ({ children }: { children: ReactNode }) => (
	<div
		aria-hidden
		className="relative mx-auto size-36 [mask-image:radial-gradient(ellipse_50%_50%_at_50%_50%,#000_70%,transparent_100%)]"
	>
		<div className="absolute inset-0 [--border:black] dark:[--border:white] bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:24px_24px] opacity-10" />
		<div className="bg-background absolute inset-0 m-auto flex size-12 items-center justify-center border-t border-l">
			{children}
		</div>
	</div>
);
