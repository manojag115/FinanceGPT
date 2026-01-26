"use client";

import { useCallback, useEffect, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { authenticatedFetch } from "@/lib/auth-utils";
import { toast } from "sonner";
import { Building2, CreditCard, DollarSign, RefreshCw, ArrowLeft } from "lucide-react";
import type { EnumConnectorName } from "@/contracts/enums/connector";

interface PlaidAccount {
	account_id: string;
	name: string;
	mask?: string;
	type: string;
	subtype?: string;
	balances?: {
		current: number;
		available?: number;
		limit?: number;
	};
}

interface PlaidManageAccountsProps {
	connectorId: number;
	connectorName: string;
	connectorType: EnumConnectorName;
	onClose: () => void;
	onDisconnect: () => void;
}

export function PlaidManageAccounts({
	connectorId,
	connectorName,
	connectorType,
	onClose,
	onDisconnect,
}: PlaidManageAccountsProps) {
	const [accounts, setAccounts] = useState<PlaidAccount[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [isSyncing, setIsSyncing] = useState(false);
	const [linkToken, setLinkToken] = useState<string | null>(null);
	const [lastSynced, setLastSynced] = useState<string | null>(null);

	// Extract institution name from connector name (remove account names in parentheses)
	const institutionName = connectorName.replace(/\s*\([^)]*\)\s*$/, "").trim();

	// Fetch accounts
	const fetchAccounts = useCallback(async () => {
		try {
			setIsLoading(true);
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/plaid/connectors/${connectorId}/accounts`,
				{
					credentials: "include",
				}
			);

			if (!response.ok) {
				throw new Error("Failed to fetch accounts");
			}

			const data = await response.json();
			setAccounts(data.accounts || []);
			setLastSynced(data.last_indexed_at);
		} catch (error) {
			console.error("Error fetching accounts:", error);
			toast.error("Failed to load accounts");
		} finally {
			setIsLoading(false);
		}
	}, [connectorId]);

	// Load accounts on mount
	useEffect(() => {
		fetchAccounts();
	}, [fetchAccounts]);

	// Create update link token
	const createUpdateLinkToken = useCallback(async () => {
		try {
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/plaid/link-token-update?connector_id=${connectorId}`,
				{
					method: "POST",
					credentials: "include",
				}
			);

			if (!response.ok) {
				throw new Error("Failed to create update link token");
			}

			const data = await response.json();
			setLinkToken(data.link_token);
		} catch (error) {
			console.error("Error creating update link token:", error);
			toast.error("Failed to initialize account update");
		}
	}, [connectorId]);

	// Handle Plaid Link success (account update)
	const onPlaidSuccess = useCallback(async () => {
		try {
			// Refresh accounts after update
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/plaid/connectors/${connectorId}/accounts/refresh`,
				{
					method: "POST",
					credentials: "include",
				}
			);

			if (!response.ok) {
				throw new Error("Failed to refresh accounts");
			}

			toast.success("Accounts updated successfully");
			await fetchAccounts();
		} catch (error) {
			console.error("Error refreshing accounts:", error);
			toast.error("Failed to update accounts");
		}
	}, [connectorId, fetchAccounts]);

	// Plaid Link hook for update mode
	const { open: openPlaidLink, ready: plaidReady } = usePlaidLink({
		token: linkToken,
		onSuccess: onPlaidSuccess,
		onExit: () => {
			setLinkToken(null);
		},
	});

	// Open Plaid Link when token is ready
	useEffect(() => {
		if (linkToken && plaidReady) {
			openPlaidLink();
		}
	}, [linkToken, plaidReady, openPlaidLink]);

	// Sync transactions
	const handleSync = useCallback(async () => {
		try {
			setIsSyncing(true);
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/plaid/connectors/${connectorId}/sync`,
				{
					method: "POST",
					credentials: "include",
				}
			);

			if (!response.ok) {
				throw new Error("Failed to sync");
			}

			toast.success("Syncing transactions in background");
		} catch (error) {
			console.error("Error syncing:", error);
			toast.error("Failed to sync transactions");
		} finally {
			setIsSyncing(false);
		}
	}, [connectorId]);

	// Format currency
	const formatCurrency = (amount: number | undefined) => {
		if (amount === undefined) return "N/A";
		return new Intl.NumberFormat("en-US", {
			style: "currency",
			currency: "USD",
		}).format(amount);
	};

	// Format account type
	const formatAccountType = (type: string, subtype?: string) => {
		if (subtype) {
			return `${subtype.replace(/_/g, " ")}`;
		}
		return type.replace(/_/g, " ");
	};

	// Get icon for account type
	const getAccountIcon = (type: string) => {
		if (type.toLowerCase().includes("credit")) {
			return <CreditCard className="h-5 w-5 text-blue-500" />;
		}
		if (type.toLowerCase().includes("investment") || type.toLowerCase().includes("brokerage")) {
			return <DollarSign className="h-5 w-5 text-green-500" />;
		}
		return <Building2 className="h-5 w-5 text-gray-500" />;
	};

	if (isLoading) {
		return (
			<div className="flex flex-col h-full">
				<div className="flex items-center gap-3 px-6 py-4 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
					<Button variant="ghost" size="icon" onClick={onClose}>
						<ArrowLeft className="h-5 w-5" />
					</Button>
					<h2 className="text-lg font-semibold">Loading...</h2>
				</div>
				<div className="flex items-center justify-center flex-1">
					<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
				</div>
			</div>
		);
	}

	return (
		<div className="flex flex-col h-full">
			{/* Header with Back Button */}
			<div className="flex items-center gap-3 px-6 py-4 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
				<Button variant="ghost" size="icon" onClick={onClose}>
					<ArrowLeft className="h-5 w-5" />
				</Button>
				<div className="flex-1">
					<h2 className="text-lg font-semibold">{institutionName}</h2>
					<p className="text-xs text-muted-foreground">
						{accounts.length} {accounts.length === 1 ? "account" : "accounts"} connected
					</p>
				</div>
			</div>

			{/* Scrollable Content */}
			<div className="flex-1 overflow-y-auto px-6 py-4">
				{/* Accounts List */}
				<div className="space-y-3 mb-6">
					{accounts.map((account) => (
						<Card key={account.account_id} className="p-4 hover:shadow-md transition-shadow">
							<div className="flex items-start gap-3">
								<div className="mt-0.5">{getAccountIcon(account.type)}</div>
								<div className="flex-1 min-w-0">
									<div className="flex items-baseline gap-2 mb-1">
										<h4 className="font-medium text-base truncate">{account.name}</h4>
										{account.mask && (
											<span className="text-xs text-muted-foreground shrink-0">
												••{account.mask}
											</span>
										)}
									</div>
									<p className="text-xs text-muted-foreground mb-3 capitalize">
										{formatAccountType(account.type, account.subtype)}
									</p>
									{account.balances && (
										<div className="grid grid-cols-2 gap-2">
											<div className="bg-muted/50 rounded-lg px-3 py-2">
												<p className="text-xs text-muted-foreground mb-0.5">Current Balance</p>
												<p className="font-semibold text-sm">
													{formatCurrency(account.balances.current)}
												</p>
											</div>
											{account.balances.available !== undefined && (
												<div className="bg-muted/50 rounded-lg px-3 py-2">
													<p className="text-xs text-muted-foreground mb-0.5">Available</p>
													<p className="font-semibold text-sm">
														{formatCurrency(account.balances.available)}
													</p>
												</div>
											)}
										</div>
									)}
								</div>
							</div>
						</Card>
					))}
				</div>

				{lastSynced && (
					<div className="flex items-center justify-center gap-2 mb-4">
						<div className="h-px flex-1 bg-border" />
						<p className="text-xs text-muted-foreground">
							Last synced: {new Date(lastSynced).toLocaleDateString()} at{" "}
							{new Date(lastSynced).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
						</p>
						<div className="h-px flex-1 bg-border" />
					</div>
				)}
			</div>

			{/* Footer Actions */}
			<div className="px-6 py-4 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 space-y-2">
				<div className="grid grid-cols-2 gap-2">
					<Button
						variant="outline"
						onClick={createUpdateLinkToken}
						disabled={!!linkToken}
						className="w-full"
					>
						Add/Update
					</Button>
					<Button
						variant="outline"
						onClick={handleSync}
						disabled={isSyncing}
						className="w-full"
					>
						<RefreshCw className={`h-4 w-4 mr-2 ${isSyncing ? "animate-spin" : ""}`} />
						{isSyncing ? "Syncing..." : "Sync"}
					</Button>
				</div>

				<Button
					className="w-full"
					variant="destructive"
					onClick={onDisconnect}
					size="sm"
				>
					Disconnect
				</Button>
			</div>
		</div>
	);
}
