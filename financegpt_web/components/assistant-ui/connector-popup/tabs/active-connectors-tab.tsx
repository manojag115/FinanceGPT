"use client";

import { RefreshCw, SquarePlus, Upload, FileText, Trash2, MoreHorizontal, Eye, Search, X } from "lucide-react";
import { useRouter } from "next/navigation";
import type { FC } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { motion, AnimatePresence } from "motion/react";
import { deleteDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import { documentTypeCountsAtom } from "@/atoms/documents/document-query.atoms";
import { useDocumentUploadDialog } from "@/components/assistant-ui/document-upload-popup";
import { DocumentViewer } from "@/components/document-viewer";
import { Button } from "@/components/ui/button";
import { TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { DocumentTypeEnum } from "@/contracts/types/document.types";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { getDocumentTypeIcon, DocumentTypeChip } from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentTypeIcon";
import { cn } from "@/lib/utils";

function useDebounced<T>(value: T, delay = 250) {
	const [debounced, setDebounced] = useState(value);
	useEffect(() => {
		const t = setTimeout(() => setDebounced(value), delay);
		return () => clearTimeout(t);
	}, [value, delay]);
	return debounced;
}

function truncate(text: string, len = 120): string {
	const plain = text
		.replace(/[#*_`>\-[\]()]+/g, " ")
		.replace(/\s+/g, " ")
		.trim();
	if (plain.length <= len) return plain;
	return `${plain.slice(0, len)}...`;
}

interface ActiveConnectorsTabProps {
	searchQuery: string;
	searchSpaceId: string;
}

export const ActiveConnectorsTab: FC<ActiveConnectorsTabProps> = ({
	searchQuery: _searchQuery,
	searchSpaceId,
}) => {
	const router = useRouter();
	const { openDialog: openUploadDialog } = useDocumentUploadDialog();

	const handleNewNote = useCallback(() => {
		router.push(`/dashboard/${searchSpaceId}/editor/new`);
	}, [router, searchSpaceId]);

	const [search, setSearch] = useState("");
	const debouncedSearch = useDebounced(search, 250);
	const [selectedType, setSelectedType] = useState<DocumentTypeEnum | "all">("all");
	const { data: rawTypeCounts } = useAtomValue(documentTypeCountsAtom);
	const { mutateAsync: deleteDocumentMutation } = useAtomValue(deleteDocumentMutationAtom);

	// Build query parameters
	const queryParams = useMemo(
		() => ({
			search_space_id: Number(searchSpaceId),
			page: 0,
			page_size: 100,
			...(selectedType !== "all" && { document_types: [selectedType] }),
		}),
		[searchSpaceId, selectedType]
	);

	// Build search query parameters
	const searchQueryParams = useMemo(
		() => ({
			search_space_id: Number(searchSpaceId),
			page: 0,
			page_size: 100,
			title: debouncedSearch.trim(),
			...(selectedType !== "all" && { document_types: [selectedType] }),
		}),
		[searchSpaceId, selectedType, debouncedSearch]
	);

	// Use query for fetching documents
	const {
		data: documentsResponse,
		isLoading: isDocumentsLoading,
		refetch: refetchDocuments,
		error: documentsError,
	} = useQuery({
		queryKey: cacheKeys.documents.globalQueryParams(queryParams),
		queryFn: () => documentsApiService.getDocuments({ queryParams }),
		staleTime: 3 * 60 * 1000,
		enabled: !!searchSpaceId && !debouncedSearch.trim(),
	});

	// Use query for searching documents
	const {
		data: searchResponse,
		isLoading: isSearchLoading,
		refetch: refetchSearch,
		error: searchError,
	} = useQuery({
		queryKey: cacheKeys.documents.globalQueryParams(searchQueryParams),
		queryFn: () => documentsApiService.searchDocuments({ queryParams: searchQueryParams }),
		staleTime: 3 * 60 * 1000,
		enabled: !!searchSpaceId && !!debouncedSearch.trim(),
	});

	const documents = debouncedSearch.trim()
		? searchResponse?.items || []
		: documentsResponse?.items || [];
	
	const loading = debouncedSearch.trim() ? isSearchLoading : isDocumentsLoading;
	const error = debouncedSearch.trim() ? searchError : documentsError;

	const [isRefreshing, setIsRefreshing] = useState(false);

	const refreshCurrentView = useCallback(async () => {
		if (isRefreshing) return;
		setIsRefreshing(true);
		try {
			if (debouncedSearch.trim()) {
				await refetchSearch();
			} else {
				await refetchDocuments();
			}
			toast.success("Documents refreshed");
		} finally {
			setIsRefreshing(false);
		}
	}, [debouncedSearch, refetchSearch, refetchDocuments, isRefreshing]);

	const handleDelete = useCallback(
		async (id: number) => {
			try {
				await deleteDocumentMutation({ id });
				toast.success("Document deleted");
				await refreshCurrentView();
			} catch (error) {
				console.error("Failed to delete document:", error);
				toast.error("Failed to delete document");
			}
		},
		[deleteDocumentMutation, refreshCurrentView]
	);

	// Get document type counts
	const typeCounts = rawTypeCounts || {};
	const availableTypes = Object.entries(typeCounts)
		.filter(([_, count]) => count > 0)
		.sort(([a], [b]) => a.localeCompare(b));

	return (
		<TabsContent value="active" className="m-0 flex flex-col h-full">
			{/* Search and Filter Bar */}
			<div className="flex flex-col sm:flex-row gap-2 mb-4">
				<div className="relative flex-1">
					<Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
					<Input
						placeholder="Search documents..."
						value={search}
						onChange={(e) => setSearch(e.target.value)}
						className="pl-9 h-9"
					/>
					{search && (
						<Button
							variant="ghost"
							size="sm"
							className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
							onClick={() => setSearch("")}
						>
							<X className="w-3.5 h-3.5" />
						</Button>
					)}
				</div>
				<div className="flex gap-2 overflow-x-auto pb-1">
					<Button
						variant={selectedType === "all" ? "default" : "outline"}
						size="sm"
						className="h-9 whitespace-nowrap"
						onClick={() => setSelectedType("all")}
					>
						All Types
					</Button>
					{availableTypes.map(([type, count]) => (
						<Button
							key={type}
							variant={selectedType === type ? "default" : "outline"}
							size="sm"
							className="h-9 whitespace-nowrap gap-1.5"
							onClick={() => setSelectedType(type as DocumentTypeEnum)}
						>
							{getDocumentTypeIcon(type)}
							<span className="text-xs">
								{type.replace(/_/g, " ").toLowerCase()} ({count})
							</span>
						</Button>
					))}
				</div>
			</div>

			{/* Documents Grid */}
			<div className="flex-1 overflow-auto">
			{loading ? (
				<div className="flex items-center justify-center py-20">
					<div className="flex flex-col items-center gap-3">
						<RefreshCw className="w-8 h-8 animate-spin text-primary" />
						<p className="text-sm text-muted-foreground">Loading documents...</p>
					</div>
				</div>
			) : error ? (
				<div className="flex items-center justify-center py-20">
					<div className="flex flex-col items-center gap-3">
						<FileText className="w-12 h-12 text-muted-foreground" />
						<p className="text-sm text-destructive">Failed to load documents</p>
						<Button variant="outline" size="sm" onClick={refreshCurrentView}>
							Retry
						</Button>
					</div>
				</div>
			) : documents.length === 0 ? (
				<div className="flex items-center justify-center py-20">
					<motion.div
						initial={{ opacity: 0, y: 10 }}
						animate={{ opacity: 1, y: 0 }}
						className="flex flex-col items-center gap-4 text-center"
					>
						<div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
							<FileText className="w-8 h-8 text-muted-foreground" />
						</div>
						<div className="space-y-1">
							<h4 className="font-semibold">No documents found</h4>
							<p className="text-sm text-muted-foreground">
								{search ? "Try a different search term" : "Upload your first document to get started"}
							</p>
						</div>
						{!search && (
							<Button onClick={openUploadDialog} size="sm">
								<Upload className="w-4 h-4 mr-2" />
								Upload Documents
							</Button>
						)}
					</motion.div>
				</div>
			) : (
				<div className="grid grid-cols-1 gap-3 pb-4">
					<AnimatePresence mode="popLayout">
						{documents.map((doc, index) => (
							<motion.div
								key={doc.id}
								initial={{ opacity: 0, y: 10 }}
								animate={{ opacity: 1, y: 0 }}
								exit={{ opacity: 0, scale: 0.95 }}
								transition={{ delay: index * 0.02 }}
								className={cn(
									"group relative flex items-start gap-3 p-3.5 rounded-xl transition-all",
									"border border-border bg-card/50 hover:bg-card hover:shadow-sm"
								)}
							>
								{/* Icon */}
								<div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted shrink-0">
									{getDocumentTypeIcon(doc.document_type)}
								</div>

								{/* Content */}
								<div className="flex-1 min-w-0 space-y-1.5">
									<div className="flex items-start justify-between gap-2">
										<h4 className="font-medium text-sm line-clamp-1">{doc.title}</h4>
										<DocumentTypeChip type={doc.document_type} />
									</div>
									
									{doc.content && (
										<p className="text-xs text-muted-foreground line-clamp-2">
											{truncate(doc.content)}
										</p>
									)}

									<div className="flex items-center gap-2">
										<span className="text-[11px] text-muted-foreground">
											{new Date(doc.created_at).toLocaleDateString("en-US", {
												month: "short",
												day: "numeric",
												year: "numeric",
											})}
										</span>
										<DocumentViewer
											title={doc.title}
											content={doc.content}
											trigger={
												<Button variant="ghost" size="sm" className="h-6 px-2 text-[11px] gap-1">
													<Eye className="w-3 h-3" />
													View
												</Button>
											}
										/>
									</div>
								</div>

								{/* Actions */}
								<DropdownMenu>
									<DropdownMenuTrigger asChild>
										<Button
											variant="ghost"
											size="sm"
											className="h-8 w-8 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
										>
											<MoreHorizontal className="w-4 h-4" />
										</Button>
									</DropdownMenuTrigger>
									<DropdownMenuContent align="end">
										<DocumentViewer
											title={doc.title}
											content={doc.content}
											trigger={
												<DropdownMenuItem onSelect={(e) => e.preventDefault()}>
													<Eye className="w-4 h-4 mr-2" />
													View Full
												</DropdownMenuItem>
											}
										/>
										<DropdownMenuItem
											className="text-destructive focus:text-destructive"
											onClick={() => handleDelete(doc.id)}
										>
											<Trash2 className="w-4 h-4 mr-2" />
											Delete
										</DropdownMenuItem>
									</DropdownMenuContent>
								</DropdownMenu>
							</motion.div>
						))}
					</AnimatePresence>
				</div>
			)}
			</div>

			{/* Footer Actions */}
			<div className="flex items-center justify-end gap-2 pt-4 border-t mt-4">
				<Button onClick={refreshCurrentView} variant="ghost" size="sm" className="h-9" disabled={isRefreshing}>
					<RefreshCw className={cn("w-4 h-4 mr-2", isRefreshing && "animate-spin")} />
					Refresh
				</Button>
				<Button onClick={openUploadDialog} variant="default" size="sm" className="h-9">
					<Upload className="w-4 h-4 mr-2" />
					Upload
				</Button>
			</div>
		</TabsContent>
	);
};
