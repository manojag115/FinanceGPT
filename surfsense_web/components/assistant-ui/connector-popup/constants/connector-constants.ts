import { EnumConnectorName } from "@/contracts/enums/connector";

// Type for connector configuration
type ConnectorConfig = {
	id: string;
	title: string;
	description: string;
	connectorType: EnumConnectorName;
	authEndpoint?: string;
	selfHostedOnly?: boolean;
};

// Financial Connectors - Plaid-powered bank integrations
export const OAUTH_CONNECTORS: readonly ConnectorConfig[] = [
	{
		id: "chase-bank-connector",
		title: "Chase Bank",
		description: "Connect your Chase accounts",
		connectorType: EnumConnectorName.CHASE_BANK,
		authEndpoint: "/api/v1/plaid/link-token",
	},
	{
		id: "fidelity-connector",
		title: "Fidelity Investments",
		description: "Connect your Fidelity accounts",
		connectorType: EnumConnectorName.FIDELITY_INVESTMENTS,
		authEndpoint: "/api/v1/plaid/link-token",
	},
	{
		id: "bank-of-america-connector",
		title: "Bank of America",
		description: "Connect your BoA accounts",
		connectorType: EnumConnectorName.BANK_OF_AMERICA,
		authEndpoint: "/api/v1/plaid/link-token",
	},
];

// All other connector types removed for FinanceGPT focus
export const CRAWLERS: readonly ConnectorConfig[] = [];
export const OTHER_CONNECTORS: readonly ConnectorConfig[] = [];
export const COMPOSIO_CONNECTORS: readonly ConnectorConfig[] = [];
export const COMPOSIO_TOOLKITS: readonly ConnectorConfig[] = [];

// Re-export IndexingConfigState from schemas for backward compatibility
export type { IndexingConfigState } from "./connector-popup.schemas";
