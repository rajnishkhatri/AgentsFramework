// E1a: 'use client' — Skill lesson surface reads the engine bag via useSkillDetail.
"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { SkillDetailView } from "@/components/learn/SkillDetailView";
import { useSkillDetail } from "@/components/learn/use_skill_detail";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";

const LEARNER_ID = "Garvit";

export default function SkillPage(): React.JSX.Element {
  const searchParams = useSearchParams();
  const skillId = searchParams.get("skillId");
  const contextParam = searchParams.get("context");
  const requested =
    contextParam === "newSkill" ||
    contextParam === "returning" ||
    contextParam === "refresher"
      ? contextParam
      : undefined;

  const { result, loading } = useSkillDetail({
    subject: DEFAULT_SUBJECT,
    learnerId: LEARNER_ID,
    skillId,
    ...(requested != null ? { requested } : {}),
  });

  if (loading || result == null) {
    return (
      <div data-testid="skill-detail-loading" className="p-6 text-sm text-muted">
        Loading lesson…
      </div>
    );
  }

  if (result.status === "not_found") {
    return (
      <div data-testid="skill-detail-404" className="flex flex-col gap-2 p-6">
        <h1 className="text-xl font-semibold">Lesson not found</h1>
        <p className="text-sm text-muted">
          Unknown or missing skill. Pick a skill from Home or Summary.
        </p>
      </div>
    );
  }

  return <SkillDetailView vm={result.vm} />;
}
