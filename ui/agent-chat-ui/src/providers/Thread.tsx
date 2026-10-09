import { getApiKey } from "@/lib/api-key";
import { resolveApiUrl } from "@/lib/resolve-api-url";
import { Thread } from "@langchain/langgraph-sdk";
import { useQueryState } from "nuqs";
import {
  createContext,
  useContext,
  ReactNode,
  useCallback,
  useState,
} from "react";

export type ChatThread = Thread & { title: string; snippet?: string };
type Page = { threads: ChatThread[]; cursor: string | null };
const ThreadContext = createContext<
  | {
      getThreads: () => Promise<ChatThread[]>;
      threads: ChatThread[];
      setThreads: React.Dispatch<React.SetStateAction<ChatThread[]>>;
      threadsLoading: boolean;
      setThreadsLoading: React.Dispatch<React.SetStateAction<boolean>>;
      request: (path: string, init?: RequestInit) => Promise<any>;
      getPage: (
        query?: string,
        cursor?: string | null,
        signal?: AbortSignal,
      ) => Promise<Page>;
      revision: number;
      refresh: () => void;
    }
  | undefined
>(undefined);

export function ThreadProvider({ children }: { children: ReactNode }) {
  const envApiUrl = process.env.NEXT_PUBLIC_API_URL;
  const [apiUrl] = useQueryState("apiUrl", { defaultValue: envApiUrl || "" });
  const [authScheme] = useQueryState("authScheme", {
    defaultValue: process.env.NEXT_PUBLIC_AUTH_SCHEME || "",
  });
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [threadsLoading, setThreadsLoading] = useState(false);
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((r) => r + 1), []);
  const request = useCallback(
    async (path: string, init?: RequestInit) => {
      const url = resolveApiUrl(apiUrl, envApiUrl);
      const headers = new Headers(init?.headers);
      const key = getApiKey(url);
      if (key) headers.set("X-Api-Key", key);
      if (authScheme) headers.set("X-Auth-Scheme", authScheme);
      if (init?.body) headers.set("Content-Type", "application/json");
      const response = await fetch(`${url}${path}`, { ...init, headers });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Chat operation failed");
      return data;
    },
    [apiUrl, envApiUrl, authScheme],
  );
  const getPage = useCallback(
    (
      query = "",
      cursor?: string | null,
      signal?: AbortSignal,
    ): Promise<Page> => {
      const params = new URLSearchParams({ q: query });
      if (cursor) params.set("cursor", cursor);
      return request(`/chat/history?${params}`, { signal });
    },
    [request],
  );
  const getThreads = useCallback(
    async () => (await getPage()).threads,
    [getPage],
  );
  return (
    <ThreadContext.Provider
      value={{
        getThreads,
        threads,
        setThreads,
        threadsLoading,
        setThreadsLoading,
        request,
        getPage,
        revision,
        refresh,
      }}
    >
      {children}
    </ThreadContext.Provider>
  );
}

export function useThreads() {
  const context = useContext(ThreadContext);
  if (!context)
    throw new Error("useThreads must be used within a ThreadProvider");
  return context;
}
