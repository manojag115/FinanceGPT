import { Activity, CreditCard, Shield, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";

export function FeaturesCards() {
	return (
		<section id="features" className="relative py-20 md:py-32">
			<div className="mx-auto max-w-7xl px-4 md:px-8">
				<div className="mx-auto max-w-3xl text-center">
					<h2 className="mb-4 text-4xl font-bold tracking-tight text-gray-900 md:text-5xl dark:text-white">
						Everything you need to{" "}
					<span className="bg-linear-to-r from-emerald-600 to-teal-600 bg-clip-text text-transparent dark:from-emerald-400 dark:to-teal-400">
							master your finances
						</span>
					</h2>
					<p className="text-lg text-gray-600 dark:text-gray-300">
						Powerful features designed to give you complete control over your financial life
					</p>
				</div>

				<div className="mt-16 grid gap-8 md:grid-cols-2 lg:grid-cols-4">
					<FeatureCard
						icon={<TrendingUp className="h-6 w-6" />}
						title="Smart Tracking"
						description="Automatically categorize transactions and track spending across all your accounts in real-time."
						gradient="from-emerald-500 to-teal-500"
					/>
					<FeatureCard
						icon={<Activity className="h-6 w-6" />}
						title="AI Insights"
						description="Get personalized recommendations and actionable insights powered by advanced AI algorithms."
						gradient="from-blue-500 to-cyan-500"
					/>
					<FeatureCard
						icon={<CreditCard className="h-6 w-6" />}
						title="Reward Optimizer"
						description="Maximize cashback and points by using the right card for every purchase automatically."
						gradient="from-violet-500 to-purple-500"
					/>
					<FeatureCard
						icon={<Shield className="h-6 w-6" />}
						title="Bank-Level Security"
						description="Your data is encrypted and protected with the same security used by major financial institutions."
						gradient="from-orange-500 to-amber-500"
					/>
				</div>
			</div>
		</section>
	);
}

const FeatureCard = ({
	icon,
	title,
	description,
	gradient,
}: {
	icon: ReactNode;
	title: string;
	description: string;
	gradient: string;
}) => (
	<div className="group relative overflow-hidden rounded-2xl border border-gray-200 bg-white p-6 transition-all duration-300 hover:-translate-y-1 hover:shadow-xl dark:border-gray-800 dark:bg-gray-900">
		{/* Gradient accent on hover */}
		<div
			className={`absolute inset-0 bg-linear-to-br ${gradient} opacity-0 transition-opacity duration-300 group-hover:opacity-5`}
		/>
		
		{/* Icon */}
		<div className={`mb-4 inline-flex rounded-xl bg-linear-to-br ${gradient} p-3 text-white shadow-lg`}>
			{icon}
		</div>

		{/* Content */}
		<h3 className="mb-2 text-xl font-semibold text-gray-900 dark:text-white">{title}</h3>
		<p className="text-sm leading-relaxed text-gray-600 dark:text-gray-400">{description}</p>
	</div>
);
