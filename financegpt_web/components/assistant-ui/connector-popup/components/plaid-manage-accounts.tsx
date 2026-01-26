"use client";

import { useCallback, useEffect, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import { Button } from "@/components/ui/button";
import { authenticatedFetch } from "@/lib/auth-utils";
import { toast } from "sonner";
import { 
	X, 
	RefreshCw, 
	Plus, 
	Wallet, 
	PiggyBank, 
	Landmark,
	Building2,
	ArrowLeft 
} from "lucide-react";
import Image from "next/image";
import type { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { cn } from "@/lib/utils";

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

	// Get icon for account type
	const getAccountIcon = (type: string, subtype?: string) => {
		const typeStr = (subtype || type).toLowerCase();
		
		if (typeStr.includes("checking") || typeStr.includes("savings")) {
			return <Wallet className="h-5 w-5 text-blue-500" />;
		}
		if (typeStr.includes("401k") || typeStr.includes("ira") || typeStr.includes("retirement")) {
			return <PiggyBank className="h-5 w-5 text-emerald-500" />;
		}
		if (typeStr.includes("investment") || typeStr.includes("brokerage")) {
			return <Landmark className="h-5 w-5 text-purple-500" />;
		}
		return <Building2 className="h-5 w-5 text-gray-500" />;
	};

	// Group accounts by category
	const groupedAccounts = accounts.reduce((acc, account) => {
		const typeStr = (account.subtype || account.type).toLowerCase();
		let category = "OTHER";
		
		if (typeStr.includes("checking") || typeStr.includes("savings")) {
			category = "DEPOSITS";
		} else if (typeStr.includes("investment") || typeStr.includes("brokerage") || 
				   typeStr.includes("401k") || typeStr.includes("ira") || typeStr.includes("retirement")) {
			category = "INVESTMENTS";
		}
		
		if (!acc[category]) {
			acc[category] = [];
		}
		acc[category].push(account);
		return acc;
	}, {} as Record<string, PlaidAccount[]>);

	// Format account name
	const formatAccountName = (account: PlaidAccount) => {
		return account.name;
	};

	if (isLoading) {
		return (
			<div className="flex flex-col h-full">
				<div className="flex-shrink-0 px-4 sm:px-12 pt-5 sm:pt-10 pb-4 border-b border-border/80 dark:border-white/5">
					<div className="flex items-center gap-3 mb-4">
						<Button variant="ghost" size="icon" onClick={onClose} className="h-9 w-9">
							<ArrowLeft className="h-5 w-5" />
						</Button>
						<div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted border border-border/40">
							{getConnectorIcon(connectorType, "h-6 w-6")}
						</div>
					</div>
					<h2 className="text-xl sm:text-3xl font-semibold tracking-tight">Loading...</h2>
				</div>
				<div className="flex items-center justify-center flex-1">
					<div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary" />
				</div>
			</div>
		);
	}

	return (
		<div className="flex flex-col h-full">
			{/* Header - matching main connector dialog style */}
			<div className="flex-shrink-0 px-4 sm:px-12 pt-5 sm:pt-10 pb-4 border-b border-border/80 dark:border-white/5">
				<div className="flex items-center gap-3 mb-4 sm:mb-6">
					<Button variant="ghost" size="icon" onClick={onClose} className="h-9 w-9">
						<ArrowLeft className="h-5 w-5" />
					</Button>
					<div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted border border-border/40">
						{getConnectorIcon(connectorType, "h-6 w-6")}
					</div>
				</div>
				<div>
					<h2 className="text-xl sm:text-3xl font-semibold tracking-tight">{institutionName}</h2>
					<p className="text-xs sm:text-base text-muted-foreground/80 mt-1 sm:mt-1.5">
						{accounts.length} {accounts.length === 1 ? "account" : "accounts"} connected
					</p>
				</div>
			</div>

			{/* Scrollable Account List */}
			<div className="flex-1 overflow-y-auto px-4 sm:px-12 py-4 sm:py-8 pb-12 sm:pb-16 space-y-4">
					{Object.entries(groupedAccounts).map(([category, categoryAccounts]) => (
						<div key={category} className="space-y-2">
							{/* Category Header */}
							<div className="flex items-center gap-2 px-1">
								<h3 className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">
									{category}
								</h3>
								<div className="h-px flex-1 bg-border/50" />
							</div>

							{/* Accounts in Category */}
							<div className="space-y-1.5">
								{categoryAccounts.map((account) => (
									<div
										key={account.account_id}
										className={cn(
											"group relative flex items-center justify-between p-3 rounded-xl",
											"border border-border/40 bg-card/50 backdrop-blur-sm",
											"hover:bg-card hover:border-border/60 hover:shadow-sm",
											"transition-all duration-200 ease-in-out"
										)}
									>
										<div className="flex items-center gap-3 flex-1 min-w-0">
											{/* Icon */}
											<div className="flex-shrink-0">
												{getAccountIcon(account.type, account.subtype)}
											</div>

											{/* Account Info */}
											<div className="flex-1 min-w-0">
												<p className="text-sm font-medium truncate">
													{formatAccountName(account)}
												</p>
												{account.mask && (
													<p className="text-xs text-muted-foreground font-mono">
														•••• {account.mask}
													</p>
												)}
											</div>
										</div>

										{/* Balance & Status */}
										<div className="flex items-center gap-2 flex-shrink-0">
											{account.balances?.current !== undefined && (
												<span className="text-sm font-semibold tabular-nums">
													{formatCurrency(account.balances.current)}
												</span>
											)}
											{/* Active Status Indicator */}
											<div className="relative">
												<div className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]" />
												<div className="absolute inset-0 h-2 w-2 rounded-full bg-emerald-400 animate-ping opacity-75" />
											</div>
										</div>
									</div>
								))}
							</div>
						</div>
					))}

					{/* Last Synced Info */}
					{lastSynced && (
						<div className="flex items-center justify-center gap-2 pt-2">
							<div className="h-px flex-1 bg-border/30" />
							<p className="text-xs text-muted-foreground">
								Last synced {new Date(lastSynced).toLocaleDateString()} at{" "}
								{new Date(lastSynced).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
							</p>
							<div className="h-px flex-1 bg-border/30" />
						</div>
					)}
				</div>

			{/* Footer */}
			<div className="px-4 sm:px-12 py-4 border-t border-border/80 dark:border-white/5 bg-muted/50 backdrop-blur-md space-y-2">
				{/* Primary Action */}
				<Button
					onClick={handleSync}
					disabled={isSyncing}
					className="w-full font-medium shadow-sm"
					size="default"
				>
					<RefreshCw className={cn("h-4 w-4 mr-2", isSyncing && "animate-spin")} />
					{isSyncing ? "Syncing..." : "Sync Now"}
				</Button>

				{/* Secondary Actions */}
				<div className="grid grid-cols-2 gap-2">
					<Button
						variant="outline"
						onClick={createUpdateLinkToken}
						disabled={!!linkToken}
						className="text-xs"
						size="sm"
					>
						<Plus className="h-3.5 w-3.5 mr-1.5" />
						Add Account
					</Button>
					<Button
						variant="outline"
						onClick={onDisconnect}
						className="text-xs text-destructive hover:bg-destructive/10 hover:text-destructive"
						size="sm"
					>
						Disconnect
					</Button>
				</div>
			</div>
		</div>
	);
}
