-- :ctx = json string
WITH inp AS (
  SELECT
    CAST(:ctx AS jsonb) AS j,
    COALESCE((CAST(:ctx AS jsonb)->>'dry_run')::boolean, false) AS dry_run,
    NULLIF(COALESCE(CAST(:ctx AS jsonb)->>'run_id', CAST(:ctx AS jsonb)#>>'{_run,run_id}', ''), '')::uuid AS run_id,
    NULLIF((CAST(:ctx AS jsonb)->>'book_id'), '')::uuid AS book_id,
    NULLIF((CAST(:ctx AS jsonb)->>'chapter_id'), '')::uuid AS chapter_id,
    COALESCE(NULLIF(CAST(:ctx AS jsonb)->>'variant', ''), 'A') AS variant,
    COALESCE(
      NULLIF(CAST(:ctx AS jsonb)->>'chapter_text', ''),
      NULLIF(CAST(:ctx AS jsonb)#>>'{llm_output,chapter_text}', ''),
      ''
    ) AS chapter_text,
    COALESCE(
      NULLIF(CAST(:ctx AS jsonb)->>'events_raw', ''),
      CAST(COALESCE(CAST(:ctx AS jsonb)#>'{llm_output,events_json}', '{}'::jsonb) AS text),
      ''
    ) AS events_raw,
    COALESCE(CAST(:ctx AS jsonb)->'structure', '{}'::jsonb) AS structure_json,
    COALESCE(CAST(:ctx AS jsonb)->'final_tasks', '[]'::jsonb) AS final_tasks_json,
    COALESCE(CAST(:ctx AS jsonb)->'deferred_tasks', '[]'::jsonb) AS deferred_tasks_json,
    COALESCE(CAST(:ctx AS jsonb)->'dropped_tasks', '[]'::jsonb) AS dropped_tasks_json,
    COALESCE(CAST(:ctx AS jsonb)->'orchestrator_limits_eff', '{}'::jsonb) AS limits_eff_json,
    COALESCE(CAST(:ctx AS jsonb)->'quality_report', '{}'::jsonb) AS quality_report_json,
    COALESCE(CAST(:ctx AS jsonb)->'reader_state_next', CAST(:ctx AS jsonb)->'reader_state', '{}'::jsonb) AS reader_state_json,
    COALESCE(CAST(:ctx AS jsonb)->'final_tasks', '[]'::jsonb) AS selection_tasks_json,
    COALESCE(CAST(:ctx AS jsonb)#>'{prompt_blocks,context_budget}', '{}'::jsonb) AS context_budget_json,
    COALESCE((CAST(:ctx AS jsonb)->>'phase'), '') AS phase_txt,
    COALESCE((CAST(:ctx AS jsonb)->>'intent_confirmed'), '') AS intent_txt
),
task_rows AS (
  SELECT
    t AS task,
    NULLIF(t#>>'{task_id}','') AS task_id_txt,
    lower(COALESCE(NULLIF(t#>>'{type}',''), NULLIF(t#>>'{task_type}',''))) AS task_type,
    NULLIF(t#>>'{refs,plan_item_id}','') AS plan_item_id_txt,
    NULLIF(t#>>'{refs,ref_id}','') AS ref_id_txt,
    lower(
      COALESCE(
        NULLIF(t#>>'{combo,combo_type}',''),
        NULLIF(t#>>'{refs,combo_type}',''),
        NULLIF(t#>>'{meta,from_combo}','')
      )
    ) AS combo_type,
    lower(
      COALESCE(
        NULLIF(t#>>'{combo,step}',''),
        NULLIF(t#>>'{meta,combo_step}','')
      )
    ) AS combo_step,
    NULLIF(t#>>'{combo,combo_fp}','') AS combo_fp,
    NULLIF(t#>>'{refs,ref_id}','') AS combo_id_txt,
    NULLIF(t#>>'{refs,foreshadow_id}','') AS foreshadow_id_txt,
    NULLIF(t#>>'{refs,inj_id}','') AS inj_id_txt
  FROM inp i
  CROSS JOIN LATERAL jsonb_array_elements(i.final_tasks_json) t
),
executed_task_rows AS (
  SELECT
    NULLIF(t->>'task_id','') AS task_id_txt,
    lower(COALESCE(NULLIF(t->>'type',''), NULLIF(t->>'task_type',''))) AS task_type,
    NULL::text AS plan_item_id_txt,
    NULL::text AS ref_id_txt,
    lower(COALESCE(NULLIF(t->>'combo_type',''), NULLIF(t->>'combo',''))) AS combo_type,
    lower(COALESCE(NULLIF(t->>'step',''), '')) AS combo_step,
    NULLIF(t->>'combo_fp','') AS combo_fp,
    NULL::text AS combo_id_txt,
    NULL::text AS foreshadow_id_txt,
    NULL::text AS inj_id_txt
  FROM inp i
  CROSS JOIN LATERAL jsonb_array_elements(COALESCE(i.j#>'{extracted_actions,executed_tasks}', '[]'::jsonb)) t
),
executed_task_rows_resolved AS (
  SELECT
    e.task_id_txt,
    e.task_type,
    COALESCE(NULLIF(tr.plan_item_id_txt,''), split_part(COALESCE(e.task_id_txt,''), ':', 1), NULL) AS plan_item_id_txt,
    tr.ref_id_txt,
    lower(COALESCE(NULLIF(e.combo_type,''), NULLIF(tr.combo_type,''), NULLIF(tr.task_type,''), '')) AS combo_type,
    lower(COALESCE(NULLIF(e.combo_step,''), NULLIF(tr.combo_step,''), '')) AS combo_step,
    COALESCE(NULLIF(e.combo_fp,''), NULLIF(tr.combo_fp,''), '') AS combo_fp,
    tr.combo_id_txt,
    tr.foreshadow_id_txt,
    tr.inj_id_txt
  FROM executed_task_rows e
  LEFT JOIN task_rows tr ON tr.task_id_txt = e.task_id_txt
),
combo_source_rows AS (
  SELECT
    task_id_txt, task_type, plan_item_id_txt, ref_id_txt, combo_type, combo_step, combo_fp, combo_id_txt, foreshadow_id_txt, inj_id_txt
  FROM executed_task_rows_resolved
  WHERE combo_step <> '' OR combo_type <> ''
  UNION ALL
  SELECT
    task_id_txt, task_type, plan_item_id_txt, ref_id_txt, combo_type, combo_step, combo_fp, combo_id_txt, foreshadow_id_txt, inj_id_txt
  FROM task_rows
  WHERE NOT EXISTS (SELECT 1 FROM executed_task_rows_resolved WHERE combo_step <> '' OR combo_type <> '')
),
combo_step_rows AS (
  SELECT
    plan_item_id_txt::uuid AS plan_item_id,
    combo_type,
    combo_step
  FROM combo_source_rows
  WHERE plan_item_id_txt ~* '^[0-9a-f-]{36}$'
    AND combo_type <> ''
    AND combo_step <> ''
),
combo_done_hits AS (
  SELECT DISTINCT plan_item_id, combo_type, combo_step
  FROM combo_step_rows
  WHERE
    (combo_type = 'setup_hook_combo' AND combo_step = 'hook')
    OR (combo_type = 'mid_spike_combo' AND combo_step = 'cost')
    OR (combo_type = 'reveal_combo' AND combo_step = 'reinterpret')
    OR (combo_type = 'vol_end_combo' AND combo_step IN ('main_payoff','cliff'))
),
upd_combo_done AS (
  UPDATE volume_plan_item vpi
  SET
    meta = COALESCE(vpi.meta, '{}'::jsonb) || jsonb_build_object(
      'done_status', 'done',
      'done_at', now(),
      'done_reason', 'combo_key_step_executed',
      'done_combo_type', h.combo_type,
      'done_combo_step', h.combo_step
    )
  FROM combo_done_hits h, volume_plan vp, inp i
  WHERE i.dry_run = false
    AND vpi.item_id = h.plan_item_id
    AND vpi.vol_plan_id = vp.vol_plan_id
    AND vpi.kind = 'combo'
    AND vp.book_id = i.book_id
    AND COALESCE(vpi.meta->>'done_status', 'todo') <> 'done'
  RETURNING vpi.item_id::text AS item_id, h.combo_type, h.combo_step
),
used_combo_ids AS (
  SELECT
    COALESCE(
      ARRAY_AGG(DISTINCT combo_id_txt::uuid) FILTER (WHERE combo_id_txt ~* '^[0-9a-f-]{36}$'),
      '{}'::uuid[]
    ) AS arr
  FROM task_rows
),
used_combo_fps AS (
  SELECT
    COALESCE(
      ARRAY_AGG(DISTINCT combo_fp) FILTER (WHERE combo_fp IS NOT NULL AND combo_fp <> ''),
      '{}'::text[]
    ) AS arr
  FROM task_rows
),
used_foreshadow_ids AS (
  SELECT
    COALESCE(
      ARRAY_AGG(DISTINCT foreshadow_id_txt::uuid) FILTER (WHERE foreshadow_id_txt ~* '^[0-9a-f-]{36}$'),
      '{}'::uuid[]
    ) AS arr
  FROM task_rows
),
used_injection_ids AS (
  SELECT
    COALESCE(
      ARRAY_AGG(DISTINCT inj_id_txt::uuid) FILTER (WHERE inj_id_txt ~* '^[0-9a-f-]{36}$'),
      '{}'::uuid[]
    ) AS arr
  FROM task_rows
),
upd_injection_consumed AS (
  UPDATE combo_injection ci
  SET
    status='consumed',
    consumed_chapter_id=i.chapter_id,
    consumed_at=now()
  FROM inp i, used_injection_ids u
  WHERE i.dry_run = false
    AND ci.inj_id = ANY(u.arr)
    AND ci.status='pending'
  RETURNING ci.inj_id::text AS inj_id
),
before_ct AS (
  SELECT COUNT(*)::int AS c
  FROM chapter_draft cd
  JOIN inp i ON cd.chapter_id = i.chapter_id
),
ins_draft AS (
  INSERT INTO chapter_draft(book_id, chapter_id, run_id, variant, text)
  SELECT i.book_id, i.chapter_id, i.run_id, i.variant, i.chapter_text
  FROM inp i
  WHERE i.dry_run = false AND i.book_id IS NOT NULL AND i.chapter_id IS NOT NULL AND i.run_id IS NOT NULL
  ON CONFLICT(run_id, variant) DO UPDATE
  SET
    text = EXCLUDED.text,
    branch = EXCLUDED.variant,
    is_candidate = true
  RETURNING draft_id, chapter_id, variant
),
upd_active_draft AS (
  UPDATE chapter c
  SET active_draft_id = d.draft_id
  FROM ins_draft d, inp i
  WHERE i.dry_run = false
    AND c.chapter_id = i.chapter_id
  RETURNING c.chapter_id
),
upsert_selected AS (
  INSERT INTO chapter_selected(chapter_id, selected_draft_id, selected_branch, selected_by, selected_reason)
  SELECT
    d.chapter_id,
    d.draft_id,
    d.variant,
    'agent',
    'draft_commit_auto_select'
  FROM ins_draft d
  ON CONFLICT(chapter_id) DO UPDATE SET
    selected_draft_id=EXCLUDED.selected_draft_id,
    selected_branch=EXCLUDED.selected_branch,
    selected_by=EXCLUDED.selected_by,
    selected_reason=EXCLUDED.selected_reason,
    selected_at=now()
  RETURNING chapter_id, selected_draft_id
),
mark_selected AS (
  UPDATE chapter_draft cd
  SET
    is_selected = (cd.draft_id = d.draft_id),
    selected_at = CASE WHEN cd.draft_id = d.draft_id THEN now() ELSE cd.selected_at END
  FROM ins_draft d, inp i
  WHERE i.dry_run = false
    AND cd.chapter_id = i.chapter_id
  RETURNING cd.draft_id
),
upsert_events AS (
  INSERT INTO chapter_events(draft_id, book_id, chapter_id, events, validated)
  SELECT
    d.draft_id,
    i.book_id,
    i.chapter_id,
    COALESCE(i.j->'extracted_actions', '{}'::jsonb),
    true
  FROM ins_draft d
  JOIN inp i ON true
  ON CONFLICT(draft_id) DO UPDATE
  SET
    events=EXCLUDED.events,
    validated=EXCLUDED.validated
  RETURNING draft_id
),
ins_trace AS (
  INSERT INTO chapter_trace(book_id, chapter_id, run_id, payload)
  SELECT i.book_id, i.chapter_id, i.run_id,
    jsonb_build_object(
      'structure', i.structure_json,
      'final_tasks', i.final_tasks_json,
      'deferred_tasks', i.deferred_tasks_json,
      'dropped_tasks', i.dropped_tasks_json,
      'limits_eff', i.limits_eff_json,
      'context_budget', i.context_budget_json,
      'events_raw', i.events_raw,
      'ctx_snapshot', i.j
    )
  FROM inp i
  WHERE i.dry_run = false AND i.book_id IS NOT NULL AND i.chapter_id IS NOT NULL AND i.run_id IS NOT NULL
  ON CONFLICT(run_id) DO UPDATE SET payload = EXCLUDED.payload
  RETURNING trace_id
),
ins_report AS (
  INSERT INTO chapter_report(book_id, chapter_id, run_id, report)
  SELECT i.book_id, i.chapter_id, i.run_id,
    jsonb_build_object(
      'reader_state', i.reader_state_json,
      'quality', i.quality_report_json,
      'length', length(i.chapter_text),
      'has_events_json', (i.events_raw <> '')
    )
  FROM inp i
  WHERE i.dry_run = false AND i.book_id IS NOT NULL AND i.chapter_id IS NOT NULL AND i.run_id IS NOT NULL
  ON CONFLICT(run_id) DO UPDATE SET report = EXCLUDED.report
  RETURNING report_id
),
ins_text_ver AS (
  INSERT INTO chapter_text_version(
    chapter_id, outline_version, source, content, note, meta
  )
  SELECT
    i.chapter_id,
    1,
    'workflow_draft',
    i.chapter_text,
    'draft_runner_v1',
    jsonb_build_object(
      'workflow_run_id', i.run_id::text,
      'phase', i.phase_txt,
      'intent', i.intent_txt,
      'events_raw', i.events_raw,
      'structure', i.structure_json,
      'final_tasks', i.final_tasks_json
    )
  FROM inp i
  WHERE i.dry_run = false AND i.chapter_id IS NOT NULL
  RETURNING text_ver_id
),
ins_usage AS (
  INSERT INTO asset_usage_log(
    book_id, chapter_id, text_ver_id, assets_injection, injected_material_ids, injected_template_ids,
    used_structure_template_ids, used_payoff_template_ids, used_combo_ids, used_combo_fingerprints,
    used_foreshadow_ids, ctx_tags, purpose
  )
  SELECT
    i.book_id,
    i.chapter_id,
    tv.text_ver_id,
    true,
    '{}'::uuid[],
    '{}'::uuid[],
    '{}'::uuid[],
    '{}'::uuid[],
    COALESCE((SELECT arr FROM used_combo_ids), '{}'::uuid[]),
    COALESCE((SELECT arr FROM used_combo_fps), '{}'::text[]),
    COALESCE((SELECT arr FROM used_foreshadow_ids), '{}'::uuid[]),
    array_remove(ARRAY[
      CASE WHEN i.phase_txt <> '' THEN i.phase_txt ELSE NULL END
    ]::text[], NULL),
    'draft'
  FROM inp i
  JOIN ins_text_ver tv ON true
  WHERE i.dry_run = false AND i.book_id IS NOT NULL AND i.chapter_id IS NOT NULL
  RETURNING usage_id
),
ins_sel_trace AS (
  INSERT INTO asset_selection_trace(
    book_id, chapter_id, text_ver_id, assets_injection, ctx_tags,
    selected_material_ids, selected_template_ids, trace
  )
  SELECT
    i.book_id,
    i.chapter_id,
    tv.text_ver_id,
    true,
    array_remove(ARRAY[
      CASE WHEN i.phase_txt <> '' THEN i.phase_txt ELSE NULL END
    ]::text[], NULL),
    '{}'::uuid[],
    '{}'::uuid[],
    jsonb_build_object(
      'version', 'v1',
      'structure', i.structure_json,
      'tasks', i.selection_tasks_json
    )
  FROM inp i
  JOIN ins_text_ver tv ON true
  WHERE i.dry_run = false AND i.book_id IS NOT NULL AND i.chapter_id IS NOT NULL
  RETURNING trace_id
),
after_ct AS (
  SELECT COUNT(*)::int AS c
  FROM chapter_draft cd
  JOIN inp i ON cd.chapter_id = i.chapter_id
)
SELECT jsonb_build_object(
  'commit_result', jsonb_build_object(
    'dry_run', (SELECT dry_run FROM inp),
    'draft_id', COALESCE((SELECT draft_id::text FROM ins_draft LIMIT 1), ''),
    'selected_draft_id', COALESCE((SELECT selected_draft_id::text FROM upsert_selected LIMIT 1), ''),
    'trace_id', COALESCE((SELECT trace_id::text FROM ins_trace LIMIT 1), ''),
    'report_id', COALESCE((SELECT report_id::text FROM ins_report LIMIT 1), ''),
    'text_ver_id', COALESCE((SELECT text_ver_id::text FROM ins_text_ver LIMIT 1), ''),
    'asset_usage_id', COALESCE((SELECT usage_id::text FROM ins_usage LIMIT 1), ''),
    'asset_selection_trace_id', COALESCE((SELECT trace_id::text FROM ins_sel_trace LIMIT 1), ''),
    'events_bound', EXISTS(SELECT 1 FROM upsert_events),
    'combo_plan_done_updates', COALESCE((SELECT COUNT(*)::int FROM upd_combo_done), 0),
    'combo_plan_done_item_ids', COALESCE((SELECT jsonb_agg(item_id) FROM upd_combo_done), '[]'::jsonb),
    'consumed_injection_updates', COALESCE((SELECT COUNT(*)::int FROM upd_injection_consumed), 0),
    'consumed_injection_ids', COALESCE((SELECT jsonb_agg(inj_id) FROM upd_injection_consumed), '[]'::jsonb),
    'chapter_id', COALESCE((SELECT chapter_id::text FROM inp), ''),
    'book_id', COALESCE((SELECT book_id::text FROM inp), '')
  ),
  'audit_before_state', jsonb_build_object('chapter_draft_count', COALESCE((SELECT c FROM before_ct), 0)),
  'audit_after_state', jsonb_build_object(
    'chapter_draft_count', COALESCE((SELECT c FROM after_ct), 0),
    'created_draft_id', COALESCE((SELECT draft_id::text FROM ins_draft LIMIT 1), ''),
    'created_trace_id', COALESCE((SELECT trace_id::text FROM ins_trace LIMIT 1), ''),
    'created_report_id', COALESCE((SELECT report_id::text FROM ins_report LIMIT 1), ''),
    'created_text_ver_id', COALESCE((SELECT text_ver_id::text FROM ins_text_ver LIMIT 1), ''),
    'created_asset_usage_id', COALESCE((SELECT usage_id::text FROM ins_usage LIMIT 1), ''),
    'created_asset_selection_trace_id', COALESCE((SELECT trace_id::text FROM ins_sel_trace LIMIT 1), '')
  ),
  'audit_diff', jsonb_build_array(
    jsonb_build_object(
      'op', 'set',
      'path', '/chapter_draft_count',
      'from', COALESCE((SELECT c FROM before_ct), 0),
      'to', COALESCE((SELECT c FROM after_ct), 0)
    )
  )
) AS data;
