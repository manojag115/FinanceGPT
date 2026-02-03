"use client";

import {
	AlertCircle,
	CheckCircle2,
	ChevronDown,
	ChevronUp,
	FileText,
	Loader2,
	X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import {
	type ConnectorIndexingMetadata,
	type DocumentProcessingMetadata,
	isConnectorIndexingMetadata,
	isDocumentProcessingMetadata,
} from "@/contracts/types/inbox.types";
import type { InboxItem } from "@/hooks/use-inbox";
import { cn } from "@/lib/utils";

interface UploadStatusPanelProps {
	inboxItems: InboxItem[];
	markAsRead: (id: number) => Promise<boolean>;
}

/**
 * Get display name for connector type
 */
function getConnectorTypeDisplayName(connectorType: string): string {
	const displayNames: Record<string, string> = {
		GITHUB_CONNECTOR: "GitHub",
		GOOGLE_CALENDAR_CONNECTOR: "Google Calendar",
		GOOGLE_GMAIL_CONNECTOR: "Gmail",
		GOOGLE_DRIVE_CONNECTOR: "Google Drive",
		LINEAR_CONNECTOR: "Linear",
		NOTION_CONNECTOR: "Notion",
		SLACK_CONNECTOR: "Slack",
		TEAMS_CONNECTOR: "Microsoft Teams",
		DISCORD_CONNECTOR: "Discord",
		JIRA_CONNECTOR: "Jira",
		CONFLUENCE_CONNECTOR: "Confluence",
		BOOKSTACK_CONNECTOR: "BookStack",
		CLICKUP_CONNECTOR: "ClickUp",
		AIRTABLE_CONNECTOR: "Airtable",
		LUMA_CONNECTOR: "Luma",
		ELASTICSEARCH_CONNECTOR: "Elasticsearch",
		WEBCRAWLER_CONNECTOR: "Web Crawler",
		YOUTUBE_CONNECTOR: "YouTube",
		CIRCLEBACK_CONNECTOR: "Circleback",
		MCP_CONNECTOR: "MCP",
		TAVILY_API: "Tavily",
		SEARXNG_API: "SearXNG",
		LINKUP_API: "Linkup",
		BAIDU_SEARCH_API: "Baidu",
	};

	return (
		displayNames[connectorType] ||
		connectorType
			.replace(/_/g, " ")
			.replace(/CONNECTOR|API/gi, "")
			.trim()
	);
}

/**
 * Google Drive-style floating upload status panel
 * Shows in-progress uploads and recent completions
 */
export function UploadStatusPanel({ inboxItems, markAsRead }: UploadStatusPanelProps) {
	const t = useTranslations("sidebar");
	const [isExpanded, setIsExpanded] = useState(true);
	const [mounted, setMounted] = useState(false);
	const [dismissedIds, setDismissedIds] = useState<Set<number>>(new Set());

	useEffect(() => {
		setMounted(true);
	}, []);

	// Filter to only status items (uploads, connector indexing, document processing)
	// Only show items from the last 30 minutes that are in progress or recently completed
	const statusItems = useMemo(() => {
		const thirtyMinutesAgo = new Date(Date.now() - 30 * 60 * 1000);

		return inboxItems
			.filter((item) => {
				// Only status items
				if (item.type !== "connector_indexing" && item.type !== "document_processing") {
					return false;
				}

				// Don't show dismissed items
				if (dismissedIds.has(item.id)) {
					return false;
				}

				// Get status from metadata
				const metadata = item.metadata as Record<string, unknown>;
				const status = typeof metadata?.status === "string" ? metadata.status : undefined;

				// Always show in-progress items
				if (status === "in_progress") {
					return true;
				}

				// Show completed/failed items only if recent (within 30 mins)
				const createdAt = new Date(item.created_at);
				if (createdAt >= thirtyMinutesAgo) {
					return true;
				}

				return false;
			})
			.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
			.slice(0, 5); // Max 5 items to show
	}, [inboxItems, dismissedIds]);

	// Count in-progress items
	const inProgressCount = useMemo(() => {
		return statusItems.filter((item) => {
			const metadata = item.metadata as Record<string, unknown>;
			return metadata?.status === "in_progress";
		}).length;
	}, [statusItems]);

	// Auto-collapse when no items
	useEffect(() => {
		if (statusItems.length === 0) {
			setIsExpanded(false);
		} else if (inProgressCount > 0) {
			// Auto-expand when new in-progress item appears
			setIsExpanded(true);
		}
	}, [statusItems.length, inProgressCount]);

	const handleDismiss = useCallback(
		async (item: InboxItem, e: React.MouseEvent) => {
			e.stopPropagation();
			setDismissedIds((prev) => new Set([...prev, item.id]));
			if (!item.read) {
				await markAsRead(item.id);
			}
		},
		[markAsRead]
	);

	const handleDismissAll = useCallback(async () => {
		const ids = statusItems.map((item) => item.id);
		setDismissedIds((prev) => new Set([...prev, ...ids]));

		// Mark all as read
		for (const item of statusItems) {
			if (!item.read) {
				await markAsRead(item.id);
			}
		}
	}, [statusItems, markAsRead]);

	const getStatusIcon = (item: InboxItem) => {
		const metadata = item.metadata as Record<string, unknown>;
		const status = typeof metadata?.status === "string" ? metadata.status : undefined;

		switch (status) {
			case "in_progress":
				return <Loader2 className="h-4 w-4 text-primary animate-spin" />;
			case "completed":
				return <CheckCircle2 className="h-4 w-4 text-green-500" />;
			case "failed":
				return <AlertCircle className="h-4 w-4 text-red-500" />;
			default:
				return <FileText className="h-4 w-4 text-muted-foreground" />;
		}
	};

	const getItemIcon = (item: InboxItem) => {
		if (item.type === "connector_indexing" && isConnectorIndexingMetadata(item.metadata)) {
			return getConnectorIcon(item.metadata.connector_type, "h-4 w-4");
		}
		return <FileText className="h-4 w-4 text-muted-foreground" />;
	};

	const getProgressValue = (item: InboxItem): number | null => {
		if (item.type === "connector_indexing" && isConnectorIndexingMetadata(item.metadata)) {
			const meta = item.metadata as ConnectorIndexingMetadata;
			if (meta.progress_percent !== undefined) {
				return meta.progress_percent;
			}
			if (meta.total_count && meta.indexed_count) {
				return Math.round((meta.indexed_count / meta.total_count) * 100);
			}
		}
		return null;
	};

	const getItemSubtitle = (item: InboxItem): string => {
		if (item.type === "connector_indexing" && isConnectorIndexingMetadata(item.metadata)) {
			const meta = item.metadata as ConnectorIndexingMetadata;
			return getConnectorTypeDisplayName(meta.connector_type);
		}
		if (item.type === "document_processing" && isDocumentProcessingMetadata(item.metadata)) {
			const meta = item.metadata as DocumentProcessingMetadata;
			return meta.processing_stage.replace(/_/g, " ");
		}
		return item.type.replace(/_/g, " ");
	};

	// Don't render if no items and not mounted
	if (!mounted || statusItems.length === 0) {
		return null;
	}

	return createPortal(
		<AnimatePresence>
			<motion.div
				initial={{ opacity: 0, y: 20, scale: 0.95 }}
				animate={{ opacity: 1, y: 0, scale: 1 }}
				exit={{ opacity: 0, y: 20, scale: 0.95 }}
				transition={{ type: "spring", damping: 25, stiffness: 300 }}
				className={cn(
					"fixed bottom-4 right-4 z-50",
					"w-80 max-w-[calc(100vw-2rem)]",
					"bg-background border rounded-lg shadow-lg",
					"flex flex-col overflow-hidden"
				)}
			>
				{/* Header - Always visible */}
				<button
					type="button"
					onClick={() => setIsExpanded(!isExpanded)}
					className={cn(
						"flex items-center justify-between w-full px-4 py-3",
						"hover:bg-accent/50 transition-colors",
						"border-b",
						!isExpanded && "border-b-0"
					)}
				>
					<div className="flex items-center gap-2">
						{inProgressCount > 0 ? (
							<Loader2 className="h-4 w-4 text-primary animate-spin" />
						) : (
							<CheckCircle2 className="h-4 w-4 text-green-500" />
						)}
						<span className="text-sm font-medium">
							{inProgressCount > 0 ? (
								<>
									{t("uploading") || "Uploading"} {inProgressCount}{" "}
									{inProgressCount === 1
										? t("item") || "item"
										: t("items") || "items"}
								</>
							) : (
								<>
									{statusItems.length}{" "}
									{statusItems.length === 1
										? t("upload_complete") || "upload complete"
										: t("uploads_complete") || "uploads complete"}
								</>
							)}
						</span>
					</div>
					<div className="flex items-center gap-1">
						{statusItems.length > 0 && inProgressCount === 0 && (
							<Tooltip>
								<TooltipTrigger asChild>
									<Button
										variant="ghost"
										size="icon"
										className="h-6 w-6"
										onClick={(e) => {
											e.stopPropagation();
											handleDismissAll();
										}}
									>
										<X className="h-3.5 w-3.5" />
									</Button>
								</TooltipTrigger>
								<TooltipContent>{t("dismiss_all") || "Dismiss all"}</TooltipContent>
							</Tooltip>
						)}
						{isExpanded ? (
							<ChevronDown className="h-4 w-4 text-muted-foreground" />
						) : (
							<ChevronUp className="h-4 w-4 text-muted-foreground" />
						)}
					</div>
				</button>

				{/* Content - Collapsible */}
				<AnimatePresence>
					{isExpanded && (
						<motion.div
							initial={{ height: 0, opacity: 0 }}
							animate={{ height: "auto", opacity: 1 }}
							exit={{ height: 0, opacity: 0 }}
							transition={{ duration: 0.2 }}
							className="overflow-hidden"
						>
							<div className="max-h-64 overflow-y-auto">
								{statusItems.map((item) => {
									const metadata = item.metadata as Record<string, unknown>;
									const status =
										typeof metadata?.status === "string" ? metadata.status : undefined;
									const progress = getProgressValue(item);
									const isInProgress = status === "in_progress";

									return (
										<div
											key={item.id}
											className={cn(
												"flex items-center gap-3 px-4 py-2.5",
												"hover:bg-accent/30 transition-colors",
												"group"
											)}
										>
											{/* Icon */}
											<div className="shrink-0">{getItemIcon(item)}</div>

											{/* Content */}
											<div className="flex-1 min-w-0">
												<div className="flex items-center gap-2">
													<p className="text-xs font-medium truncate flex-1">{item.title}</p>
													{getStatusIcon(item)}
												</div>
												<p className="text-[10px] text-muted-foreground truncate">
													{getItemSubtitle(item)}
												</p>
												{/* Progress bar for in-progress items */}
												{isInProgress && progress !== null && (
													<Progress value={progress} className="h-1 mt-1.5" />
												)}
											</div>

											{/* Dismiss button - only for completed/failed */}
											{!isInProgress && (
												<Tooltip>
													<TooltipTrigger asChild>
														<Button
															variant="ghost"
															size="icon"
															className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
															onClick={(e) => handleDismiss(item, e)}
														>
															<X className="h-3 w-3" />
														</Button>
													</TooltipTrigger>
													<TooltipContent>{t("dismiss") || "Dismiss"}</TooltipContent>
												</Tooltip>
											)}
										</div>
									);
								})}
							</div>
						</motion.div>
					)}
				</AnimatePresence>
			</motion.div>
		</AnimatePresence>,
		document.body
	);
}
