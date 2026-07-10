-- C2 / ADR-0027: additive nullable misconception on test_item.
-- Engine schema has no drizzle-kit pipeline yet (same posture as S3
-- target_count T-a3 N/A); hand-authored to match the plan artifact
-- `frontend/drizzle/00NN_add_misconception_to_test_item.sql`.
ALTER TABLE "test_item" ADD COLUMN "misconception" text;
