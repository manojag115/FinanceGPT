"use client";
import { motion } from "motion/react";

export function StatsSection() {
	const stats = [
		{ number: "100K+", label: "Active Users" },
		{ number: "$2.5B+", label: "Money Managed" },
		{ number: "150+", label: "Bank Integrations" },
		{ number: "4.9/5", label: "User Rating" },
	];

	return (
		<section className="border-y border-gray-200 bg-white py-16 dark:border-gray-800 dark:bg-gray-950">
			<div className="mx-auto max-w-7xl px-4 md:px-8">
				<div className="grid grid-cols-2 gap-8 md:grid-cols-4">
					{stats.map((stat, index) => (
						<motion.div
							key={index}
							initial={{ opacity: 0, y: 20 }}
							whileInView={{ opacity: 1, y: 0 }}
							viewport={{ once: true }}
							transition={{ duration: 0.5, delay: index * 0.1 }}
							className="text-center"
						>
							<p className="mb-2 bg-linear-to-r from-emerald-600 to-teal-600 bg-clip-text text-4xl font-bold text-transparent md:text-5xl dark:from-emerald-400 dark:to-teal-400">
								{stat.number}
							</p>
							<p className="text-sm text-gray-600 md:text-base dark:text-gray-400">{stat.label}</p>
						</motion.div>
					))}
				</div>
			</div>
		</section>
	);
}
