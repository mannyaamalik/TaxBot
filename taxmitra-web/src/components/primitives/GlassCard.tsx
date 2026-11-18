"use client";
import { cn } from "@/lib/utils";
import { HTMLAttributes, ElementType } from "react";

interface GlassCardProps extends HTMLAttributes<HTMLElement> {
  as?:     ElementType;
  hover?:  boolean;
  padding?: "none" | "sm" | "md" | "lg";
}

const paddingMap = {
  none: "",
  sm:   "p-4",
  md:   "p-6",
  lg:   "p-8",
};

export function GlassCard({
  as: Tag = "div",
  hover = false,
  padding = "md",
  className,
  children,
  ...props
}: GlassCardProps) {
  return (
    <Tag
      className={cn(
        "glass rounded-2xl border",
        "border-white/[0.08] shadow-glass",
        hover && "transition-all duration-base hover:border-white/[0.15] hover:shadow-popup cursor-pointer",
        paddingMap[padding],
        className
      )}
      {...props}
    >
      {children}
    </Tag>
  );
}
