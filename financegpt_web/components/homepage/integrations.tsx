"use client";
import { motion } from "motion/react";
import React from "react";

interface Integration {
	name: string;
	icon: string;
	category: string;
}

const INTEGRATIONS: Integration[] = [
	// Banks
	{ name: "Chase", icon: "https://upload.wikimedia.org/wikipedia/commons/8/84/JPMorgan_Chase_Logo.svg", category: "Banking" },
	{ name: "Bank of America", icon: "https://upload.wikimedia.org/wikipedia/commons/8/80/Bank_of_America_logo.svg", category: "Banking" },
	{ name: "Wells Fargo", icon: "https://upload.wikimedia.org/wikipedia/commons/b/b3/Wells_Fargo_Bank.png", category: "Banking" },
	{ name: "Citibank", icon: "https://upload.wikimedia.org/wikipedia/commons/1/1b/Citi.svg", category: "Banking" },
	{ name: "Capital One", icon: "https://upload.wikimedia.org/wikipedia/commons/9/98/Capital_One_logo.svg", category: "Banking" },

	// Investment Platforms
	{ name: "Fidelity", icon: "https://upload.wikimedia.org/wikipedia/commons/6/6b/Fidelity_Investments_Logo.svg", category: "Investing" },
	{ name: "Charles Schwab", icon: "https://upload.wikimedia.org/wikipedia/commons/9/9b/Charles_Schwab_Corporation_logo.svg", category: "Investing" },
	{ name: "Vanguard", icon: "https://cdn.iconscout.com/icon/free/png-256/free-vanguard-logo-icon-download-in-svg-png-gif-file-formats--brand-company-world-logos-vol-1-pack-icons-282332.png", category: "Investing" },
	{ name: "Robinhood", icon: "https://upload.wikimedia.org/wikipedia/commons/e/e4/Robinhood_logo.svg", category: "Investing" },

	// Credit Cards
	{ name: "American Express", icon: "https://upload.wikimedia.org/wikipedia/commons/3/30/American_Express_logo.svg", category: "Credit Cards" },
	{ name: "Visa", icon: "https://cdn.simpleicons.org/visa/1A1F71", category: "Credit Cards" },
	{ name: "Mastercard", icon: "https://cdn.simpleicons.org/mastercard/EB001B", category: "Credit Cards" },
	{ name: "Discover", icon: "https://upload.wikimedia.org/wikipedia/commons/5/57/Discover_Card_logo.svg", category: "Credit Cards" },

	// Crypto
	{ name: "Coinbase", icon: "https://cdn.simpleicons.org/coinbase/0052FF", category: "Crypto" },
	{ name: "Binance", icon: "https://cdn.simpleicons.org/binance/F3BA2F", category: "Crypto" },

	// Payment Platforms
	{ name: "PayPal", icon: "https://cdn.simpleicons.org/paypal/00457C", category: "Payments" },
	{ name: "Venmo", icon: "https://cdn.simpleicons.org/venmo/3D95CE", category: "Payments" },
	{ name: "Stripe", icon: "https://cdn.simpleicons.org/stripe/008CDD", category: "Payments" },
];


export default function ExternalIntegrations() {
	return (
		<section className="relative overflow-hidden bg-gray-50 py-20 md:py-32 dark:bg-gray-900">
			<div className="mx-auto max-w-7xl px-4 md:px-8">
				{/* Header - Left aligned */}
				<div className="mb-16 max-w-2xl">
					<h2 className="mb-4 text-4xl font-bold tracking-tight text-gray-900 md:text-5xl dark:text-white">
						Several Financial{" "}
						<span className="bg-linear-to-r from-emerald-600 to-teal-600 bg-clip-text text-transparent dark:from-emerald-400 dark:to-teal-400">
							Integrations
						</span>
					</h2>
					<p className="text-lg text-gray-600 dark:text-gray-300">
						Securely connect your accounts from banks, investment platforms, credit cards, and more
					</p>
				</div>

				{/* Grid of logos */}
				<div className="grid grid-cols-3 gap-6 md:grid-cols-4 lg:grid-cols-6">
					{INTEGRATIONS.map((integration, index) => (
						<motion.div
							key={integration.name}
							initial={{ opacity: 0, y: 20 }}
							whileInView={{ opacity: 1, y: 0 }}
							viewport={{ once: true }}
							transition={{ duration: 0.5, delay: index * 0.05 }}
							className="group relative flex h-24 items-center justify-center rounded-xl border border-gray-200 bg-white p-4 transition-all duration-300 hover:-translate-y-1 hover:shadow-lg dark:border-gray-800 dark:bg-gray-950"
						>
							<img
								src={integration.icon}
								alt={integration.name}
								className="max-h-10 max-w-full object-contain opacity-70 transition-opacity duration-300 group-hover:opacity-100"
							/>
							<div className="pointer-events-none absolute -bottom-12 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap rounded-lg bg-gray-900 px-3 py-1.5 text-xs text-white opacity-0 transition-opacity duration-200 group-hover:opacity-100 dark:bg-gray-700">
								{integration.name}
							</div>
						</motion.div>
					))}
				</div>

				{/* Bottom text */}
				<motion.div
					initial={{ opacity: 0 }}
					whileInView={{ opacity: 1 }}
					viewport={{ once: true }}
					transition={{ duration: 0.8, delay: 0.5 }}
					className="mt-16 text-center"
				>
					<p className="text-sm text-gray-500 dark:text-gray-400">
						🔒 All connections are encrypted with 256-bit SSL encryption
					</p>
				</motion.div>
			</div>
		</section>
	);
}
