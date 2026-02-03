import type { Metadata } from "next";
import "./globals.css";
import { RootProvider } from "fumadocs-ui/provider/next";
import { Roboto } from "next/font/google";
import { ElectricProvider } from "@/components/providers/ElectricProvider";
import { I18nProvider } from "@/components/providers/I18nProvider";
import { PostHogProvider } from "@/components/providers/PostHogProvider";
import { ThemeProvider } from "@/components/theme/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { LocaleProvider } from "@/contexts/LocaleContext";
import { ReactQueryClientProvider } from "@/lib/query-client/query-client.provider";
import { cn } from "@/lib/utils";

const roboto = Roboto({
	subsets: ["latin"],
	weight: ["400", "500", "700"],
	display: "swap",
	variable: "--font-roboto",
});

export const metadata: Metadata = {
	title: "FinanceGPT – Customizable AI Research & Knowledge Management Assistant",
	description:
		"FinanceGPT is an AI-powered research assistant that integrates with tools like Notion, GitHub, Slack, and more to help you efficiently manage, search, and chat with your documents. Generate podcasts, perform hybrid search, and unlock insights from your knowledge base.",
	keywords: [
		"FinanceGPT",
		"AI research assistant",
		"AI knowledge management",
		"AI document assistant",
		"customizable AI assistant",
		"notion integration",
		"slack integration",
		"github integration",
		"hybrid search",
		"vector search",
		"RAG",
		"LangChain",
		"FastAPI",
		"LLM apps",
		"AI document chat",
		"knowledge management AI",
		"AI-powered document search",
		"personal AI assistant",
		"AI research tools",
		"AI podcast generator",
		"AI knowledge base",
		"AI document assistant tools",
		"AI-powered search assistant",
	]
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	// Using client-side i18n
	// Language can be switched dynamically through LanguageSwitcher component
	// Locale state is managed by LocaleContext and persisted in localStorage
	return (
		<html lang="en" suppressHydrationWarning>
			<body className={cn(roboto.className, "bg-white dark:bg-black antialiased h-full w-full ")}>
				<PostHogProvider>
					<LocaleProvider>
						<I18nProvider>
							<ThemeProvider
								attribute="class"
								enableSystem
								disableTransitionOnChange
								defaultTheme="light"
							>
								<RootProvider>
									<ReactQueryClientProvider>
										<ElectricProvider>{children}</ElectricProvider>
									</ReactQueryClientProvider>
									<Toaster />
								</RootProvider>
							</ThemeProvider>
						</I18nProvider>
					</LocaleProvider>
				</PostHogProvider>
			</body>
		</html>
	);
}
