import type { MetadataRoute } from "next";

// Returns a date rounded to the current hour (updates only once per hour)
function getHourlyDate(): Date {
	const now = new Date();
	now.setMinutes(0, 0, 0);
	return now;
}

export default function sitemap(): MetadataRoute.Sitemap {
	const lastModified = getHourlyDate();

	return [
		{
			url: "https://www.financegpt.com/",
			lastModified,
			changeFrequency: "daily",
			priority: 1,
		},
		{
			url: "https://www.financegpt.com/contact",
			lastModified,
			changeFrequency: "daily",
			priority: 0.9,
		},
		{
			url: "https://www.financegpt.com/pricing",
			lastModified,
			changeFrequency: "daily",
			priority: 0.9,
		},
		{
			url: "https://www.financegpt.com/privacy",
			lastModified,
			changeFrequency: "daily",
			priority: 0.9,
		},
		{
			url: "https://www.financegpt.com/terms",
			lastModified,
			changeFrequency: "daily",
			priority: 0.9,
		},
		// Documentation pages
		{
			url: "https://www.financegpt.com/docs",
			lastModified,
			changeFrequency: "daily",
			priority: 1,
		},
		{
			url: "https://www.financegpt.com/docs/installation",
			lastModified,
			changeFrequency: "daily",
			priority: 0.9,
		},
		{
			url: "https://www.financegpt.com/docs/docker-installation",
			lastModified,
			changeFrequency: "daily",
			priority: 0.9,
		},
		{
			url: "https://www.financegpt.com/docs/manual-installation",
			lastModified,
			changeFrequency: "daily",
			priority: 0.9,
		},
		// Connector documentation
		{
			url: "https://www.financegpt.com/docs/connectors/airtable",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/bookstack",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/circleback",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/clickup",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/confluence",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/discord",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/elasticsearch",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/github",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/gmail",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/google-calendar",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/google-drive",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/jira",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/linear",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/luma",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/microsoft-teams",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/notion",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/slack",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
		{
			url: "https://www.financegpt.com/docs/connectors/web-crawler",
			lastModified,
			changeFrequency: "daily",
			priority: 0.8,
		},
	];
}
