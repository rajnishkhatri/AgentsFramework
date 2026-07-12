-- E1a / ADR-0028: additive nullable teaching fields on tutorial.
-- Engine schema has no drizzle-kit pipeline yet (same posture as C2
-- misconception / S3 target_count); hand-authored ALTER TABLE only (no drop).
ALTER TABLE "tutorial" ADD COLUMN "ground_md" text;
ALTER TABLE "tutorial" ADD COLUMN "pitfall_md" text;
ALTER TABLE "tutorial" ADD COLUMN "question_md" text;
ALTER TABLE "tutorial" ADD COLUMN "self_explain_prompt" text;
ALTER TABLE "tutorial" ADD COLUMN "worked_example" jsonb;
ALTER TABLE "tutorial" ADD COLUMN "completion_try" jsonb;
ALTER TABLE "tutorial" ADD COLUMN "annotated_examples" jsonb;
