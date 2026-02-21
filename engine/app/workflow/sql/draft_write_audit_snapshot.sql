-- :ctx = json string
WITH inp AS (
  SELECT
    CAST(:ctx AS jsonb) AS j,
    COALESCE((CAST(:ctx AS jsonb)->>'dry_run')::boolean, false) AS dry_run,
    NULLIF((CAST(:ctx AS jsonb)->>'book_id'), '')::uuid AS book_id,
    NULLIF((CAST(:ctx AS jsonb)->>'chapter_id'), '')::uuid AS chapter_id,
    NULLIF(COALESCE(CAST(:ctx AS jsonb)->>'run_id', CAST(:ctx AS jsonb)#>>'{_run,run_id}', ''), '')::uuid AS run_id,
    COALESCE(CAST(:ctx AS jsonb)->'audit_before_state', '{}'::jsonb) AS before_state,
    COALESCE(CAST(:ctx AS jsonb)->'audit_after_state', '{}'::jsonb) AS after_state,
    COALESCE(CAST(:ctx AS jsonb)->'audit_diff', '[]'::jsonb) AS diff
),
ins AS (
  INSERT INTO state_apply_audit(book_id, chapter_id, run_id, action_type, before_state, after_state, diff, reason)
  SELECT i.book_id, i.chapter_id, i.run_id, 'draft_commit', i.before_state, i.after_state, i.diff, 'workflow commit snapshot'
  FROM inp i
  WHERE i.dry_run = false AND i.book_id IS NOT NULL
  RETURNING audit_id
)
SELECT jsonb_build_object(
  'audit_result', jsonb_build_object(
    'dry_run', (SELECT dry_run FROM inp),
    'audit_id', COALESCE((SELECT audit_id::text FROM ins LIMIT 1), '')
  )
) AS data;
