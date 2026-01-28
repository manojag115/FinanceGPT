"use client";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import React, { useRef } from "react";
import Balancer from "react-wrap-balancer";
import { AUTH_TYPE, BACKEND_URL } from "@/lib/env-config";
import { trackLoginAttempt } from "@/lib/posthog/events";
import { cn } from "@/lib/utils";

// Official Google "G" logo with brand colors
const GoogleLogo = ({ className }: { className?: string }) => (
	<svg className={className} viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
		<path
			d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
			fill="#4285F4"
		/>
		<path
			d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
			fill="#34A853"
		/>
		<path
			d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
			fill="#FBBC05"
		/>
		<path
			d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
			fill="#EA4335"
		/>
	</svg>
);

export function HeroSection() {
	const containerRef = useRef<HTMLDivElement>(null);
	const parentRef = useRef<HTMLDivElement>(null);

	return (
		<div
			ref={parentRef}
			className="relative min-h-screen overflow-hidden bg-linear-to-br from-emerald-50 via-teal-50/50 to-blue-50 dark:from-gray-950 dark:via-emerald-950/10 dark:to-blue-950/10"
		>
			<div className="mx-auto grid min-h-screen max-w-7xl grid-cols-1 items-center gap-12 px-4 py-12 md:px-8 lg:grid-cols-2 lg:gap-16">
				{/* Left side - Content */}
				<div className="relative z-10 space-y-8 lg:pr-8">
					{/* Badge */}
					<motion.div
						initial={{ opacity: 0, x: -20 }}
						animate={{ opacity: 1, x: 0 }}
						transition={{ duration: 0.6 }}
						className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-1.5 text-sm font-medium text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-300"
					>
						<span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
						AI-Powered Finance Management
					</motion.div>

					{/* Main heading */}
					<motion.h1
						initial={{ opacity: 0, x: -20 }}
						animate={{ opacity: 1, x: 0 }}
						transition={{ duration: 0.6, delay: 0.1 }}
						className="text-5xl font-bold leading-tight tracking-tight text-gray-900 md:text-6xl lg:text-7xl dark:text-white"
					>
						<Balancer>
							Your Money,{" "}
							<span className="bg-linear-to-r from-emerald-600 via-teal-600 to-blue-600 bg-clip-text text-transparent dark:from-emerald-400 dark:via-teal-400 dark:to-blue-400">
								Simplified
							</span>{" "}
							by AI
						</Balancer>
					</motion.h1>

					{/* Description */}
					<motion.p
						initial={{ opacity: 0, x: -20 }}
						animate={{ opacity: 1, x: 0 }}
						transition={{ duration: 0.6, delay: 0.2 }}
						className="text-lg leading-relaxed text-gray-600 md:text-xl dark:text-gray-300"
					>
						Connect all your financial accounts in one place. Get personalized insights, track
						spending patterns, and maximize your wealth with AI-powered recommendations.
					</motion.p>

					{/* CTA Buttons */}
					<motion.div
						initial={{ opacity: 0, x: -20 }}
						animate={{ opacity: 1, x: 0 }}
						transition={{ duration: 0.6, delay: 0.3 }}
						className="flex flex-col gap-4 sm:flex-row"
					>
						<GetStartedButton />
						<Link
							href="#features"
							className="group flex h-11 items-center justify-center gap-2 rounded-xl border-2 border-gray-200 bg-white px-6 py-2.5 text-sm font-semibold text-gray-700 transition-all duration-300 hover:border-gray-300 hover:shadow-lg dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:border-gray-600"
						>
							Learn More
							<svg
								className="h-4 w-4 transition-transform group-hover:translate-x-1"
								fill="none"
								viewBox="0 0 24 24"
								stroke="currentColor"
							>
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
							</svg>
						</Link>
					</motion.div>

					{/* Trust indicators */}
					<motion.div
						initial={{ opacity: 0, x: -20 }}
						animate={{ opacity: 1, x: 0 }}
						transition={{ duration: 0.6, delay: 0.4 }}
						className="flex flex-wrap gap-6 text-sm text-gray-500 dark:text-gray-400"
					>
						<div className="flex items-center gap-2">
							<svg className="h-5 w-5 text-emerald-600" fill="currentColor" viewBox="0 0 20 20">
								<path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5c.11.65.166 1.32.166 2.001 0 5.225-3.34 9.67-8 11.317C5.34 16.67 2 12.225 2 7c0-.682.057-1.35.166-2.001zm11.541 3.708a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
							</svg>
							<span>Bank-Level Security</span>
						</div>
						<div className="flex items-center gap-2">
							<svg className="h-5 w-5 text-emerald-600" fill="currentColor" viewBox="0 0 20 20">
								<path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd" />
							</svg>
							<span>AI-Powered</span>
						</div>
					</motion.div>
				</div>

				{/* Right side - Visual */}
				<motion.div
					initial={{ opacity: 0, x: 20 }}
					animate={{ opacity: 1, x: 0 }}
					transition={{ duration: 0.8, delay: 0.2 }}
					className="relative hidden lg:block"
				>
					{/* Gradient orbs background */}
					<div className="pointer-events-none absolute inset-0">
						<div className="absolute left-0 top-0 h-72 w-72 rounded-full bg-linear-to-br from-emerald-400/30 to-teal-400/30 blur-3xl dark:from-emerald-600/20 dark:to-teal-600/20" />
						<div className="absolute right-0 top-1/4 h-72 w-72 rounded-full bg-linear-to-br from-blue-400/30 to-cyan-400/30 blur-3xl dark:from-blue-600/20 dark:to-cyan-600/20" />
					</div>

					{/* Floating cards */}
					<div className="relative space-y-4">
						<motion.div
							animate={{ y: [0, -10, 0] }}
							transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
							className="rounded-2xl border border-gray-200 bg-white p-6 shadow-lg dark:border-gray-800 dark:bg-gray-900"
						>
							<div className="mb-3 flex items-center gap-3">
								<div className="flex h-12 w-12 items-center justify-center rounded-xl bg-linear-to-br from-emerald-500 to-teal-500 text-2xl">
									💰
								</div>
								<div>
									<p className="text-sm font-semibold text-gray-900 dark:text-white">Total Balance</p>
									<p className="text-xs text-gray-500 dark:text-gray-400">All Accounts</p>
								</div>
							</div>
							<p className="text-3xl font-bold text-gray-900 dark:text-white">$124,567</p>
							<p className="mt-1 text-sm text-emerald-600">+12.5% this month</p>
						</motion.div>

						<motion.div
							animate={{ y: [0, 10, 0] }}
							transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
							className="ml-auto w-4/5 rounded-2xl border border-gray-200 bg-white p-6 shadow-lg dark:border-gray-800 dark:bg-gray-900"
						>
							<div className="mb-3 flex items-center gap-3">
								<div className="flex h-12 w-12 items-center justify-center rounded-xl bg-linear-to-br from-blue-500 to-cyan-500 text-2xl">
									📊
								</div>
								<div>
									<p className="text-sm font-semibold text-gray-900 dark:text-white">AI Insight</p>
									<p className="text-xs text-gray-500 dark:text-gray-400">Just now</p>
								</div>
							</div>
							<p className="text-sm text-gray-600 dark:text-gray-300">
								You could save $240/mo by switching to the Sapphire card for groceries
							</p>
						</motion.div>

						<motion.div
							animate={{ y: [0, -8, 0] }}
							transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut", delay: 1 }}
							className="w-3/4 rounded-2xl border border-gray-200 bg-white p-6 shadow-lg dark:border-gray-800 dark:bg-gray-900"
						>
							<div className="mb-3 flex items-center gap-3">
								<div className="flex h-12 w-12 items-center justify-center rounded-xl bg-linear-to-br from-violet-500 to-purple-500 text-2xl">
									💳
								</div>
								<div>
									<p className="text-sm font-semibold text-gray-900 dark:text-white">Rewards Earned</p>
									<p className="text-xs text-gray-500 dark:text-gray-400">This quarter</p>
								</div>
							</div>
							<p className="text-2xl font-bold text-gray-900 dark:text-white">$1,847</p>
							<p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Cashback & Points</p>
						</motion.div>
					</div>
				</motion.div>
			</div>
		</div>
	);
}

