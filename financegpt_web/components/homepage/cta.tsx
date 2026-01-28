"use client";
import Link from "next/link";
import type React from "react";

export function CTAHomepage() {
	return (
		<section className="relative py-20 md:py-32">
			<div className="mx-auto max-w-7xl px-4 md:px-8">
				<div className="relative overflow-hidden rounded-3xl border border-gray-200 bg-linear-to-br from-emerald-50 via-teal-50 to-blue-50 p-12 md:p-20 dark:border-gray-800 dark:from-emerald-950/50 dark:via-teal-950/50 dark:to-blue-950/50">
					{/* Background decorative elements */}
					<div className="pointer-events-none absolute inset-0 overflow-hidden">
						<div className="absolute -right-1/4 top-0 h-96 w-96 rounded-full bg-linear-to-br from-emerald-400/20 to-teal-400/20 blur-3xl" />
						<div className="absolute -left-1/4 bottom-0 h-96 w-96 rounded-full bg-linear-to-br from-blue-400/20 to-cyan-400/20 blur-3xl" />
					</div>

					{/* Content */}
					<div className="relative z-10 mx-auto max-w-3xl text-center">
						<h2 className="mb-6 text-4xl font-bold tracking-tight text-gray-900 md:text-5xl dark:text-white">
							Ready to take control of your finances?
						</h2>
						<p className="mb-10 text-lg text-gray-700 md:text-xl dark:text-gray-200">
							Join thousands of users who are already using FinanceGPT to make smarter financial
							decisions. Get started in minutes.
						</p>

						<div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
							<Link
								href="/register"
							className="group flex h-12 items-center gap-2 rounded-xl bg-linear-to-r from-emerald-600 to-teal-600 px-8 py-3 text-base font-semibold text-white shadow-lg shadow-emerald-500/30 transition-all duration-300 hover:shadow-xl hover:shadow-emerald-500/40 dark:from-emerald-500 dark:to-teal-500"
							>
								Start Free Today
								<svg
									className="h-5 w-5 transition-transform group-hover:translate-x-1"
									fill="none"
									viewBox="0 0 24 24"
									stroke="currentColor"
								>
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
								</svg>
							</Link>
							<Link
								href="/contact"
								className="flex h-12 items-center gap-2 rounded-xl border-2 border-gray-300 bg-white px-8 py-3 text-base font-semibold text-gray-700 transition-all duration-300 hover:border-gray-400 hover:shadow-lg dark:border-gray-600 dark:bg-gray-900 dark:text-gray-200 dark:hover:border-gray-500"
							>
								Contact Sales
							</Link>
						</div>

						<p className="mt-8 text-sm text-gray-600 dark:text-gray-400">
							No credit card required • Free forever plan available
						</p>
					</div>
				</div>
			</div>
		</section>
	);
}
