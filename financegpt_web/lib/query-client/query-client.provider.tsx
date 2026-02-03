"use client";
import { QueryClientAtomProvider } from "jotai-tanstack-query/react";
import { queryClient } from "./client";

export function ReactQueryClientProvider({ children }: { children: React.ReactNode }) {
	return (
		<QueryClientAtomProvider client={queryClient}>
			{children}
		</QueryClientAtomProvider>
	);
}
