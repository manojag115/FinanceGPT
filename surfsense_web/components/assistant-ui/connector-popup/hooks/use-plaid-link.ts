"use client";

import { useCallback, useEffect, useState } from "react";
import {
	type PlaidLinkOnSuccessMetadata,
	type PlaidLinkOptions,
	usePlaidLink,
} from "react-plaid-link";
import { toast } from "sonner";
import type { EnumConnectorName } from "@/contracts/enums/connector";
import { authenticatedFetch, getBearerToken } from "@/lib/auth-utils";

interface UsePlaidLinkHookProps {
	searchSpaceId: number;
	connectorType: EnumConnectorName;
	onSuccess: (publicToken: string, metadata: PlaidLinkOnSuccessMetadata) => void;
	onExit?: () => void;
}

/**
 * Custom hook for Plaid Link integration
 * Handles link token creation and Plaid Link initialization
 */
export function usePlaidLinkHook({
	searchSpaceId,
	connectorType,
	onSuccess,
	onExit,
}: UsePlaidLinkHookProps) {
	const [linkToken, setLinkToken] = useState<string | null>(null);
	const [isLoading, setIsLoading] = useState(false);

	// Create link token from backend
	const createLinkToken = useCallback(async () => {
		setIsLoading(true);
		try {
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/plaid/link-token`,
				{
					method: "POST",
					headers: {
						"Content-Type": "application/json",
					},
					credentials: "include",
					body: JSON.stringify({
						connector_type: connectorType,
						search_space_id: searchSpaceId,
					}),
				}
			);
			
			console.log("Plaid link token response status:", response.status);

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				console.error("Failed to create link token:", errorData);
				throw new Error(errorData.detail || "Failed to create link token");
			}

			const data = await response.json();
			setLinkToken(data.link_token);
		} catch (error) {
			console.error("Error creating link token:", error);
			toast.error("Failed to initialize bank connection");
		} finally {
			setIsLoading(false);
		}
	}, [searchSpaceId, connectorType]);

	// Plaid Link configuration
	const config: PlaidLinkOptions = {
		token: linkToken,
		onSuccess: (public_token: string, metadata: PlaidLinkOnSuccessMetadata) => {
			onSuccess(public_token, metadata);
			// Re-enable body pointer events after Plaid closes
			document.body.style.removeProperty("pointer-events");
		},
		onExit: (err, metadata) => {
			if (err != null) {
				console.error("Plaid Link error:", err);
				toast.error("Bank connection cancelled or failed");
			}
			// Re-enable body pointer events after Plaid closes
			document.body.style.removeProperty("pointer-events");
			onExit?.();
		},
	};

	// Initialize Plaid Link
	const { open, ready } = usePlaidLink(config);

	// Auto-open when ready and fix body pointer-events
	useEffect(() => {
		if (!ready || !linkToken) return;

		// Fix body pointer-events that blocks Plaid iframe clicks
		// Some modal libraries set pointer-events: none on body
		const originalPointerEvents = document.body.style.pointerEvents;
		document.body.style.pointerEvents = "auto";

		// Open Plaid Link
		open();

		// Restore original pointer-events when component unmounts
		return () => {
			document.body.style.pointerEvents = originalPointerEvents;
		};
	}, [ready, linkToken, open]);

	return {
		createLinkToken,
		isLoading,
		ready,
		open,
	};
}
