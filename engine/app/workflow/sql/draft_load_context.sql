-- :ctx = json string
WITH inp AS (
  SELECT CAST(:ctx AS jsonb) AS j
),
base AS (
  SELECT
    c.chapter_id,
    c.book_id,
    c."order" AS chapter_no,
    c.title AS chapter_title,
    b.title AS book_title
  FROM chapter c
  JOIN book b ON b.book_id = c.book_id
  JOIN inp i ON c.chapter_id = NULLIF(i.j->>'chapter_id', '')::uuid
  LIMIT 1
),
recent AS (
  SELECT COALESCE(
    jsonb_agg(jsonb_build_object('chapter_no', r.chapter_no, 'title', r.title) ORDER BY r.chapter_no DESC),
    '[]'::jsonb
  ) AS rows
  FROM (
    SELECT c."order" AS chapter_no, c.title
    FROM chapter c
    JOIN base b ON b.book_id = c.book_id
    WHERE c."order" < b.chapter_no
    ORDER BY c."order" DESC
    LIMIT 3
  ) r
),
bs AS (
  SELECT COALESCE(s.settings, '{}'::jsonb) AS settings
  FROM base b
  LEFT JOIN book_settings s ON s.book_id = b.book_id
),
rs AS (
  SELECT COALESCE((cr.report->'reader_state'), '{}'::jsonb) AS reader_state
  FROM chapter_report cr
  JOIN chapter c ON c.chapter_id = cr.chapter_id
  JOIN base b ON b.book_id = c.book_id
  ORDER BY cr.created_at DESC
  LIMIT 1
),
char_facts AS (
  SELECT COALESCE(
    jsonb_agg(
      jsonb_build_object(
        'entity_name', x.entity_name,
        'fact_type', x.fact_type,
        'fact', x.fact,
        'confidence', x.confidence
      )
      ORDER BY x.chapter_no DESC, x.created_at DESC
    ),
    '[]'::jsonb
  ) AS rows
  FROM (
    SELECT
      cf.entity_name,
      cf.fact_type,
      cf.fact,
      cf.confidence,
      c."order" AS chapter_no,
      cf.created_at
    FROM chapter_fact cf
    JOIN chapter c ON c.chapter_id = cf.chapter_id
    JOIN base b ON b.book_id = c.book_id
    WHERE c."order" <= b.chapter_no
    ORDER BY c."order" DESC, cf.created_at DESC
    LIMIT 20
  ) x
),
timeline_facts AS (
  SELECT COALESCE(
    jsonb_agg(
      jsonb_build_object(
        'chapter_no', x.chapter_no,
        'event_no', x.event_no,
        'time_hint', x.time_hint,
        'location', x.location,
        'event', x.event,
        'consequence', x.consequence
      )
      ORDER BY x.chapter_no DESC, x.event_no ASC
    ),
    '[]'::jsonb
  ) AS rows
  FROM (
    SELECT
      c."order" AS chapter_no,
      te.event_no,
      te.time_hint,
      te.location,
      te.event,
      te.consequence
    FROM chapter_timeline_event te
    JOIN chapter c ON c.chapter_id = te.chapter_id
    JOIN base b ON b.book_id = c.book_id
    WHERE c."order" <= b.chapter_no
    ORDER BY c."order" DESC, te.event_no ASC
    LIMIT 20
  ) x
),
open_foreshadows AS (
  SELECT COALESCE(
    jsonb_agg(
      jsonb_build_object(
        'foreshadow_id', f.foreshadow_id::text,
        'title', f.title,
        'type', f.type,
        'status', f.status,
        'priority', f.priority,
        'question', f.question,
        'expected_payoff', f.expected_payoff,
        'planned_payoff_chapter_id', f.planned_payoff_chapter_id::text
      )
      ORDER BY f.priority DESC, f.updated_at DESC
    ),
    '[]'::jsonb
  ) AS rows
  FROM foreshadow f
  JOIN base b ON b.book_id = f.book_id
  WHERE f.status IN ('seeded', 'reinforced', 'payoff_planned')
  LIMIT 12
),
growth_nodes AS (
  SELECT COALESCE(
    jsonb_agg(
      jsonb_build_object(
        'milestone_id', gm.milestone_id::text,
        'character_name', gm.character_name,
        'title', gm.title,
        'stage', gm.stage,
        'status', gm.status,
        'priority', gm.priority,
        'planned_chapter_no', gm.planned_chapter_no,
        'payoff_template_type', gm.payoff_template_type
      )
      ORDER BY gm.priority DESC, gm.updated_at DESC
    ),
    '[]'::jsonb
  ) AS rows
  FROM growth_milestone gm
  JOIN base b ON b.book_id = gm.book_id
  WHERE gm.status IN ('planned', 'in_progress')
  LIMIT 12
),
prev_deferred AS (
  SELECT COALESCE(ct.payload->'deferred_tasks', '[]'::jsonb) AS rows
  FROM chapter_trace ct
  JOIN chapter c_prev ON c_prev.chapter_id = ct.chapter_id
  JOIN base b ON b.book_id = c_prev.book_id
  WHERE c_prev."order" = b.chapter_no - 1
  ORDER BY ct.created_at DESC
  LIMIT 1
)
SELECT jsonb_build_object(
  'context', jsonb_build_object(
    'book_title', COALESCE((SELECT book_title FROM base), ''),
    'chapter_title', COALESCE((SELECT chapter_title FROM base), ''),
    'recent_chapters', COALESCE((SELECT rows FROM recent), '[]'::jsonb)
  ),
  'book_settings', COALESCE((SELECT settings FROM bs), '{}'::jsonb),
  'character_facts', COALESCE((SELECT rows FROM char_facts), '[]'::jsonb),
  'timeline_facts', COALESCE((SELECT rows FROM timeline_facts), '[]'::jsonb),
  'open_foreshadows', COALESCE((SELECT rows FROM open_foreshadows), '[]'::jsonb),
  'growth_milestones', COALESCE((SELECT rows FROM growth_nodes), '[]'::jsonb),
  'deferred_tasks_in', COALESCE((SELECT rows FROM prev_deferred), '[]'::jsonb),
  'reader_state', CASE
    WHEN (SELECT reader_state FROM rs) IS NULL OR (SELECT reader_state FROM rs) = '{}'::jsonb
      THEN jsonb_build_object('expectation',0.6,'tension',0.4,'clarity',0.7,'satisfaction',0.3,'fatigue',0.1)
    ELSE (SELECT reader_state FROM rs)
  END
) AS data;
