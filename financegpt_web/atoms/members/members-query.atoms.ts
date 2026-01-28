import { atomWithQuery } from "jotai-tanstack-query";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { membersApiService } from "@/lib/apis/members-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export const membersAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		queryKey: cacheKeys.members.all(searchSpaceId?.toString() ?? ""),
		enabled: false, // Disabled for single-user FinanceGPT
		staleTime: 3 * 1000, // 3 seconds - short staleness for live collaboration
		queryFn: async () => {
			// Return empty array for single-user app
			return [];
		},
	};
});

export const myAccessAtom = atomWithQuery((get) => {
	const searchSpaceId = get(activeSearchSpaceIdAtom);

	return {
		queryKey: cacheKeys.members.myAccess(searchSpaceId?.toString() ?? ""),
		enabled: false, // Disabled for single-user FinanceGPT
		staleTime: 5 * 60 * 1000, // 5 minutes
		queryFn: async () => {
			// Return null for single-user app
			return null;
		},
	};
});
