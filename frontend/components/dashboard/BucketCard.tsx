/**
 * BucketCard — one skill-mastery card in the dashboard grid (FR-C3).
 *
 * Presentational only (F-R1): renders a `BucketCardVM`. Shows the bucket name,
 * mastery %, share-of-test %, a bucket-colored progress bar (the `--color-bucket-*`
 * accent, FR-A3), and a "Due" badge when due. The card IS a link (FR-C4): per the
 * prototype, a bucket click opens Skill detail (`/learn/skill?skillId=<id>`) — the
 * teach plane, not a drill. `/learn/skill` is live (E1a/ADR-0028; SD-6), so this is
 * the real destination, not the interim `/learn/quiz?focus=` drill it replaced.
 *
 * FR-A8 (color is never the sole signal): "Due" is a text badge, not just a color;
 * mastery is a number, not only a bar length. State rides `data-*` (§13).
 */

import * as React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import type { BucketCardVM } from "@/lib/translators/bucket_card_vm";
import { screen } from "@/components/shell/nav_model";

export function BucketCard(props: { vm: BucketCardVM }): React.JSX.Element {
  const { vm } = props;
  // SD-6: open Skill detail (the teach plane) for this bucket's skill. The skill
  // route comes from the nav model; the Skill page reads `?skillId` and matches
  // by Skill.id (mirrors SummaryView's "See full lesson" link).
  const skillHref = `${screen("skill").route}?skillId=${vm.skillId}`;
  return (
    <Link
      href={skillHref}
      data-testid={`bucket-${vm.skillId}`}
      data-due={vm.due ? "true" : "false"}
      // Scope the bucket accent to a local var the bar + border read (FR-A3).
      style={{ ["--accent" as string]: `var(${vm.accentVar})` }}
      className={cn(
        "flex flex-col gap-3 rounded-[13px] border p-4",
        "border-[color-mix(in_oklab,var(--accent)_30%,var(--color-border))]",
        "hover:border-[color-mix(in_oklab,var(--accent)_55%,var(--color-border))]",
      )}
    >
      <header className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {vm.accentVar ? (
            <span
              data-testid={`bucket-dot-${vm.skillId}`}
              aria-hidden="true"
              className="h-[11px] w-[11px] shrink-0 rounded bg-[var(--accent)]"
            />
          ) : null}
          <h3 className="text-sm font-semibold">{vm.name}</h3>
        </div>
        {vm.due ? (
          <span
            data-testid={`due-${vm.skillId}`}
            className="rounded-full bg-[color-mix(in_oklab,var(--accent)_18%,transparent)] px-2 py-0.5 text-xs font-semibold text-fg"
          >
            Due
          </span>
        ) : null}
      </header>

      {/*
        Honest-null (Epic F FR-4 / P-4): a bucket with no SkillState has UNKNOWN
        mastery. Render an inert "no data" track — NOT a role=progressbar with
        aria-valuenow=0, which a screen reader (and the eye) can't tell apart
        from a genuine 0% mastery. The KNOWN flag gates the whole bar+percent.
      */}
      {vm.masteryKnown ? (
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
      ) : (
        <div
          data-testid={`bucket-nodata-${vm.skillId}`}
          className="h-2 w-full rounded-full bg-selected opacity-40"
          aria-hidden="true"
        />
      )}

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
            {vm.masteryKnown ? (
              <>
                <span className="font-semibold text-fg">{vm.masteryPct}%</span>
                <span>mastery</span>
              </>
            ) : (
              // Honest absence — never a fabricated 0% (FR-4).
              <span className="italic">No data yet</span>
            )}
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
    </Link>
  );
}
