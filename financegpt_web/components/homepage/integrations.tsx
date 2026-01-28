"use client";
import React, { useEffect, useState } from "react";

interface Integration {
	name: string;
	icon: string;
}

const INTEGRATIONS: Integration[] = [
	// Banks
	{ name: "Chase", icon: "https://upload.wikimedia.org/wikipedia/commons/8/84/JPMorgan_Chase_Logo.svg" },
	{ name: "Bank of America", icon: "https://upload.wikimedia.org/wikipedia/commons/8/80/Bank_of_America_logo.svg" },
	{ name: "Wells Fargo", icon: "https://upload.wikimedia.org/wikipedia/commons/b/b3/Wells_Fargo_Bank.png" },
	{ name: "Citibank", icon: "https://upload.wikimedia.org/wikipedia/commons/1/1b/Citi.svg" },

	// Investment Platforms
	{ name: "Fidelity", icon: "https://upload.wikimedia.org/wikipedia/commons/6/6b/Fidelity_Investments_Logo.svg" },
	{ name: "Charles Schwab", icon: "https://upload.wikimedia.org/wikipedia/commons/9/9b/Charles_Schwab_Corporation_logo.svg" },
	{ name: "Vanguard", icon: "https://cdn.iconscout.com/icon/free/png-256/free-vanguard-logo-icon-download-in-svg-png-gif-file-formats--brand-company-world-logos-vol-1-pack-icons-282332.png" },
	{ name: "Robinhood", icon: "https://upload.wikimedia.org/wikipedia/commons/e/e4/Robinhood_logo.svg" },

	// Credit Cards
	{ name: "American Express", icon: "https://upload.wikimedia.org/wikipedia/commons/3/30/American_Express_logo.svg" },
	{ name: "Visa", icon: "https://cdn.simpleicons.org/visa/1A1F71" },
	{ name: "Mastercard", icon: "https://cdn.simpleicons.org/mastercard/EB001B" },
	{ name: "Discover", icon: "https://upload.wikimedia.org/wikipedia/commons/5/57/Discover_Card_logo.svg" },

	// Crypto
	{ name: "Coinbase", icon: "https://cdn.simpleicons.org/coinbase/0052FF" },
	{ name: "Binance", icon: "https://cdn.simpleicons.org/binance/F3BA2F" },

	// Payment Platforms
	{ name: "PayPal", icon: "https://cdn.simpleicons.org/paypal/00457C" },
	{ name: "Venmo", icon: "https://cdn.simpleicons.org/venmo/3D95CE" },
	{ name: "Stripe", icon: "https://cdn.simpleicons.org/stripe/008CDD" },

	// More Banks
	{ name: "Capital One", icon: "https://upload.wikimedia.org/wikipedia/commons/9/98/Capital_One_logo.svg" },
	{ name: "US Bank", icon: "https://upload.wikimedia.org/wikipedia/commons/4/40/US_Bank_logo_%282018%29.svg" },
	{ name: "PNC Bank", icon: "https://upload.wikimedia.org/wikipedia/commons/b/b4/PNC_Bank_logo.svg" },
];

function SemiCircleOrbit({ radius, centerX, centerY, count, iconSize, startIndex }: any) {
	return (
		<>
			{/* Semi-circle glow background */}
			<div className="absolute inset-0 flex justify-center items-start overflow-visible">
				<div
					className="
            w-[800px] h-[800px] rounded-full 
            bg-[radial-gradient(circle_at_center,rgba(0,0,0,0.15),transparent_70%)]
            dark:bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.15),transparent_70%)]
            blur-3xl 
            pointer-events-none
          "
					style={{
						zIndex: 0,
						transform: "translateY(-20%)",
					}}
				/>
			</div>

			{/* Orbit icons */}
			{Array.from({ length: count }).map((_, index) => {
				const actualIndex = startIndex + index;
				// Skip if we've run out of integrations
				if (actualIndex >= INTEGRATIONS.length) return null;

				const angle = (index / (count - 1)) * 180;
				const x = radius * Math.cos((angle * Math.PI) / 180);
				const y = radius * Math.sin((angle * Math.PI) / 180);
				const integration = INTEGRATIONS[actualIndex];

				// Tooltip positioning — above or below based on angle
				const tooltipAbove = angle > 90;

				return (
					<div
						key={index}
						className="absolute flex flex-col items-center group"
						style={{
							left: `${centerX + x - iconSize / 2}px`,
							top: `${centerY - y - iconSize / 2}px`,
							zIndex: 5,
						}}
					>
						<img
							src={integration.icon}
							alt={integration.name}
							width={iconSize}
							height={iconSize}
							className="object-contain cursor-pointer transition-transform hover:scale-110"
							style={{ minWidth: iconSize, minHeight: iconSize }} // fix accidental shrink
						/>

						{/* Tooltip */}
						<div
							className={`absolute ${
								tooltipAbove ? "bottom-[calc(100%+8px)]" : "top-[calc(100%+8px)]"
							} hidden group-hover:block w-auto min-w-max rounded-lg bg-black px-3 py-1.5 text-xs text-white shadow-lg text-center whitespace-nowrap`}
						>
							{integration.name}
							<div
								className={`absolute left-1/2 -translate-x-1/2 w-3 h-3 rotate-45 bg-black ${
									tooltipAbove ? "top-full" : "bottom-full"
								}`}
							></div>
						</div>
					</div>
				);
			})}
		</>
	);
}

export default function ExternalIntegrations() {
	const [size, setSize] = useState({ width: 0, height: 0 });

	useEffect(() => {
		const updateSize = () => setSize({ width: window.innerWidth, height: window.innerHeight });
		updateSize();
		window.addEventListener("resize", updateSize);
		return () => window.removeEventListener("resize", updateSize);
	}, []);

	const baseWidth = Math.min(size.width * 0.8, 700);
	const centerX = baseWidth / 2;
	const centerY = baseWidth * 0.5;

	const iconSize =
		size.width < 480
			? Math.max(24, baseWidth * 0.05)
			: size.width < 768
				? Math.max(28, baseWidth * 0.06)
				: Math.max(32, baseWidth * 0.07);

	return (
		<section className="py-8 relative w-full overflow-visible">
			<div className="relative flex flex-col items-center text-center z-10">
				<h1 className="my-4 text-4xl font-bold lg:text-7xl">Integrations</h1>
				<p className="mb-12 max-w-2xl text-gray-600 dark:text-gray-400 lg:text-xl">
					Integrate with your team's most important tools
				</p>

				<div
					className="relative overflow-visible"
					style={{ width: baseWidth, height: baseWidth * 0.7, paddingBottom: "100px" }}
				>
					<SemiCircleOrbit
						radius={baseWidth * 0.22}
						centerX={centerX}
						centerY={centerY}
						count={5}
						iconSize={iconSize}
						startIndex={0}
					/>
					<SemiCircleOrbit
						radius={baseWidth * 0.36}
						centerX={centerX}
						centerY={centerY}
						count={6}
						iconSize={iconSize}
						startIndex={5}
					/>
					<SemiCircleOrbit
						radius={baseWidth * 0.5}
						centerX={centerX}
						centerY={centerY}
						count={8}
						iconSize={iconSize}
						startIndex={11}
					/>
				</div>
			</div>
		</section>
	);
}
