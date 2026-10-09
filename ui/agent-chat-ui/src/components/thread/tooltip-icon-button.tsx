"use client";

import { forwardRef } from "react";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Button, ButtonProps } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type TooltipIconButtonProps = ButtonProps & {
  tooltip: string;
  tooltipDisabled?: boolean;
  side?: "top" | "bottom" | "left" | "right";
};

export const TooltipIconButton = forwardRef<
  HTMLButtonElement,
  TooltipIconButtonProps
>(
  (
    { children, tooltip, tooltipDisabled, side = "bottom", className, ...rest },
    ref,
  ) => {
    return (
      <TooltipProvider>
        <Tooltip open={tooltipDisabled ? false : undefined}>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              {...rest}
              className={cn("size-6 p-1", className)}
              ref={ref}
            >
              {children}
              <span className="sr-only">{tooltip}</span>
            </Button>
          </TooltipTrigger>
          {!tooltipDisabled && (
            <TooltipContent side={side}>{tooltip}</TooltipContent>
          )}
        </Tooltip>
      </TooltipProvider>
    );
  },
);

TooltipIconButton.displayName = "TooltipIconButton";
