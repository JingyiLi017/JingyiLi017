-- :ctx = json string
WITH inp AS (
  SELECT CAST(:ctx AS jsonb) AS j
),
cid AS (
  SELECT NULLIF((SELECT j->>'chapter_id' FROM inp), '')::uuid AS chapter_id
),
vol AS (
  SELECT NULLIF((SELECT j->>'volume_id' FROM inp), '')::uuid AS volume_id
),
runtime AS (
  SELECT
    COALESCE((SELECT (j->>'chapter_no')::int FROM inp), 0) AS chapter_no,
    COALESCE((SELECT (j->>'p_vol')::numeric FROM inp), 0) AS p_vol,
    COALESCE((SELECT (j->>'chapters_to_end')::int FROM inp), 9999) AS chapters_to_end
),
plan AS (
  SELECT vp.vol_plan_id, vp.version, vp.assumptions
  FROM volume_plan vp
  JOIN vol v ON v.volume_id = vp.volume_id
  WHERE vp.status = 'active'
  ORDER BY vp.version DESC
  LIMIT 1
),
items AS (
  SELECT COALESCE(
    jsonb_agg(
      jsonb_build_object(
        'item_id', vpi.item_id::text,
        'kind', vpi.kind,
        'summary', COALESCE((vpi.meta->>'summary'), ''),
        'target_window', vpi.target_window,
        'target_p_vol_min', vpi.target_p_vol_min,
        'target_p_vol_max', vpi.target_p_vol_max,
        'priority', vpi.priority,
        'must_happen', vpi.must_happen,
        'meta', COALESCE(vpi.meta, '{}'::jsonb),
        'ref_id', vpi.ref_id::text
      )
      ORDER BY vpi.priority DESC, vpi.created_at
    ),
    '[]'::jsonb
  ) AS arr
  FROM volume_plan_item vpi
  JOIN plan p ON p.vol_plan_id = vpi.vol_plan_id
),
orch AS (
  SELECT
    COALESCE((SELECT j->'book_settings'->'orchestrator' FROM inp), '{}'::jsonb) AS cfg_book,
    COALESCE(
      (
        SELECT bs.orchestrator_limits
        FROM book_state bs
        WHERE bs.book_id = NULLIF((SELECT j->>'book_id' FROM inp), '')::uuid
        LIMIT 1
      ),
      '{}'::jsonb
    ) AS cfg_state,
    COALESCE(
      (
        SELECT cs.settings->'orchestrator'
        FROM chapter_settings cs
        JOIN cid ON cs.chapter_id = cid.chapter_id
        LIMIT 1
      ),
      '{}'::jsonb
    ) AS cfg_chapter
),
exp AS (
  UPDATE combo_injection ci
  SET status = 'expired'
  FROM runtime r
  WHERE ci.book_id = NULLIF((SELECT j->>'book_id' FROM inp), '')::uuid
    AND ci.status = 'pending'
    AND ci.expires_after_chapter_no IS NOT NULL
    AND r.chapter_no > 0
    AND ci.expires_after_chapter_no < r.chapter_no
  RETURNING ci.inj_id
),
inj AS (
  SELECT COALESCE(
    jsonb_agg(
      jsonb_build_object(
        'inj_id', ci.inj_id::text,
        'combo_type', ci.combo_type,
        'window_next_chapters', ci.window_next_chapters,
        'priority', ci.priority,
        'volume_id', ci.volume_id::text,
        'status', ci.status,
        'expires_after_chapter_no', ci.expires_after_chapter_no
      )
      ORDER BY ci.created_at DESC
    ),
    '[]'::jsonb
  ) AS arr
  FROM combo_injection ci
  WHERE ci.book_id = NULLIF((SELECT j->>'book_id' FROM inp), '')::uuid
    AND ci.status = 'pending'
    AND (
      ci.volume_id IS NULL
      OR ci.volume_id = (SELECT volume_id FROM vol)
    )
)
SELECT jsonb_build_object(
  'volume_plan', COALESCE(
    (SELECT jsonb_build_object('vol_plan_id', p.vol_plan_id::text, 'version', p.version, 'assumptions', COALESCE(p.assumptions, '{}'::jsonb)) FROM plan p),
    '{}'::jsonb
  ),
  'volume_plan_items', COALESCE((SELECT arr FROM items), '[]'::jsonb),
  'near_end_force', CASE
    WHEN (SELECT chapters_to_end FROM runtime) <= 2 OR (SELECT p_vol FROM runtime) >= 0.95
    THEN jsonb_build_array(
      jsonb_build_object(
        'task_id', gen_random_uuid()::text,
        'type', 'cliff',
        'source', 'near_end_force',
        'must_happen', true,
        'priority', 5,
        'intensity', 2,
        'structure_weight', 1,
        'target_window', jsonb_build_object('min', (SELECT p_vol FROM runtime), 'max', 1.0),
        'p_vol', (SELECT p_vol FROM runtime),
        'refs', jsonb_build_object('reason', 'near_end'),
        'meta', jsonb_build_object('forced', true, 'reason', 'near_end')
      )
    )
    ELSE '[]'::jsonb
  END,
  'combo_injections', COALESCE((SELECT arr FROM inj), '[]'::jsonb),
  'orchestrator_limits', jsonb_build_object(
    'max_structure_weight', COALESCE(((SELECT cfg_chapter FROM orch)->>'max_structure_weight')::int, ((SELECT cfg_state FROM orch)->>'max_structure_weight')::int, ((SELECT cfg_book FROM orch)->>'max_structure_weight')::int, 4),
    'max_tasks_per_chapter', COALESCE(((SELECT cfg_chapter FROM orch)->>'max_tasks_per_chapter')::int, ((SELECT cfg_state FROM orch)->>'max_tasks_per_chapter')::int, ((SELECT cfg_state FROM orch)->>'max_tasks')::int, ((SELECT cfg_book FROM orch)->>'max_tasks_per_chapter')::int, 3),
    'ban_strong_cliff', COALESCE(((SELECT cfg_chapter FROM orch)->>'ban_strong_cliff')::boolean, ((SELECT cfg_state FROM orch)->>'ban_strong_cliff')::boolean, ((SELECT cfg_book FROM orch)->>'ban_strong_cliff')::boolean, false),
    'defer_max_rounds', COALESCE((((SELECT cfg_chapter FROM orch)->'replay'->>'defer_max_rounds'))::int, (((SELECT cfg_state FROM orch)->'replay'->>'defer_max_rounds'))::int, (((SELECT cfg_book FROM orch)->'replay'->>'defer_max_rounds'))::int, 3),
    'defer_expire_grace', COALESCE((((SELECT cfg_chapter FROM orch)->'replay'->>'defer_expire_grace'))::numeric, (((SELECT cfg_state FROM orch)->'replay'->>'defer_expire_grace'))::numeric, (((SELECT cfg_book FROM orch)->'replay'->>'defer_expire_grace'))::numeric, 0.12)
  ),
  'orchestrator_context_budget', jsonb_build_object(
    'character_facts', jsonb_build_object(
      'max_items', COALESCE((((SELECT cfg_chapter FROM orch)->'context_budget'->'character_facts'->>'max_items'))::int, (((SELECT cfg_book FROM orch)->'context_budget'->'character_facts'->>'max_items'))::int, 8),
      'max_chars', COALESCE((((SELECT cfg_chapter FROM orch)->'context_budget'->'character_facts'->>'max_chars'))::int, (((SELECT cfg_book FROM orch)->'context_budget'->'character_facts'->>'max_chars'))::int, 1000)
    ),
    'timeline_facts', jsonb_build_object(
      'max_items', COALESCE((((SELECT cfg_chapter FROM orch)->'context_budget'->'timeline_facts'->>'max_items'))::int, (((SELECT cfg_book FROM orch)->'context_budget'->'timeline_facts'->>'max_items'))::int, 8),
      'max_chars', COALESCE((((SELECT cfg_chapter FROM orch)->'context_budget'->'timeline_facts'->>'max_chars'))::int, (((SELECT cfg_book FROM orch)->'context_budget'->'timeline_facts'->>'max_chars'))::int, 1000)
    ),
    'open_foreshadows', jsonb_build_object(
      'max_items', COALESCE((((SELECT cfg_chapter FROM orch)->'context_budget'->'open_foreshadows'->>'max_items'))::int, (((SELECT cfg_book FROM orch)->'context_budget'->'open_foreshadows'->>'max_items'))::int, 6),
      'max_chars', COALESCE((((SELECT cfg_chapter FROM orch)->'context_budget'->'open_foreshadows'->>'max_chars'))::int, (((SELECT cfg_book FROM orch)->'context_budget'->'open_foreshadows'->>'max_chars'))::int, 900)
    ),
    'growth_milestones', jsonb_build_object(
      'max_items', COALESCE((((SELECT cfg_chapter FROM orch)->'context_budget'->'growth_milestones'->>'max_items'))::int, (((SELECT cfg_book FROM orch)->'context_budget'->'growth_milestones'->>'max_items'))::int, 6),
      'max_chars', COALESCE((((SELECT cfg_chapter FROM orch)->'context_budget'->'growth_milestones'->>'max_chars'))::int, (((SELECT cfg_book FROM orch)->'context_budget'->'growth_milestones'->>'max_chars'))::int, 900)
    )
  )
) AS data;
