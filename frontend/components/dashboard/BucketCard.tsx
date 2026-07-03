/**
 * BucketCard — one skill-mastery card in the dashboard grid (FR-C3).
 *
 * Presentational only (F-R1): renders a `BucketCardVM`. Shows the bucket name,
 * mastery %, share-of-test %, a bucket-colored progress bar (the `--color-bucket-*`
 * accent, FR-A3), and a "Due" badge when due. The card is a link to the bucket's
 * Skill detail (FR-C4) — currently the coming-soon Skill screen, so the whole card
 * is rendered by the parent grid; here we keep it a self-contained article.
 *
 * FR-A8 (color is never the sole signal): "Due" is a text badge, not just a color;
 * mastery is a number, not only a bar length. State rides `data-*` (§13).
 */

import * as React from "react";
import { cn } from "@/lib/utils";
import type { BucketCardVM } from "@/lib/translators/bucket_card_vm";

export function BucketCard(props: { vm: BucketCardVM }): React.JSX.Element {
  const { vm } = props;
  return (
    <article
      data-testid={`bucket-${vm.skillId}`}
      data-due={vm.due ? "true" : "false"}
      // Scope the bucket accent to a local var the bar + border read (FR-A3).
      style={{ ["--accent" as string]: `var(${vm.accentVar})` }}
      className={cn(
        "flex flex-col gap-3 rounded-[13px] border p-4",
        "border-[color-mix(in_oklab,var(--accent)_30%,var(--color-border))]",
      )}
    >
      <header className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{vm.name}</h3>
        {vm.due ? (
          <span
            data-testid={`due-${vm.skillId}`}
            className="rounded-full bg-[color-mix(in_oklab,var(--accent)_18%,transparent)] px-2 py-0.5 text-xs font-semibold text-fg"
          >
            Due
          </span>
        ) : null}
      </header>

      <div
        className="h-2 w-full overflow-hidden rounded-full bg-selected"
        role="progressbar"
        aria-valuenow={vm.masteryPct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${vm.name} mastery`}
      >
        <div
          className="h-full rounded-full bg-[var(--accent)]"
          style={{ width: `${vm.masteryPct}%` }}
        />
      </div>

      {/*
        A <dl> may contain only <dt>/<dd> (optionally grouped in a <div>) — bare
        <span> siblings trip axe's `definition-list` rule. The visible unit word
        ("mastery" / "of test") lives inside the <dd> instead of as a loose span,
        so each grouping <div> holds exactly a <dt> + <dd>.
      */}
      <dl className="flex items-center justify-between text-xs text-muted">
        <div className="flex gap-1">
          <dt className="sr-only">Mastery</dt>
          <dd className="flex gap-1">
            <span className="font-semibold text-fg">{vm.masteryPct}%</span>
            <span>mastery</span>
          </dd>
        </div>
        <div className="flex gap-1">
          <dt className="sr-only">Share of test</dt>
          <dd className="flex gap-1">
            <span>{vm.shareOfTestPct}%</span>
            <span>of test</span>
          </dd>
        </div>
      </dl>
    </article>
  );
}
