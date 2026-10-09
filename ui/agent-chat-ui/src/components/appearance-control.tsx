"use client";

import { Check, Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import {
  useEffect,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { TooltipIconButton } from "@/components/thread/tooltip-icon-button";
import { cn } from "@/lib/utils";

const subscribe = () => () => {};
const choices = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

export function AppearanceControl() {
  const mounted = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const items = useRef<(HTMLButtonElement | null)[]>([]);
  const selected = choices.findIndex((choice) => choice.value === theme);
  const current = choices[selected] ?? choices[2];
  const Icon = current.icon;

  useEffect(() => {
    if (!open) return;
    items.current[selected < 0 ? 2 : selected]?.focus();
    const dismiss = (event: PointerEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, [open, selected]);

  // Reserve the trigger's space until the browser preference is available.
  if (!mounted)
    return (
      <div
        className="size-10"
        aria-hidden="true"
      />
    );

  const close = () => {
    setOpen(false);
    trigger.current?.focus();
  };

  return (
    <div
      ref={container}
      className="relative shrink-0"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          event.preventDefault();
          event.stopPropagation();
          close();
        }
      }}
    >
      <TooltipIconButton
        ref={trigger}
        tooltip="Appearance"
        tooltipDisabled={open}
        aria-label={`Appearance: ${current.label}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        className="size-10"
        onClick={() => setOpen((value) => !value)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            setOpen(true);
          }
        }}
      >
        <Icon
          className="size-5"
          aria-hidden="true"
        />
      </TooltipIconButton>
      {open && (
        <div
          id={menuId}
          role="menu"
          aria-label="Appearance"
          className="bg-popover text-popover-foreground absolute top-full right-0 z-50 mt-1 w-40 rounded-lg border p-1 shadow-lg"
          onKeyDown={(event) => {
            const index = items.current.indexOf(
              document.activeElement as HTMLButtonElement,
            );
            let next: number;
            switch (event.key) {
              case "ArrowDown":
                next = (index + 1) % choices.length;
                break;
              case "ArrowUp":
                next = (index + choices.length - 1) % choices.length;
                break;
              case "Home":
                next = 0;
                break;
              case "End":
                next = choices.length - 1;
                break;
              default:
                return;
            }
            event.preventDefault();
            items.current[next]?.focus();
          }}
        >
          <p className="text-muted-foreground px-2 py-1.5 text-xs font-medium">
            Appearance
          </p>
          {choices.map(({ value, label, icon: ChoiceIcon }, index) => (
            <button
              key={value}
              ref={(element) => {
                items.current[index] = element;
              }}
              type="button"
              role="menuitemradio"
              aria-checked={theme === value}
              tabIndex={-1}
              className={cn(
                "hover:bg-accent hover:text-accent-foreground focus-visible:bg-accent focus-visible:text-accent-foreground flex min-h-10 w-full cursor-pointer items-center gap-2.5 rounded-md px-2 text-sm outline-none",
                theme === value && "bg-accent/50",
              )}
              onClick={() => {
                setTheme(value);
                close();
              }}
            >
              <ChoiceIcon
                className="text-muted-foreground size-4"
                aria-hidden="true"
              />
              <span>{label}</span>
              {theme === value && (
                <Check
                  className="ml-auto size-4"
                  aria-hidden="true"
                />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