function GetStartedButton() {
	const isGoogleAuth = AUTH_TYPE === "GOOGLE";

	const handleGoogleLogin = () => {
		trackLoginAttempt("google");
		window.location.href = `${BACKEND_URL}/auth/google/authorize-redirect`;
	};

	if (isGoogleAuth) {
		return (
			<motion.button
				type="button"
				onClick={handleGoogleLogin}
				whileHover="hover"
				whileTap={{ scale: 0.98 }}
				initial="idle"
					className="group relative z-20 flex h-11 w-full cursor-pointer items-center justify-center gap-3 overflow-hidden rounded-xl bg-linear-to-r from-emerald-600 to-teal-600 px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-emerald-500/30 transition-shadow duration-300 hover:shadow-xl hover:shadow-emerald-500/40 sm:w-56 dark:from-emerald-500 dark:to-teal-500 dark:shadow-emerald-500/20"
				variants={{
					idle: { scale: 1, y: 0 },
					hover: { scale: 1.02, y: -2 },
				}}
			>
				<motion.div
					className="relative"
					variants={{
						idle: { rotate: 0 },
						hover: { rotate: [0, -8, 8, 0] },
					}}
					transition={{ duration: 0.4, ease: "easeInOut" }}
				>
					<GoogleLogo className="h-5 w-5" />
				</motion.div>
				<span className="relative">Continue with Google</span>
			</motion.button>
		);
	}

	return (
		<motion.div whileHover={{ scale: 1.02, y: -2 }} whileTap={{ scale: 0.98 }}>
			<Link
				href="/register"
				className="group relative z-20 flex h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-linear-to-r from-emerald-600 to-teal-600 px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-emerald-500/30 transition-shadow duration-300 hover:shadow-xl hover:shadow-emerald-500/40 sm:w-56 dark:from-emerald-500 dark:to-teal-500"
			>
				Get Started Free
				<svg
					className="h-4 w-4 transition-transform group-hover:translate-x-1"
					fill="none"
					viewBox="0 0 24 24"
					stroke="currentColor"
				>
					<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
				</svg>
			</Link>
		</motion.div>
	);
}

