import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useThreads } from "@/providers/Thread";
import { useEffect, useRef, useState } from "react";
import { useQueryState, parseAsBoolean } from "nuqs";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { PanelRightOpen } from "lucide-react";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { ChatActions } from "../chat-actions";

export default function ThreadHistory() {
  const large = useMediaQuery("(min-width: 1024px)");
  const [open, setOpen] = useQueryState(
    "chatHistoryOpen",
    parseAsBoolean.withDefault(false),
  );
  const [selected, setSelected] = useQueryState("threadId");
  const { getPage, threads, setThreads, revision, refresh } = useThreads();
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const generation = useRef(0);
  useEffect(() => {
    const controller = new AbortController();
    const version = ++generation.current;
    const timer = setTimeout(() => {
      setLoading(true);
      setError("");
      setCursor(null);
      getPage(query, null, controller.signal)
        .then((page) => {
          if (version === generation.current) {
            setThreads(page.threads);
            setCursor(page.cursor);
          }
        })
        .catch((e) => {
          if (version === generation.current && !controller.signal.aborted)
            setError(e.message);
        })
        .finally(() => {
          if (version === generation.current) setLoading(false);
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, revision, getPage, setThreads]);
  async function more() {
    const version = generation.current;
    setLoading(true);
    setError("");
    try {
      const page = await getPage(query, cursor);
      if (version === generation.current) {
        setThreads((previous) => [...previous, ...page.threads]);
        setCursor(page.cursor);
      }
    } catch (e) {
      if (version === generation.current) setError((e as Error).message);
    } finally {
      if (version === generation.current) setLoading(false);
    }
  }
  const contents = (
    <>
      <Input
        className="mx-3 w-[calc(100%_-_1.5rem)]"
        aria-label="Search chat history"
        placeholder="Search chats..."
        value={query}
        maxLength={200}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="flex w-full flex-1 flex-col gap-2 overflow-y-auto px-2 pb-4">
        {error && (
          <p
            role="alert"
            className="text-destructive text-sm"
          >
            {error}
          </p>
        )}
        {loading && (
          <p
            role="status"
            className="text-muted-foreground text-sm"
          >
            Loading chats...
          </p>
        )}
        {error && (
          <Button
            variant="outline"
            onClick={refresh}
          >
            Retry
          </Button>
        )}
        {!loading && !error && !threads.length && (
          <p className="text-muted-foreground p-2 text-sm">
            {query ? "No matching chats." : "No conversations yet."}
          </p>
        )}
        {threads.map((t) => (
          <div
            key={t.thread_id}
            className="flex w-full items-center"
          >
            <Button
              variant="ghost"
              aria-current={selected === t.thread_id ? "page" : undefined}
              className="h-auto min-w-0 flex-1 justify-start py-2 text-left font-normal"
              onClick={() => {
                setSelected(t.thread_id);
                if (!large) setOpen(false);
              }}
            >
              <span className="min-w-0">
                <span className="block truncate">{t.title}</span>
                {t.snippet && (
                  <span className="text-muted-foreground block truncate text-xs">
                    {t.snippet}
                  </span>
                )}
              </span>
            </Button>
            <ChatActions
              id={t.thread_id}
              title={t.title}
              busy={t.status === "busy"}
            />
          </div>
        ))}
        {cursor && (
          <Button
            variant="outline"
            disabled={loading}
            onClick={more}
          >
            Load more
          </Button>
        )}
      </div>
    </>
  );
  return (
    <>
      <div className="bg-sidebar text-sidebar-foreground hidden h-screen w-[300px] shrink-0 flex-col gap-4 border-r lg:flex">
        <div className="flex items-center justify-between px-3 pt-2">
          <h1 className="text-xl font-semibold">Thread History</h1>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Toggle thread history"
            onClick={() => setOpen(false)}
          >
            <PanelRightOpen className="size-5" />
          </Button>
        </div>
        {large && contents}
      </div>
      <Sheet
        open={!!open && !large}
        onOpenChange={setOpen}
      >
        <SheetContent
          side="left"
          className="flex flex-col gap-4 p-2"
        >
          <SheetHeader>
            <SheetTitle>Thread History</SheetTitle>
          </SheetHeader>
          {!large && contents}
        </SheetContent>
      </Sheet>
    </>
  );
}
