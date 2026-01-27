"use client";


import type { FC } from "react";
import { DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

interface ConnectorDialogHeaderProps {
	activeTab: string;
	totalSourceCount: number;
	totalDocumentCount: number;
	onTabChange: (value: string) => void;
	isScrolled: boolean;
}

export const ConnectorDialogHeader: FC<ConnectorDialogHeaderProps> = ({
	totalSourceCount,
	totalDocumentCount,
	isScrolled,
}) => {
	return (
		<div
			className={cn(
				"flex-shrink-0 px-4 sm:px-12 pt-5 sm:pt-10 transition-shadow duration-200 relative z-10",
				isScrolled && "shadow-xl bg-muted/50 backdrop-blur-md"
			)}
		>
			<DialogHeader>
				<DialogTitle className="text-xl sm:text-3xl font-semibold tracking-tight">
					Connections
				</DialogTitle>
				<DialogDescription className="text-xs sm:text-base text-muted-foreground/80 mt-1 sm:mt-1.5">
					Search across all your accounts and documents in one place.
				</DialogDescription>
			</DialogHeader>

			<div className="flex flex-col-reverse sm:flex-row sm:items-end justify-between gap-4 sm:gap-8 mt-4 sm:mt-8 border-b border-border/80 dark:border-white/5">
				<TabsList className="bg-transparent p-0 gap-4 sm:gap-8 h-auto w-full sm:w-auto justify-center sm:justify-start">
					<TabsTrigger
						value="all"
						className="px-0 pb-3 bg-transparent data-[state=active]:bg-transparent shadow-none data-[state=active]:shadow-none rounded-none border-b-[1.5px] border-transparent data-[state=active]:border-foreground dark:data-[state=active]:border-white transition-all text-base font-medium text-muted-foreground data-[state=active]:text-foreground"
					>
						Institution Connections
					</TabsTrigger>
					<TabsTrigger
						value="active"
						className="group px-0 pb-3 bg-transparent data-[state=active]:bg-transparent shadow-none data-[state=active]:shadow-none rounded-none border-b-[1.5px] border-transparent transition-all text-base font-medium flex items-center gap-2 text-muted-foreground data-[state=active]:text-foreground relative"
					>
						<span className="relative">
							Documents
							<span className="absolute bottom-[-13.5px] left-1/2 -translate-x-1/2 w-20 h-[1.5px] bg-foreground dark:bg-white opacity-0 group-data-[state=active]:opacity-100 transition-all duration-200" />
						</span>
					{totalDocumentCount > 0 && (
						<span className="px-1.5 py-0.5 rounded-full bg-muted-foreground/15 text-[10px] font-bold">
							{totalDocumentCount}
						</span>
					)}
					</TabsTrigger>
				</TabsList>
			</div>
		</div>
	);
};
