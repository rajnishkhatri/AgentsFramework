-- Commit-first coach FR-10: additive nullable resolution on attempt.
-- Engine schema has no drizzle-kit pipeline yet (same posture as C2
-- misconception / E1a tutorial teaching fields); hand-authored ALTER only.
-- Values: first_try | coached | walked_through. Null = legacy / non-resolving.
ALTER TABLE "attempt" ADD COLUMN "resolution" text;
