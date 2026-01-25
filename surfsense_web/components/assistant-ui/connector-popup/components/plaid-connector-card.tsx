"use client";

import { useCallback } from "react";
import type { PlaidLinkOnSuccessMetadata } from "react-plaid-link";
import type { EnumConnectorName } from "@/contracts/enums/connector";
import { usePlaidLinkHook } from "../hooks/use-plaid-link";
import { ConnectorCard } from "./connector-card";

interface PlaidConnectorCardProps {
	id: string;
	title: string;
	description: string;
	connectorType: EnumConnectorName;
	searchSpaceId: number;
	isConnected: boolean;
	isConnecting: boolean;
	onSuccess: (publicToken: string, connectorType: EnumConnectorName, metadata: PlaidLinkOnSuccessMetadata) => void;
	onSetConnecting: (id: string | null) => void;
}

/**
 * Connector card component specifically for Plaid-powered bank connectors
 * Handles Plaid Link initialization and OAuth flow
 */
export function PlaidConnectorCard({
	id,
	title,
	description,
	connectorType,
	searchSpaceId,
	isConnected,
	isConnecting,
	onSuccess,
	onSetConnecting,
}: PlaidConnectorCardProps) {
	const handlePlaidSuccess = useCallback(
		(publicToken: string, metadata: PlaidLinkOnSuccessMetadata) => {
			onSuccess(publicToken, connectorType, metadata);
		},
		[connectorType, onSuccess]
	);

	const handlePlaidExit = useCallback(() => {
		onSetConnecting(null);
	}, [onSetConnecting]);

	const { createLinkToken, isLoading } = usePlaidLinkHook({
		searchSpaceId,
		connectorType,
		onSuccess: handlePlaidSuccess,
		onExit: handlePlaidExit,
	});

	const handleConnect = useCallback(() => {
		onSetConnecting(id);
		createLinkToken();
	}, [id, createLinkToken, onSetConnecting]);

	return (
		<ConnectorCard
			id={id}
			title={title}
			description={description}
			connectorType={connectorType}
			isConnected={isConnected}
			isConnecting={isConnecting || isLoading}
			onConnect={handleConnect}
		/>
	);
}