const FloatingIcon = ({
	icon,
	delay = 0,
	duration = 20,
	initialX = 0,
	initialY = 0,
}: {
	icon: string;
	delay?: number;
	duration?: number;
	initialX?: number;
	initialY?: number;
}) => {
	return (
		<motion.div
			initial={{
				x: initialX,
				y: initialY,
				opacity: 0,
				scale: 0.5,
			}}
			animate={{
				x: [initialX, initialX + 80, initialX - 40, initialX + 120, initialX],
				y: [initialY, initialY - 150, initialY - 80, initialY - 200, initialY],
				opacity: [0, 0.4, 0.6, 0.4, 0],
				scale: [0.5, 1, 0.9, 1.1, 0.5],
				rotate: [0, 90, 180, 270, 360],
			}}
			transition={{
				duration: duration,
				repeat: Infinity,
				delay: delay,
				ease: "easeInOut",
			}}
			className="pointer-events-none absolute left-1/2 top-1/2 text-5xl opacity-30 md:text-6xl"
		>
			{icon}
		</motion.div>
	);
};

const BackgroundGrids = () => {
	return (
		<div className="pointer-events-none absolute inset-0 z-0 grid h-full w-full -rotate-45 transform select-none grid-cols-2 gap-10 md:grid-cols-4">
			<div className="relative h-full w-full">
				<GridLineVertical className="left-0" />
				<GridLineVertical className="left-auto right-0" />
			</div>
			<div className="relative h-full w-full">
				<GridLineVertical className="left-0" />
				<GridLineVertical className="left-auto right-0" />
			</div>
			<div className="relative h-full w-full bg-linear-to-b from-transparent via-neutral-100 to-transparent dark:via-neutral-800">
				<GridLineVertical className="left-0" />
				<GridLineVertical className="left-auto right-0" />
			</div>
			<div className="relative h-full w-full">
				<GridLineVertical className="left-0" />
				<GridLineVertical className="left-auto right-0" />
			</div>
		</div>
	);
};

const GridLineVertical = ({ className, offset }: { className?: string; offset?: string }) => {
	return (
		<div
			style={
				{
					"--background": "#ffffff",
					"--color": "rgba(0, 0, 0, 0.2)",
					"--height": "5px",
					"--width": "1px",
					"--fade-stop": "90%",
					"--offset": offset || "150px", //-100px if you want to keep the line inside
					"--color-dark": "rgba(255, 255, 255, 0.3)",
					maskComposite: "exclude",
				} as React.CSSProperties
			}
			className={cn(
				"absolute top-[calc(var(--offset)/2*-1)] h-[calc(100%+var(--offset))] w-(--width)",
				"bg-[linear-gradient(to_bottom,var(--color),var(--color)_50%,transparent_0,transparent)]",
				"bg-size-[var(--width)_var(--height)]",
				"[mask:linear-gradient(to_top,var(--background)_var(--fade-stop),transparent),linear-gradient(to_bottom,var(--background)_var(--fade-stop),transparent),linear-gradient(black,black)]",
				"mask-exclude",
				"z-30",
				"dark:bg-[linear-gradient(to_bottom,var(--color-dark),var(--color-dark)_50%,transparent_0,transparent)]",
				className
			)}
		></div>
	);
};
