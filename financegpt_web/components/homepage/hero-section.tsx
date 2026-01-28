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
			className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-4 py-10 md:px-8 md:py-20"
		>
			<BackgroundGrids />
			<FloatingCurrency
				symbol="$"
				delay={0}
				duration={15}
				initialX={-100}
				initialY={100}
				className="text-green-500/20 dark:text-green-400/10"
			/>
			<FloatingCurrency
				symbol="€"
				delay={2}
				duration={18}
				initialX={200}
				initialY={-50}
				className="text-blue-500/20 dark:text-blue-400/10"
			/>
			<FloatingCurrency
				symbol="£"
				delay={4}
				duration={20}
				initialX={-200}
				initialY={200}
				className="text-purple-500/20 dark:text-purple-400/10"
			/>
			<FloatingCurrency
				symbol="¥"
				delay={1}
				duration={16}
				initialX={100}
				initialY={50}
				className="text-orange-500/20 dark:text-orange-400/10"
			/>
			<FloatingCurrency
				symbol="₿"
				delay={3}
				duration={22}
				initialX={-50}
				initialY={-100}
				className="text-yellow-500/20 dark:text-yellow-400/10"
			/>

			<h2 className="relative z-50 mx-auto mb-4 mt-4 max-w-4xl text-balance text-center text-3xl font-semibold tracking-tight text-gray-700 md:text-7xl dark:text-neutral-300">
				<Balancer>
					Your AI-Powered{" "}
					<div className="relative mx-auto inline-block w-max filter-[drop-shadow(0px_1px_3px_rgba(27,37,80,0.14))]">
						<div className="text-black [text-shadow:0_0_rgba(0,0,0,0.1)] dark:text-white">
							<span className="">Financial Assistant</span>
						</div>
					</div>
				</Balancer>
			</h2>
			<p className="relative z-50 mx-auto mt-4 max-w-lg px-4 text-center text-base/6 text-gray-600 dark:text-gray-200">
				Connect your bank accounts, investments, and credit cards. Get AI-powered insights,
				optimize spending, and make smarter financial decisions.
			</p>
			<div className="mb-10 mt-8 flex w-full flex-col items-center justify-center gap-4 px-8 sm:flex-row md:mb-20">
				<GetStartedButton />
				{/* <Link
					href="/pricing"
					className="shadow-input group relative z-20 flex h-10 w-full cursor-pointer items-center justify-center space-x-2 rounded-lg bg-white p-px px-4 py-2 text-sm font-semibold leading-6 text-black no-underline transition duration-200 hover:-translate-y-0.5 sm:w-52 dark:bg-neutral-800 dark:text-white"
				>
					Start Free Trial
				</Link> */}
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
				className="group relative z-20 flex h-11 w-full cursor-pointer items-center justify-center gap-3 overflow-hidden rounded-xl bg-white px-6 py-2.5 text-sm font-semibold text-neutral-700 shadow-lg ring-1 ring-neutral-200/50 transition-shadow duration-300 hover:shadow-xl sm:w-56 dark:bg-neutral-900 dark:text-neutral-200 dark:ring-neutral-700/50"
				variants={{
					idle: { scale: 1, y: 0 },
					hover: { scale: 1.02, y: -2 },
				}}
			>
				{/* Animated gradient background on hover */}
				<motion.div
					className="absolute inset-0 bg-linear-to-r from-blue-50 via-green-50 to-yellow-50 dark:from-blue-950/30 dark:via-green-950/30 dark:to-yellow-950/30"
					variants={{
						idle: { opacity: 0 },
						hover: { opacity: 1 },
					}}
					transition={{ duration: 0.3 }}
				/>
				{/* Google logo with subtle animation */}
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
				className="group relative z-20 flex h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-black px-6 py-2.5 text-sm font-semibold text-white shadow-lg transition-shadow duration-300 hover:shadow-xl sm:w-56 dark:bg-white dark:text-black"
			>
				Get Started
			</Link>
		</motion.div>
	);
};

const FloatingCurrency = ({
	symbol,
	delay = 0,
	duration = 20,
	initialX = 0,
	initialY = 0,
	className = "",
}: {
	symbol: string;
	delay?: number;
	duration?: number;
	initialX?: number;
	initialY?: number;
	className?: string;
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
				x: [initialX, initialX + 100, initialX - 50, initialX + 150, initialX],
				y: [initialY, initialY - 200, initialY - 100, initialY - 300, initialY],
				opacity: [0, 0.3, 0.5, 0.3, 0],
				scale: [0.5, 1.2, 1, 1.5, 0.5],
				rotate: [0, 180, 360, 540, 720],
			}}
			transition={{
				duration: duration,
				repeat: Infinity,
				delay: delay,
				ease: "easeInOut",
			}}
			className={cn(
				"pointer-events-none absolute left-1/2 top-1/2 text-6xl font-bold md:text-8xl",
				className
			)}
		>
			{symbol}
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
