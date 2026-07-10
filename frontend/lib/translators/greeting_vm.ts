/**
 * greeting_vm — nowISO + learnerId → GreetingVM (FR-9/FR-10).
 *
 * Pure T1 map for the Dashboard header: time-of-day greeting + title-cased
 * display name, plus an Intl-formatted weekday/date subline. Clock is injected
 * (`nowISO`); no `Date.now()`, no React, no I/O.
 *
 * Imports nothing from wire (inputs are plain strings). Stdlib only.
 */

export interface GreetingVM {
  readonly headline: string;
  readonly subline: string;
}

function titleCaseId(learnerId: string): string {
  if (learnerId.length === 0) return learnerId;
  return learnerId.charAt(0).toUpperCase() + learnerId.slice(1).toLowerCase();
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

export function toGreetingVM(nowISO: string, learnerId: string): GreetingVM {
  const now = new Date(nowISO);
  const greeting = timeOfDayGreeting(now);
  const name = titleCaseId(learnerId);
  const subline = new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(now);
  return {
    headline: `${greeting}, ${name}`,
    subline,
  };
}
