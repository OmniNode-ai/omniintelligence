-- Migration: 029_plan_reviewer_slot_ids
-- Purpose: plan reviewer identifiers name reviewer slots, not models [OMN-21790]
--
-- EnumReviewModel values are slot names; the model behind a slot is bound by the
-- deployment overlay. Rename the identifiers seeded by 020 (and recorded in
-- plan_reviewer_strategy_runs.models_used) to the slot names. Idempotent: a row
-- already renamed is untouched.

UPDATE plan_reviewer_model_accuracy AS acc
SET model_id = renamed.slot_id
FROM (VALUES
    ('qwen3-coder', 'code-drafter'),
    ('deepseek-r1', 'deep-reasoner'),
    ('gemini-flash', 'fast-reviewer'),
    ('glm-4', 'tiebreaker')
) AS renamed (model_id, slot_id)
WHERE acc.model_id = renamed.model_id
  AND NOT EXISTS (
      SELECT 1 FROM plan_reviewer_model_accuracy AS taken
      WHERE taken.model_id = renamed.slot_id
  );

UPDATE plan_reviewer_strategy_runs
SET models_used = array_replace(
    array_replace(
        array_replace(
            array_replace(models_used, 'qwen3-coder', 'code-drafter'),
            'deepseek-r1', 'deep-reasoner'),
        'gemini-flash', 'fast-reviewer'),
    'glm-4', 'tiebreaker')
WHERE models_used && ARRAY['qwen3-coder', 'deepseek-r1', 'gemini-flash', 'glm-4'];
