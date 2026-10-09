import { useEffect, useRef, useState } from "react";
import { MoreHorizontal } from "lucide-react";
import { useQueryState } from "nuqs";
import { useThreads } from "@/providers/Thread";
import { useStreamContext } from "@/providers/Stream";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import * as Dialog from "@radix-ui/react-dialog";
import { toast } from "sonner";
import { useArtifactContext, useArtifactOpen } from "./artifact";

export function ChatActions({
  id,
  title,
  busy = false,
  className,
}: {
  id: string;
  title: string;
  busy?: boolean;
  className?: string;
}) {
  const { request, refresh, setThreads } = useThreads();
  const stream = useStreamContext();
  const [, closeArtifact] = useArtifactOpen();
  const [, setArtifactContext] = useArtifactContext();
  const [selected, setSelected] = useQueryState("threadId");
  const active = busy || (id === selected && stream.isLoading);
  const [menu, setMenu] = useState(false);
  const [dialog, setDialog] = useState<"rename" | "delete" | null>(null);
  const [name, setName] = useState(title);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  function showMenu() {
    const rect = trigger.current?.getBoundingClientRect();
    if (rect)
      setPosition({
        top: Math.max(8, Math.min(rect.bottom, window.innerHeight - 190)),
        left: Math.max(8, rect.right - 192),
      });
    setMenu(true);
  }
  useEffect(() => {
    if (!menu) return;
    container.current
      ?.querySelector<HTMLButtonElement>('[role="menuitem"]')
      ?.focus();
    const dismiss = (event: PointerEvent) => {
      if (!container.current?.contains(event.target as Node)) setMenu(false);
    };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, [menu]);
  async function save() {
    setSaving(true);
    setError("");
    try {
      await request(`/chat/${id}/${dialog === "rename" ? "title" : "delete"}`, {
        method: "POST",
        body: JSON.stringify(dialog === "rename" ? { title: name.trim() } : {}),
      });
      setThreads((previous) =>
        dialog === "delete"
          ? previous.filter((thread) => thread.thread_id !== id)
          : previous.map((thread) =>
              thread.thread_id === id
                ? { ...thread, title: name.trim() }
                : thread,
            ),
      );
      if (dialog === "delete" && selected === id) {
        closeArtifact();
        setArtifactContext({});
        await setSelected(null);
      }
      refresh();
      setDialog(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  async function download(format: "markdown" | "json") {
    setMenu(false);
    try {
      const result = await request(`/chat/${id}/export?format=${format}`);
      const url = URL.createObjectURL(
        new Blob([result.content], {
          type:
            format === "json"
              ? "application/json;charset=utf-8"
              : "text/markdown;charset=utf-8",
        }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = result.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      if (format === "json")
        toast.info(
          "JSON is a transcript record, not an executable replay or import format.",
        );
    } catch (e) {
      toast.error((e as Error).message);
    }
  }
  function open(kind: "rename" | "delete") {
    setMenu(false);
    setError("");
    setName(title);
    setDialog(kind);
  }
  return (
    <div
      ref={container}
      className="relative shrink-0"
    >
      <Button
        variant="ghost"
        size="icon"
        className={className}
        aria-label={`Actions for ${title}`}
        aria-haspopup="menu"
        aria-expanded={menu}
        ref={trigger}
        onClick={() => (menu ? setMenu(false) : showMenu())}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            showMenu();
          }
        }}
      >
        <MoreHorizontal className="size-5" />
      </Button>
      {menu && (
        <div
          role="menu"
          style={position}
          className="bg-popover text-popover-foreground fixed z-40 w-48 rounded-md border p-1 shadow-md"
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.preventDefault();
              e.stopPropagation();
              setMenu(false);
              trigger.current?.focus();
            }
            if (e.key === "ArrowDown" || e.key === "ArrowUp") {
              e.preventDefault();
              const items = Array.from(
                e.currentTarget.querySelectorAll<HTMLButtonElement>(
                  "button:not(:disabled)",
                ),
              );
              const index = items.indexOf(
                document.activeElement as HTMLButtonElement,
              );
              items[
                (index + (e.key === "ArrowDown" ? 1 : items.length - 1)) %
                  items.length
              ]?.focus();
            }
            if (e.key === "Home" || e.key === "End") {
              e.preventDefault();
              const items = e.currentTarget.querySelectorAll<HTMLButtonElement>(
                "button:not(:disabled)",
              );
              items[e.key === "Home" ? 0 : items.length - 1]?.focus();
            }
          }}
        >
          <Button
            autoFocus
            role="menuitem"
            variant="ghost"
            className="w-full justify-start"
            onClick={() => open("rename")}
          >
            Rename
          </Button>
          <Button
            role="menuitem"
            variant="ghost"
            className="w-full justify-start"
            disabled={active}
            onClick={() => download("markdown")}
          >
            Export Markdown
          </Button>
          <Button
            role="menuitem"
            variant="ghost"
            className="w-full justify-start"
            disabled={active}
            onClick={() => download("json")}
          >
            Export JSON
          </Button>
          <Button
            role="menuitem"
            variant="ghost"
            className="text-destructive w-full justify-start"
            disabled={active}
            onClick={() => open("delete")}
          >
            Delete
          </Button>
        </div>
      )}
      <Dialog.Root
        open={dialog !== null}
        onOpenChange={(open) => {
          if (!open && !saving) setDialog(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
          <Dialog.Content
            className="bg-background text-foreground fixed top-1/2 left-1/2 z-50 w-[calc(100%_-_2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border p-6 shadow-xl"
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              trigger.current?.focus();
            }}
            onEscapeKeyDown={(e) => {
              if (saving) e.preventDefault();
            }}
          >
            <Dialog.Title className="text-lg font-semibold">
              {dialog === "rename" ? "Rename chat" : `Delete "${title}"?`}
            </Dialog.Title>
            <Dialog.Description className="text-muted-foreground mt-2 text-sm">
              {dialog === "rename"
                ? "Enter a title of 1-100 characters."
                : "Permanently removes conversation history. Deleting history does not undo service-request actions."}
            </Dialog.Description>
            {dialog === "rename" && (
              <Input
                aria-label="Chat title"
                className="mt-4"
                value={name}
                maxLength={100}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && name.trim() && !saving) save();
                }}
              />
            )}
            {error && (
              <p
                role="alert"
                className="text-destructive mt-3 text-sm"
              >
                {error}
              </p>
            )}
            <div className="mt-5 flex justify-end gap-2">
              <Button
                variant="outline"
                disabled={saving}
                onClick={() => setDialog(null)}
              >
                Cancel
              </Button>
              <Button
                disabled={
                  saving ||
                  (dialog === "rename" &&
                    (!name.trim() || [...name.trim()].length > 100))
                }
                onClick={save}
              >
                {saving
                  ? "Saving..."
                  : dialog === "rename"
                    ? "Save"
                    : "Delete permanently"}
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
