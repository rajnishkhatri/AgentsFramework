/**
 * greeting_vm — nowISO + optional displayName → GreetingVM (FR-9/FR-10/FR-11).
 *
 * Pure T1 map for the Dashboard header: time-of-day greeting + optional
 * caller-supplied display name, plus an Intl-formatted weekday/date subline.
 * Clock is injected (`nowISO`); no `Date.now()`, no React, no I/O.
 * Never derives a name from `learner_id` (C-4 honesty / FR-11).
 *
 * Imports nothing from wire (inputs are plain strings). Stdlib only.
 */

export interface GreetingVM {
  readonly headline: string;
  readonly subline: string;
}

function timeOfDayGreeting(now: Date): string {
  const hour = now.getHours();
  const minute = now.getMinutes();
  const mins = hour * 60 + minute;
  // [05:00 .. 12:00) morning; [12:00 .. 18:00) afternoon; else evening.
  if (mins >= 5 * 60 && mins < 12 * 60) return "Good morning";
  if (mins >= 12 * 60 && mins < 18 * 60) return "Good afternoon";
  return "Good evening";
}

export function toGreetingVM(nowISO: string, displayName?: string): GreetingVM {
  const now = new Date(nowISO);
  const greeting = timeOfDayGreeting(now);
  const subline = new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(now);
  const headline =
    displayName != null && displayName.length > 0
      ? `${greeting}, ${displayName}`
      : greeting;
  return { headline, subline };
}
