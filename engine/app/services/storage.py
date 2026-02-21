from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

INIT_SQL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS schema_meta (
  version TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS profile (
  profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  note TEXT,
  active_version INTEGER NOT NULL DEFAULT 1,
  features JSONB NOT NULL DEFAULT '{}'::jsonb,
  dos TEXT[] NOT NULL DEFAULT '{}'::text[],
  donts TEXT[] NOT NULL DEFAULT '{}'::text[],
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE profile ADD COLUMN IF NOT EXISTS active_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE profile ADD COLUMN IF NOT EXISTS features JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE profile ADD COLUMN IF NOT EXISTS dos TEXT[] NOT NULL DEFAULT '{}'::text[];
ALTER TABLE profile ADD COLUMN IF NOT EXISTS donts TEXT[] NOT NULL DEFAULT '{}'::text[];
ALTER TABLE profile ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE TABLE IF NOT EXISTS profile_version (
  profile_id UUID NOT NULL REFERENCES profile(profile_id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  snapshot JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor TEXT NOT NULL DEFAULT 'desktop_user',
  action TEXT NOT NULL DEFAULT 'manual_edit',
  note TEXT NOT NULL DEFAULT '',
  parent_version INTEGER NULL,
  source_text_ver_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  PRIMARY KEY (profile_id, version)
);
CREATE INDEX IF NOT EXISTS idx_profile_version_time
ON profile_version(profile_id, created_at DESC);

CREATE TABLE IF NOT EXISTS book (
  book_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID REFERENCES profile(profile_id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  author TEXT,
  language TEXT NOT NULL DEFAULT 'zh',
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE book ADD COLUMN IF NOT EXISTS profile_id UUID;
CREATE INDEX IF NOT EXISTS idx_book_title_trgm ON book USING gin (title gin_trgm_ops);

CREATE TABLE IF NOT EXISTS book_profile_link (
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  profile_id UUID NOT NULL REFERENCES profile(profile_id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'experiment',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (book_id, profile_id)
);
CREATE INDEX IF NOT EXISTS idx_book_profile_role ON book_profile_link(book_id, role);

CREATE TABLE IF NOT EXISTS chapter (
  chapter_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  "order" INTEGER NOT NULL,
  arc_id TEXT,
  arc_index INTEGER,
  title TEXT NOT NULL DEFAULT '',
  text TEXT,
  intent JSONB NOT NULL DEFAULT '{}'::jsonb,
  intent_status TEXT NOT NULL DEFAULT 'suggested',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE chapter ADD COLUMN IF NOT EXISTS arc_id TEXT;
ALTER TABLE chapter ADD COLUMN IF NOT EXISTS arc_index INTEGER;
ALTER TABLE chapter ADD COLUMN IF NOT EXISTS intent JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE chapter ADD COLUMN IF NOT EXISTS intent_status TEXT NOT NULL DEFAULT 'suggested';

CREATE INDEX IF NOT EXISTS idx_chapter_book_order ON chapter(book_id, "order");
CREATE INDEX IF NOT EXISTS idx_chapter_arc ON chapter(book_id, arc_id, "order");
CREATE INDEX IF NOT EXISTS idx_chapter_title_trgm ON chapter USING gin (title gin_trgm_ops);

CREATE TABLE IF NOT EXISTS volume (
  volume_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  volume_no INTEGER NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  start_chapter_no INTEGER NOT NULL,
  end_chapter_no INTEGER NOT NULL,
  planned_chapters INTEGER NULL,
  note TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(book_id, volume_no)
);
CREATE INDEX IF NOT EXISTS idx_volume_book_range ON volume(book_id, start_chapter_no, end_chapter_no);

CREATE TABLE IF NOT EXISTS volume_plan (
  vol_plan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  volume_id UUID NOT NULL REFERENCES volume(volume_id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
  note TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(volume_id, version)
);
CREATE INDEX IF NOT EXISTS idx_volume_plan_active ON volume_plan(volume_id, status);

CREATE TABLE IF NOT EXISTS volume_plan_item (
  item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vol_plan_id UUID NOT NULL REFERENCES volume_plan(vol_plan_id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  ref_id UUID NULL,
  summary TEXT NOT NULL DEFAULT '',
  target_window TEXT NOT NULL,
  target_p_vol_min NUMERIC NOT NULL,
  target_p_vol_max NUMERIC NOT NULL,
  priority INTEGER NOT NULL DEFAULT 3,
  must_happen BOOLEAN NOT NULL DEFAULT true,
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE volume_plan_item
ADD COLUMN IF NOT EXISTS summary TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_vol_plan_item_plan ON volume_plan_item(vol_plan_id, kind, priority DESC);

CREATE TABLE IF NOT EXISTS volume_plan_audit (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  volume_id UUID NOT NULL REFERENCES volume(volume_id) ON DELETE CASCADE,
  from_version INTEGER NOT NULL,
  to_version INTEGER NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_volume_plan_audit_time ON volume_plan_audit(book_id, volume_id, created_at DESC);

CREATE TABLE IF NOT EXISTS source (
  source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  title TEXT,
  uri TEXT,
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_source_book_type ON source(book_id, type);
CREATE INDEX IF NOT EXISTS idx_source_title_trgm ON source USING gin (title gin_trgm_ops);

CREATE TABLE IF NOT EXISTS material_card (
  card_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NULL REFERENCES book(book_id) ON DELETE SET NULL,
  source_type TEXT NOT NULL DEFAULT 'manual',
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  tag TEXT NULL,
  importance INTEGER NOT NULL DEFAULT 3,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_material_book ON material_card(book_id);
CREATE INDEX IF NOT EXISTS idx_material_tag ON material_card(tag);
CREATE INDEX IF NOT EXISTS idx_material_title_trgm ON material_card USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_material_content_trgm ON material_card USING gin (content gin_trgm_ops);

CREATE TABLE IF NOT EXISTS material_embedding (
  card_id UUID PRIMARY KEY REFERENCES material_card(card_id) ON DELETE CASCADE,
  embedding vector(1024),
  model TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_material_embed_hnsw
ON material_embedding USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS splitbook (
  splitbook_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  author TEXT NULL,
  source_path TEXT NULL,
  note TEXT NULL,
  ingest_status TEXT NOT NULL DEFAULT 'new',
  embed_status TEXT NOT NULL DEFAULT 'pending',
  allow_guard BOOLEAN NOT NULL DEFAULT true,
  stats JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_splitbook_created ON splitbook(created_at DESC);

CREATE TABLE IF NOT EXISTS chapter_ref_inbox (
  ref_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NULL REFERENCES book(book_id) ON DELETE SET NULL,
  chapter_id UUID NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  source_type TEXT NOT NULL,
  source_id UUID NULL,
  title TEXT NOT NULL,
  tag TEXT NULL,
  ref_block TEXT NOT NULL,
  extracted_points JSONB NOT NULL DEFAULT '[]'::jsonb,
  status TEXT NOT NULL DEFAULT 'new',
  used_at TIMESTAMPTZ NULL,
  sort_key INTEGER NOT NULL DEFAULT 1000,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ref_inbox_chapter
ON chapter_ref_inbox(chapter_id, status, sort_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ref_inbox_book
ON chapter_ref_inbox(book_id);

CREATE TABLE IF NOT EXISTS chapter_version (
  chapter_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chapter_id UUID NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  kind TEXT NOT NULL DEFAULT 'draft',
  text TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(chapter_id, version)
);

CREATE TABLE IF NOT EXISTS chapter_text_version (
  text_ver_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chapter_id UUID NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  outline_version INTEGER NOT NULL,
  profile_id_used UUID NULL REFERENCES profile(profile_id) ON DELETE SET NULL,
  profile_version_used INTEGER NULL,
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  source TEXT NOT NULL DEFAULT 'draft',
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  note TEXT NULL
);
ALTER TABLE chapter_text_version ADD COLUMN IF NOT EXISTS profile_id_used UUID NULL REFERENCES profile(profile_id) ON DELETE SET NULL;
ALTER TABLE chapter_text_version ADD COLUMN IF NOT EXISTS profile_version_used INTEGER NULL;
ALTER TABLE chapter_text_version ADD COLUMN IF NOT EXISTS meta JSONB NOT NULL DEFAULT '{}'::jsonb;
CREATE INDEX IF NOT EXISTS idx_text_ver_chapter ON chapter_text_version(chapter_id, created_at DESC);

CREATE TABLE IF NOT EXISTS draft_run (
  draft_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chapter_id UUID NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  outline_version INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'running',
  params JSONB NOT NULL DEFAULT '{}'::jsonb,
  result JSONB NULL,
  error JSONB NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_draft_run_chapter ON draft_run(chapter_id, created_at DESC);

CREATE TABLE IF NOT EXISTS chapter_fact (
  fact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NULL REFERENCES book(book_id) ON DELETE SET NULL,
  chapter_id UUID NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  commit_txn_id UUID NULL,
  entity_type TEXT NOT NULL,
  entity_name TEXT NOT NULL,
  fact_type TEXT NOT NULL,
  fact TEXT NOT NULL,
  evidence_span TEXT NULL,
  confidence REAL NOT NULL DEFAULT 0.7,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_fact_chapter ON chapter_fact(chapter_id, entity_type, entity_name);
CREATE INDEX IF NOT EXISTS idx_fact_book ON chapter_fact(book_id, entity_type, entity_name);
ALTER TABLE chapter_fact
  DROP CONSTRAINT IF EXISTS uq_fact_commit;
ALTER TABLE chapter_fact
  ADD CONSTRAINT uq_fact_commit UNIQUE (commit_txn_id, entity_type, entity_name, fact_type, fact);

CREATE TABLE IF NOT EXISTS chapter_timeline_event (
  event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NULL REFERENCES book(book_id) ON DELETE SET NULL,
  chapter_id UUID NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  commit_txn_id UUID NULL,
  event_no INTEGER NOT NULL,
  time_hint TEXT NULL,
  location TEXT NULL,
  actors TEXT[] NOT NULL DEFAULT '{}'::text[],
  event TEXT NOT NULL,
  consequence TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(chapter_id, event_no)
);
CREATE INDEX IF NOT EXISTS idx_timeline_chapter ON chapter_timeline_event(chapter_id, event_no);
ALTER TABLE chapter_timeline_event
  DROP CONSTRAINT IF EXISTS chapter_timeline_event_chapter_id_event_no_key;
ALTER TABLE chapter_timeline_event
  DROP CONSTRAINT IF EXISTS uq_timeline_commit;
ALTER TABLE chapter_timeline_event
  ADD CONSTRAINT uq_timeline_commit UNIQUE (commit_txn_id, event_no);

CREATE TABLE IF NOT EXISTS character_growth_log (
  growth_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NULL REFERENCES book(book_id) ON DELETE SET NULL,
  chapter_id UUID NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  commit_txn_id UUID NULL,
  character_name TEXT NOT NULL,
  pressure TEXT NULL,
  cost TEXT NULL,
  gain TEXT NULL,
  change TEXT NULL,
  trigger_event_no INTEGER NULL,
  confidence REAL NOT NULL DEFAULT 0.7,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_growth_chapter ON character_growth_log(chapter_id, character_name);
ALTER TABLE character_growth_log
  DROP CONSTRAINT IF EXISTS uq_growth_commit;
ALTER TABLE character_growth_log
  ADD CONSTRAINT uq_growth_commit UNIQUE (commit_txn_id, character_name);

CREATE TABLE IF NOT EXISTS chapter_outline_detail (
  chapter_id UUID PRIMARY KEY REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  nodes JSONB NOT NULL DEFAULT '[]'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS outline (
  outline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  chapter_id UUID REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  scope TEXT NOT NULL,
  title TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  content JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(book_id, chapter_id, scope, version)
);
CREATE INDEX IF NOT EXISTS idx_outline_book_scope ON outline(book_id, scope);
CREATE INDEX IF NOT EXISTS idx_outline_chapter ON outline(chapter_id);

CREATE TABLE IF NOT EXISTS chunk (
  chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  source_id UUID REFERENCES source(source_id) ON DELETE SET NULL,
  chapter_id UUID NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  index_in_chapter INTEGER NOT NULL,
  text TEXT NOT NULL,
  fts tsvector,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE chunk ADD COLUMN IF NOT EXISTS source_id UUID;
ALTER TABLE chunk ADD COLUMN IF NOT EXISTS fts tsvector;

CREATE INDEX IF NOT EXISTS idx_chunk_book ON chunk(book_id);
CREATE INDEX IF NOT EXISTS idx_chunk_chapter ON chunk(chapter_id);
CREATE INDEX IF NOT EXISTS idx_chunk_fts ON chunk USING GIN (fts);

CREATE TABLE IF NOT EXISTS chunk_embedding (
  chunk_id UUID PRIMARY KEY REFERENCES chunk(chunk_id) ON DELETE CASCADE,
  embedding vector(1024) NOT NULL,
  model TEXT NOT NULL DEFAULT 'bge-m3:latest',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_embedding_vector_hnsw
ON chunk_embedding USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS jobs (
  job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID REFERENCES book(book_id) ON DELETE SET NULL,
  chapter_id UUID REFERENCES chapter(chapter_id) ON DELETE SET NULL,
  job_type TEXT NOT NULL DEFAULT 'GENERIC',
  capability_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  stage TEXT NOT NULL DEFAULT 'QUEUED',
  progress_value REAL NOT NULL DEFAULT 0.0,
  progress JSONB NOT NULL DEFAULT '{}'::jsonb,
  run_id UUID,
  result JSONB NOT NULL DEFAULT '{}'::jsonb,
  logs TEXT[] NOT NULL DEFAULT '{}'::text[],
  error JSONB,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  request_id TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS book_id UUID;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS chapter_id UUID;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS job_type TEXT NOT NULL DEFAULT 'GENERIC';
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS stage TEXT NOT NULL DEFAULT 'QUEUED';
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS progress_value REAL NOT NULL DEFAULT 0.0;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS result JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS logs TEXT[] NOT NULL DEFAULT '{}'::text[];
CREATE INDEX IF NOT EXISTS idx_job_book_created ON jobs(book_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_status_created ON jobs(status, created_at DESC);

CREATE TABLE IF NOT EXISTS runs (
  run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  capability_id TEXT NOT NULL,
  status TEXT NOT NULL,
  input JSONB NOT NULL DEFAULT '{}'::jsonb,
  output JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workflow_run (
  run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workflow_id TEXT NOT NULL,
  workflow_version INTEGER NOT NULL,
  book_id UUID NULL REFERENCES book(book_id) ON DELETE SET NULL,
  chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
  idempotency_key TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'running',
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at TIMESTAMPTZ NULL,
  error JSONB NULL,
  ctx_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
  meta JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_workflow_run_idem
ON workflow_run(workflow_id, idempotency_key);
CREATE INDEX IF NOT EXISTS idx_workflow_run_time
ON workflow_run(workflow_id, started_at DESC);

CREATE TABLE IF NOT EXISTS workflow_step (
  step_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID NOT NULL REFERENCES workflow_run(run_id) ON DELETE CASCADE,
  node_id TEXT NOT NULL,
  node_type TEXT NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'running',
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at TIMESTAMPTZ NULL,
  input JSONB NOT NULL DEFAULT '{}'::jsonb,
  output JSONB NOT NULL DEFAULT '{}'::jsonb,
  metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  error JSONB NULL
);
CREATE INDEX IF NOT EXISTS idx_workflow_step_run ON workflow_step(run_id, started_at);

CREATE TABLE IF NOT EXISTS state_apply_audit (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
  run_id UUID NULL REFERENCES workflow_run(run_id) ON DELETE SET NULL,
  action_type TEXT NOT NULL,
  before_state JSONB NOT NULL DEFAULT '{}'::jsonb,
  after_state JSONB NOT NULL DEFAULT '{}'::jsonb,
  diff JSONB NOT NULL DEFAULT '{}'::jsonb,
  reason TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_state_apply_audit_book_time
ON state_apply_audit(book_id, created_at DESC);

CREATE TABLE IF NOT EXISTS ingest_runs (
  ingest_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'queued',
  checkpoint JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS skill_run (
  skill_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  skill_name TEXT NOT NULL,
  schema_ver INTEGER NOT NULL DEFAULT 1,
  output JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_skill_run_name_trgm ON skill_run USING gin (skill_name gin_trgm_ops);

CREATE TABLE IF NOT EXISTS character (
  character_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  alias TEXT[] NOT NULL DEFAULT '{}'::text[],
  role TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(book_id, name)
);

CREATE TABLE IF NOT EXISTS character_version (
  character_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  character_id UUID NOT NULL REFERENCES character(character_id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  card JSONB NOT NULL,
  source_chunk_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(character_id, version)
);

CREATE TABLE IF NOT EXISTS timeline_event (
  event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  chapter_id UUID REFERENCES chapter(chapter_id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  causality JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_chunk_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS world_fact (
  fact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  key TEXT NOT NULL,
  value JSONB NOT NULL,
  confidence REAL NOT NULL DEFAULT 0.7,
  source_chunk_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(book_id, key)
);

CREATE TABLE IF NOT EXISTS plot_hook (
  hook_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  chapter_id UUID REFERENCES chapter(chapter_id) ON DELETE SET NULL,
  kind TEXT NOT NULL,
  content TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_chunk_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS structure_template (
  template_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID NOT NULL REFERENCES profile(profile_id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  level TEXT NOT NULL,
  tags TEXT[] NOT NULL DEFAULT '{}'::text[],
  schema_ver INTEGER NOT NULL DEFAULT 1,
  graph JSONB NOT NULL,
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE structure_template ADD COLUMN IF NOT EXISTS st_type TEXT NOT NULL DEFAULT 'legacy';
ALTER TABLE structure_template ADD COLUMN IF NOT EXISTS subtype TEXT NOT NULL DEFAULT '';
ALTER TABLE structure_template ADD COLUMN IF NOT EXISTS pattern JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE structure_template ADD COLUMN IF NOT EXISTS slots TEXT[] NOT NULL DEFAULT '{}'::text[];
ALTER TABLE structure_template ADD COLUMN IF NOT EXISTS risk_score NUMERIC NOT NULL DEFAULT 0;
ALTER TABLE structure_template ADD COLUMN IF NOT EXISTS policy TEXT NOT NULL DEFAULT 'normal';
ALTER TABLE structure_template ADD COLUMN IF NOT EXISTS fingerprint TEXT NULL;
ALTER TABLE structure_template ADD COLUMN IF NOT EXISTS source_meta JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE structure_template ADD COLUMN IF NOT EXISTS source_book_hash TEXT NULL;
ALTER TABLE structure_template ADD COLUMN IF NOT EXISTS rotation_group TEXT NULL;
ALTER TABLE structure_template ADD COLUMN IF NOT EXISTS last_used_volume_no INTEGER NULL;
CREATE INDEX IF NOT EXISTS idx_template_profile_level ON structure_template(profile_id, level);
CREATE INDEX IF NOT EXISTS idx_template_tags_gin ON structure_template USING gin(tags);
CREATE INDEX IF NOT EXISTS idx_structure_template_type ON structure_template(st_type, subtype);
CREATE INDEX IF NOT EXISTS idx_structure_template_policy ON structure_template(policy);
CREATE INDEX IF NOT EXISTS idx_structure_template_fp ON structure_template(fingerprint);

CREATE TABLE IF NOT EXISTS template_usage_log (
  usage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  template_id UUID NOT NULL REFERENCES structure_template(template_id) ON DELETE CASCADE,
  book_id UUID REFERENCES book(book_id) ON DELETE SET NULL,
  chapter_id UUID REFERENCES chapter(chapter_id) ON DELETE SET NULL,
  usage_type TEXT NOT NULL,
  feedback JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_usage_template ON template_usage_log(template_id);

CREATE TABLE IF NOT EXISTS structure_template_source (
  template_source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  template_id UUID NOT NULL REFERENCES structure_template(template_id) ON DELETE CASCADE,
  source_book_id UUID REFERENCES book(book_id) ON DELETE SET NULL,
  source_chunk_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
  note TEXT
);

CREATE TABLE IF NOT EXISTS template_asset (
  asset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_type TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  tags TEXT[] NOT NULL DEFAULT '{}'::text[],
  source_splitbook_id UUID NULL,
  source_span JSONB NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_template_asset_type ON template_asset(asset_type);
CREATE INDEX IF NOT EXISTS idx_template_asset_tags ON template_asset USING gin(tags);
CREATE INDEX IF NOT EXISTS idx_template_asset_name_trgm ON template_asset USING gin(name gin_trgm_ops);

CREATE TABLE IF NOT EXISTS app_config (
  key TEXT PRIMARY KEY,
  value JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_settings (
  singleton_id INTEGER PRIMARY KEY DEFAULT 1 CHECK (singleton_id = 1),
  settings JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO app_settings(singleton_id, settings)
VALUES (1, '{}'::jsonb)
ON CONFLICT (singleton_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS book_settings (
  book_id UUID PRIMARY KEY REFERENCES book(book_id) ON DELETE CASCADE,
  settings JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chapter_settings (
  chapter_id UUID PRIMARY KEY REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  settings JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS settings_preset (
  preset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT '',
  settings JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS settings_audit_log (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor TEXT NOT NULL DEFAULT 'desktop_user',
  action TEXT NOT NULL,
  scope TEXT NOT NULL,
  scope_id UUID NULL,
  preset_id UUID NULL REFERENCES settings_preset(preset_id) ON DELETE SET NULL,
  mode TEXT NULL,
  before_settings JSONB NULL,
  after_settings JSONB NULL,
  note TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_settings_audit_time ON settings_audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_settings_audit_scope ON settings_audit_log(scope, scope_id);

CREATE TABLE IF NOT EXISTS agent_action_audit_log (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
  proposal_id TEXT NOT NULL DEFAULT '',
  action_type TEXT NOT NULL,
  action_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  before_state JSONB NULL,
  after_state JSONB NULL,
  status TEXT NOT NULL DEFAULT 'applied',
  note TEXT NOT NULL DEFAULT '',
  rollback_of UUID NULL REFERENCES agent_action_audit_log(audit_id) ON DELETE SET NULL,
  rolled_back_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_action_audit_book_time
ON agent_action_audit_log(book_id, created_at DESC);

CREATE TABLE IF NOT EXISTS chapter_tension_metrics (
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  chapter_id UUID NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  chapter_no INTEGER NOT NULL,
  chapter_version_id UUID NULL,
  eval_skill_run_id UUID NOT NULL REFERENCES skill_run(skill_run_id) ON DELETE CASCADE,
  scores JSONB NOT NULL,
  tension_curve REAL[] NOT NULL,
  issues_count INTEGER NOT NULL DEFAULT 0,
  mechanics_used TEXT[] NOT NULL DEFAULT '{}'::text[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (book_id, chapter_id, eval_skill_run_id)
);
CREATE INDEX IF NOT EXISTS idx_ctm_book_chapter_no ON chapter_tension_metrics(book_id, chapter_no);

CREATE TABLE IF NOT EXISTS arc_target (
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  arc_id TEXT NOT NULL,
  target_shape TEXT NOT NULL,
  target_points REAL[] NOT NULL,
  weights JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (book_id, arc_id)
);
CREATE INDEX IF NOT EXISTS idx_arc_target_book ON arc_target(book_id, arc_id);

CREATE TABLE IF NOT EXISTS template_variant (
  variant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  base_template_id UUID NULL REFERENCES structure_template(template_id) ON DELETE SET NULL,
  unique_key TEXT,
  name TEXT NOT NULL,
  scope JSONB NOT NULL DEFAULT '{}'::jsonb,
  recipe JSONB NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT false,
  weight REAL NOT NULL DEFAULT 0.1,
  stats JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_template_variant_base ON template_variant(base_template_id, enabled);
CREATE UNIQUE INDEX IF NOT EXISTS uq_template_variant_key ON template_variant(unique_key);

CREATE TABLE IF NOT EXISTS repair_effect_sample (
  sample_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  arc_id TEXT NULL,
  chapter_no INTEGER NOT NULL,
  before_eval_run_id UUID NOT NULL REFERENCES skill_run(skill_run_id) ON DELETE CASCADE,
  after_eval_run_id UUID NOT NULL REFERENCES skill_run(skill_run_id) ON DELETE CASCADE,
  applied_mechanics TEXT[] NOT NULL,
  delta JSONB NOT NULL,
  context JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sample_context ON repair_effect_sample((context->>'arc_shape'));

CREATE TABLE IF NOT EXISTS repair_txn (
  repair_txn_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  chapter_id UUID NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  before_eval_run_id UUID NULL REFERENCES skill_run(skill_run_id) ON DELETE SET NULL,
  after_eval_run_id UUID NULL REFERENCES skill_run(skill_run_id) ON DELETE SET NULL,
  plan_skill_run_id UUID NULL REFERENCES skill_run(skill_run_id) ON DELETE SET NULL,
  applied_outline_version INTEGER NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_repair_txn_chapter ON repair_txn(chapter_id, created_at DESC);

CREATE TABLE IF NOT EXISTS report (
  report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  profile_id_used UUID NULL REFERENCES profile(profile_id) ON DELETE SET NULL,
  profile_version_used INTEGER NULL,
  report_type TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  html TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE report ADD COLUMN IF NOT EXISTS profile_id_used UUID NULL REFERENCES profile(profile_id) ON DELETE SET NULL;
ALTER TABLE report ADD COLUMN IF NOT EXISTS profile_version_used INTEGER NULL;
CREATE INDEX IF NOT EXISTS idx_report_book_time ON report(book_id, created_at DESC);

CREATE TABLE IF NOT EXISTS ab_batch_run (
  batch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  chapter_id UUID NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'running',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ NULL,
  note TEXT NOT NULL DEFAULT '',
  settings_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb
);
ALTER TABLE ab_batch_run
ADD COLUMN IF NOT EXISTS score_cfg JSONB NOT NULL DEFAULT jsonb_build_object('penalty', 0.8);
ALTER TABLE ab_batch_run
ADD COLUMN IF NOT EXISTS winner_bundle_id UUID NULL;
ALTER TABLE ab_batch_run
ADD COLUMN IF NOT EXISTS intent_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE ab_batch_run
ADD COLUMN IF NOT EXISTS volume_id UUID NULL REFERENCES volume(volume_id) ON DELETE SET NULL;
ALTER TABLE ab_batch_run
ADD COLUMN IF NOT EXISTS volume_plan_id UUID NULL;
ALTER TABLE ab_batch_run
ADD COLUMN IF NOT EXISTS volume_plan_version INTEGER NULL;
CREATE INDEX IF NOT EXISTS idx_ab_batch_run_time ON ab_batch_run(created_at DESC);

CREATE TABLE IF NOT EXISTS ab_batch_item (
  batch_id UUID NOT NULL REFERENCES ab_batch_run(batch_id) ON DELETE CASCADE,
  profile_id UUID NOT NULL REFERENCES profile(profile_id) ON DELETE CASCADE,
  variant TEXT NOT NULL DEFAULT 'exp',
  assets_injection BOOLEAN NOT NULL DEFAULT true,
  profile_version INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  text_ver_id UUID NULL REFERENCES chapter_text_version(text_ver_id) ON DELETE SET NULL,
  report_id UUID NULL REFERENCES report(report_id) ON DELETE SET NULL,
  eval_overall NUMERIC NULL,
  simguard_max NUMERIC NULL,
  score NUMERIC NULL,
  error TEXT NOT NULL DEFAULT '',
  started_at TIMESTAMPTZ NULL,
  finished_at TIMESTAMPTZ NULL,
  PRIMARY KEY(batch_id, profile_id, variant)
);
ALTER TABLE ab_batch_item ADD COLUMN IF NOT EXISTS variant TEXT NOT NULL DEFAULT 'exp';
ALTER TABLE ab_batch_item ADD COLUMN IF NOT EXISTS assets_injection BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE ab_batch_item
ADD COLUMN IF NOT EXISTS score NUMERIC NULL;
CREATE INDEX IF NOT EXISTS idx_ab_batch_item_status ON ab_batch_item(batch_id, status);

CREATE TABLE IF NOT EXISTS book_profile_audit_log (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  action TEXT NOT NULL,
  batch_id UUID NULL REFERENCES ab_batch_run(batch_id) ON DELETE SET NULL,
  old_main_profile_id UUID NULL REFERENCES profile(profile_id) ON DELETE SET NULL,
  new_main_profile_id UUID NULL REFERENCES profile(profile_id) ON DELETE SET NULL,
  score NUMERIC NULL,
  note TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_book_profile_audit_time ON book_profile_audit_log(book_id, created_at DESC);

ALTER TABLE material_card
ADD COLUMN IF NOT EXISTS source_text_ver_id UUID NULL REFERENCES chapter_text_version(text_ver_id) ON DELETE SET NULL;
ALTER TABLE material_card
ADD COLUMN IF NOT EXISTS source_batch_id UUID NULL REFERENCES ab_batch_run(batch_id) ON DELETE SET NULL;
ALTER TABLE material_card
ADD COLUMN IF NOT EXISTS profile_id_used UUID NULL REFERENCES profile(profile_id) ON DELETE SET NULL;
ALTER TABLE material_card
ADD COLUMN IF NOT EXISTS profile_version_used INTEGER NULL;
ALTER TABLE material_card
ADD COLUMN IF NOT EXISTS risk_score NUMERIC NULL;
ALTER TABLE material_card
ADD COLUMN IF NOT EXISTS extract_meta JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE material_card
ADD COLUMN IF NOT EXISTS policy TEXT NOT NULL DEFAULT 'normal';
ALTER TABLE material_card
ADD COLUMN IF NOT EXISTS fingerprint TEXT NULL;
CREATE INDEX IF NOT EXISTS idx_material_policy ON material_card(book_id, policy);
CREATE INDEX IF NOT EXISTS idx_material_fp ON material_card(book_id, fingerprint);

CREATE TABLE IF NOT EXISTS prompt_template (
  template_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  purpose TEXT NOT NULL,
  template TEXT NOT NULL,
  slots JSONB NOT NULL DEFAULT '[]'::jsonb,
  tags TEXT[] NOT NULL DEFAULT '{}'::text[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_text_ver_id UUID NULL REFERENCES chapter_text_version(text_ver_id) ON DELETE SET NULL,
  source_batch_id UUID NULL REFERENCES ab_batch_run(batch_id) ON DELETE SET NULL,
  profile_id_used UUID NULL REFERENCES profile(profile_id) ON DELETE SET NULL,
  profile_version_used INTEGER NULL,
  risk_score NUMERIC NULL,
  extract_meta JSONB NOT NULL DEFAULT '{}'::jsonb
);
ALTER TABLE prompt_template
ADD COLUMN IF NOT EXISTS policy TEXT NOT NULL DEFAULT 'normal';
ALTER TABLE prompt_template
ADD COLUMN IF NOT EXISTS fingerprint TEXT NULL;
CREATE INDEX IF NOT EXISTS idx_prompt_template_purpose ON prompt_template(purpose);
CREATE INDEX IF NOT EXISTS idx_template_policy ON prompt_template(policy);
CREATE INDEX IF NOT EXISTS idx_template_fp ON prompt_template(fingerprint);

CREATE TABLE IF NOT EXISTS extraction_run (
  run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  kind TEXT NOT NULL,
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
  text_ver_id UUID NOT NULL REFERENCES chapter_text_version(text_ver_id) ON DELETE CASCADE,
  batch_id UUID NULL REFERENCES ab_batch_run(batch_id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'running',
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  result_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  error TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ NULL
);
CREATE INDEX IF NOT EXISTS idx_extraction_run_time ON extraction_run(book_id, created_at DESC);

CREATE TABLE IF NOT EXISTS asset_bundle (
  bundle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
  batch_id UUID NULL REFERENCES ab_batch_run(batch_id) ON DELETE SET NULL,
  text_ver_id UUID NOT NULL REFERENCES chapter_text_version(text_ver_id) ON DELETE CASCADE,
  kind TEXT NOT NULL DEFAULT 'winner_assets',
  status TEXT NOT NULL DEFAULT 'ready',
  risk_score NUMERIC NULL,
  note TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_asset_bundle_book_time ON asset_bundle(book_id, created_at DESC);

CREATE TABLE IF NOT EXISTS asset_bundle_item (
  bundle_id UUID NOT NULL REFERENCES asset_bundle(bundle_id) ON DELETE CASCADE,
  item_type TEXT NOT NULL,
  item_id UUID NOT NULL,
  PRIMARY KEY(bundle_id, item_type, item_id)
);
CREATE INDEX IF NOT EXISTS idx_asset_bundle_item_bundle ON asset_bundle_item(bundle_id);

CREATE TABLE IF NOT EXISTS book_default_assets (
  book_id UUID PRIMARY KEY REFERENCES book(book_id) ON DELETE CASCADE,
  bundle_id UUID NOT NULL REFERENCES asset_bundle(bundle_id) ON DELETE RESTRICT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS asset_usage_log (
  usage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
  text_ver_id UUID NOT NULL REFERENCES chapter_text_version(text_ver_id) ON DELETE CASCADE,
  batch_id UUID NULL REFERENCES ab_batch_run(batch_id) ON DELETE SET NULL,
  profile_id_used UUID NULL REFERENCES profile(profile_id) ON DELETE SET NULL,
  profile_version_used INTEGER NULL,
  assets_injection BOOLEAN NOT NULL,
  injected_bundle_id UUID NULL REFERENCES asset_bundle(bundle_id) ON DELETE SET NULL,
  injected_material_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
  injected_template_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
  used_structure_template_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
  used_payoff_template_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
  used_combo_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
  used_combo_fingerprints TEXT[] NOT NULL DEFAULT '{}'::text[],
  used_foreshadow_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
  ctx_tags TEXT[] NOT NULL DEFAULT '{}'::text[],
  purpose TEXT NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE asset_usage_log
ADD COLUMN IF NOT EXISTS used_foreshadow_ids UUID[] NOT NULL DEFAULT '{}'::uuid[];
ALTER TABLE asset_usage_log
ADD COLUMN IF NOT EXISTS used_structure_template_ids UUID[] NOT NULL DEFAULT '{}'::uuid[];
ALTER TABLE asset_usage_log
ADD COLUMN IF NOT EXISTS used_payoff_template_ids UUID[] NOT NULL DEFAULT '{}'::uuid[];
ALTER TABLE asset_usage_log
ADD COLUMN IF NOT EXISTS used_combo_ids UUID[] NOT NULL DEFAULT '{}'::uuid[];
ALTER TABLE asset_usage_log
ADD COLUMN IF NOT EXISTS used_combo_fingerprints TEXT[] NOT NULL DEFAULT '{}'::text[];
CREATE INDEX IF NOT EXISTS idx_asset_usage_batch ON asset_usage_log(batch_id);
CREATE INDEX IF NOT EXISTS idx_asset_usage_book_time ON asset_usage_log(book_id, created_at DESC);

CREATE TABLE IF NOT EXISTS structure_combo (
  combo_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NULL REFERENCES book(book_id) ON DELETE SET NULL,
  combo_type TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  pattern JSONB NOT NULL DEFAULT '{}'::jsonb,
  tags TEXT[] NOT NULL DEFAULT '{}'::text[],
  risk_score NUMERIC NOT NULL DEFAULT 0,
  policy TEXT NOT NULL DEFAULT 'normal',
  rotation_group TEXT NULL,
  last_used_volume_no INTEGER NULL,
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(book_id, fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_structure_combo_type ON structure_combo(combo_type);
CREATE INDEX IF NOT EXISTS idx_structure_combo_fp ON structure_combo(fingerprint);
CREATE INDEX IF NOT EXISTS idx_structure_combo_policy ON structure_combo(policy);

CREATE TABLE IF NOT EXISTS asset_score_stat (
  item_type TEXT NOT NULL,
  item_id UUID NOT NULL,
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  uses INTEGER NOT NULL DEFAULT 0,
  wins INTEGER NOT NULL DEFAULT 0,
  losses INTEGER NOT NULL DEFAULT 0,
  avg_delta NUMERIC NOT NULL DEFAULT 0,
  last_delta NUMERIC NULL,
  weight NUMERIC NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (item_type, item_id, book_id)
);
CREATE INDEX IF NOT EXISTS idx_asset_stat_book_weight ON asset_score_stat(book_id, weight DESC);

CREATE TABLE IF NOT EXISTS asset_selection_trace (
  trace_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
  text_ver_id UUID NOT NULL REFERENCES chapter_text_version(text_ver_id) ON DELETE CASCADE,
  batch_id UUID NULL REFERENCES ab_batch_run(batch_id) ON DELETE SET NULL,
  injected_bundle_id UUID NULL REFERENCES asset_bundle(bundle_id) ON DELETE SET NULL,
  assets_injection BOOLEAN NOT NULL,
  ctx_tags TEXT[] NOT NULL DEFAULT '{}'::text[],
  selected_material_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
  selected_template_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
  trace JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_asset_trace_book_time ON asset_selection_trace(book_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_asset_trace_textver ON asset_selection_trace(text_ver_id);

CREATE TABLE IF NOT EXISTS asset_policy_proposal (
  proposal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  item_type TEXT NOT NULL,
  item_id UUID NOT NULL,
  proposed_policy TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  reason TEXT NOT NULL DEFAULT '',
  evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  decided_at TIMESTAMPTZ NULL,
  decided_note TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_asset_policy_proposal_pending
ON asset_policy_proposal(book_id, item_type, item_id, proposed_policy, status);
CREATE INDEX IF NOT EXISTS idx_policy_proposal_book_status
ON asset_policy_proposal(book_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS asset_policy_audit_log (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  item_type TEXT NOT NULL,
  item_id UUID NOT NULL,
  from_policy TEXT NOT NULL,
  to_policy TEXT NOT NULL,
  proposal_id UUID NULL REFERENCES asset_policy_proposal(proposal_id) ON DELETE SET NULL,
  note TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_asset_policy_audit_book_time
ON asset_policy_audit_log(book_id, created_at DESC);

CREATE TABLE IF NOT EXISTS foreshadow (
  foreshadow_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  volume_id UUID NULL REFERENCES volume(volume_id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  type TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT 'volume',
  priority INTEGER NOT NULL DEFAULT 3,
  status TEXT NOT NULL DEFAULT 'seeded',
  created_chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
  planned_payoff_chapter_id UUID NULL REFERENCES chapter(chapter_id) ON DELETE SET NULL,
  question TEXT NOT NULL DEFAULT '',
  expected_payoff TEXT NOT NULL DEFAULT '',
  constraints TEXT[] NOT NULL DEFAULT '{}'::text[],
  tags TEXT[] NOT NULL DEFAULT '{}'::text[],
  risk_score NUMERIC NULL,
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_foreshadow_book_status ON foreshadow(book_id, status);
CREATE INDEX IF NOT EXISTS idx_foreshadow_volume ON foreshadow(volume_id);

CREATE TABLE IF NOT EXISTS foreshadow_event (
  event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  foreshadow_id UUID NOT NULL REFERENCES foreshadow(foreshadow_id) ON DELETE CASCADE,
  chapter_id UUID NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  intensity INTEGER NOT NULL DEFAULT 1,
  excerpt_safe TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_foreshadow_event_foreshadow_time
ON foreshadow_event(foreshadow_id, created_at DESC);

CREATE TABLE IF NOT EXISTS payoff_template (
  template_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type TEXT NOT NULL,
  applicable_foreshadow_type TEXT[] NOT NULL DEFAULT '{}'::text[],
  structure_pattern TEXT NOT NULL,
  rewrite_instruction TEXT NOT NULL,
  intensity_level INTEGER NOT NULL DEFAULT 2,
  risk_score NUMERIC NULL,
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_payoff_template_type ON payoff_template(type, intensity_level);
CREATE UNIQUE INDEX IF NOT EXISTS uq_payoff_template_type_level ON payoff_template(type, intensity_level);

CREATE TABLE IF NOT EXISTS growth_milestone (
  milestone_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id UUID NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  character_name TEXT NOT NULL DEFAULT '主角',
  milestone_no INTEGER NOT NULL DEFAULT 1,
  title TEXT NOT NULL,
  stage TEXT NOT NULL DEFAULT 'pressure',
  priority INTEGER NOT NULL DEFAULT 3,
  planned_scope TEXT NOT NULL DEFAULT 'volume',
  planned_chapter_no INTEGER NULL,
  planned_volume_id UUID NULL REFERENCES volume(volume_id) ON DELETE SET NULL,
  trigger TEXT NOT NULL DEFAULT '',
  cost TEXT NOT NULL DEFAULT '',
  choice_text TEXT NOT NULL DEFAULT '',
  new_belief TEXT NOT NULL DEFAULT '',
  bind_foreshadow_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
  payoff_template_type TEXT NULL,
  status TEXT NOT NULL DEFAULT 'planned',
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(book_id, character_name, milestone_no)
);
CREATE INDEX IF NOT EXISTS idx_growth_milestone_book_status ON growth_milestone(book_id, status);

ALTER TABLE asset_usage_log
ADD COLUMN IF NOT EXISTS growth_milestone_id UUID NULL;
ALTER TABLE asset_usage_log
ADD COLUMN IF NOT EXISTS growth_action TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_asset_usage_growth ON asset_usage_log(book_id, growth_milestone_id);

CREATE TABLE IF NOT EXISTS tag_dictionary (
  tag TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  is_enabled BOOLEAN NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS idx_tag_dictionary_category ON tag_dictionary(category, is_enabled);

CREATE TABLE IF NOT EXISTS tag_alias (
  from_tag TEXT PRIMARY KEY,
  to_tag TEXT NOT NULL REFERENCES tag_dictionary(tag)
);
CREATE INDEX IF NOT EXISTS idx_tag_alias_to_tag ON tag_alias(to_tag);
"""


async def run_init_sql(session: AsyncSession) -> None:
    for statement in [s.strip() for s in INIT_SQL.split(";") if s.strip()]:
        await session.execute(text(statement))
    await session.execute(
        text(
            """
            INSERT INTO app_config(key, value)
            VALUES
            ('ollama', CAST(:ollama AS jsonb)),
            ('similarity', CAST(:similarity AS jsonb)),
            ('limits', CAST(:limits AS jsonb))
            ON CONFLICT (key) DO NOTHING
            """
        ),
        {
            "ollama": json.dumps(
                {"base_url": "http://127.0.0.1:11434", "llm_model": "qwen2.5:7b", "embedding_model": "bge-m3:latest"}
            ),
            "similarity": json.dumps({"vec_high": 0.86, "vec_mid": 0.80, "ng_high": 0.20, "ng_mid": 0.12}),
            "limits": json.dumps({"llm_concurrency": 1, "embed_concurrency": 2, "max_insert_nodes": 4}),
        },
    )
    default_tags: list[tuple[str, str, str]] = [
        ("draft", "task", "draft generation"),
        ("rewrite", "task", "rewrite generation"),
        ("scene_start", "task", "scene start section"),
        ("scene_mid", "task", "scene middle section"),
        ("scene_end", "task", "scene end section"),
        ("fast_paced", "pacing", "fast pacing"),
        ("mid_paced", "pacing", "medium pacing"),
        ("slow_burn", "pacing", "slow burn pacing"),
        ("high_conflict", "pacing", "high conflict"),
        ("low_conflict", "pacing", "low conflict"),
        ("dialog_heavy", "narrative", "dialogue focused"),
        ("action_heavy", "narrative", "action focused"),
        ("introspection_heavy", "narrative", "introspection focused"),
        ("cliffhanger_end", "goal", "chapter ends with cliffhanger"),
        ("soft_end", "goal", "chapter ends softly"),
        ("character_growth", "goal", "character growth"),
        ("relationship_shift", "goal", "relationship shift"),
        ("worldbuilding", "goal", "worldbuilding focus"),
        ("info_reveal", "goal", "information reveal"),
        ("mystery_build", "goal", "mystery build up"),
        ("eval_on", "runtime", "eval enabled for run"),
        ("simguard_on", "runtime", "simguard enabled for run"),
        ("phase_setup", "phase", "setup phase"),
        ("phase_midgame", "phase", "midgame phase"),
        ("phase_climax", "phase", "climax phase"),
        ("phase_closure", "phase", "closure phase"),
        ("conflict_low", "curve", "conflict curve low"),
        ("conflict_mid", "curve", "conflict curve mid"),
        ("conflict_high", "curve", "conflict curve high"),
        ("reveal_low", "curve", "reveal curve low"),
        ("reveal_mid", "curve", "reveal curve mid"),
        ("reveal_high", "curve", "reveal curve high"),
        ("tension_low", "curve", "tension curve low"),
        ("tension_mid", "curve", "tension curve mid"),
        ("tension_high", "curve", "tension curve high"),
        ("growth_low", "curve", "growth curve low"),
        ("growth_mid", "curve", "growth curve mid"),
        ("growth_high", "curve", "growth curve high"),
        ("closure_low", "curve", "closure curve low"),
        ("closure_mid", "curve", "closure curve mid"),
        ("closure_high", "curve", "closure curve high"),
        ("xuanhuan", "genre", "genre"),
        ("xianxia", "genre", "genre"),
        ("dushi", "genre", "genre"),
        ("kehuan", "genre", "genre"),
        ("lishi", "genre", "genre"),
        ("youxi", "genre", "genre"),
        ("wuxia", "genre", "genre"),
        ("lingyi", "genre", "genre"),
    ]
    for tag, category, desc in default_tags:
        await session.execute(
            text(
                """
                INSERT INTO tag_dictionary(tag, category, description, is_enabled)
                VALUES (:tag, :category, :description, true)
                ON CONFLICT (tag) DO NOTHING
                """
            ),
            {"tag": tag, "category": category, "description": desc},
        )
    default_aliases: list[tuple[str, str]] = [
        ("fast", "fast_paced"),
        ("mid", "mid_paced"),
        ("slow", "slow_burn"),
        ("high", "high_conflict"),
        ("low", "low_conflict"),
        ("dialog", "dialog_heavy"),
        ("action", "action_heavy"),
        ("introspection", "introspection_heavy"),
        ("cliffhanger", "cliffhanger_end"),
        ("soft", "soft_end"),
    ]
    for from_tag, to_tag in default_aliases:
        await session.execute(
            text(
                """
                INSERT INTO tag_alias(from_tag, to_tag)
                VALUES (:from_tag, :to_tag)
                ON CONFLICT (from_tag) DO NOTHING
                """
            ),
            {"from_tag": from_tag, "to_tag": to_tag},
        )
    default_payoff_templates = [
        (
            "reversal",
            ["mystery", "secret", "hidden_identity"],
            "Reveal a truth that reframes earlier clues without breaking logic.",
            "先呈现读者预期，再给出反转证据，最后回扣旧线索一致性。",
            3,
        ),
        (
            "cost",
            ["threat", "artifact", "power_upgrade", "promise"],
            "兑现代价并让角色承担后果，推动下一阶段冲突。",
            "明确展示失去/牺牲，不要用旁白跳过代价。",
            3,
        ),
        (
            "misinterpretation",
            ["relationship", "betrayal", "secret"],
            "纠正读者与角色的误读，揭示真实动机。",
            "用一个关键事实改写误会来源，并保留情绪余波。",
            2,
        ),
        (
            "emotional",
            ["character_growth", "promise", "relationship"],
            "通过对照与选择完成情绪兑现而非信息反转。",
            "让角色明确做出选择并体现新信念。",
            2,
        ),
        (
            "parallel",
            ["mystery", "threat", "relationship"],
            "双线索并行回收，形成镜像或交叉增幅。",
            "主线回收时带出次线回收，避免互相抢戏。",
            3,
        ),
    ]
    for p_type, fs_types, pattern, instruction, intensity in default_payoff_templates:
        await session.execute(
            text(
                """
                INSERT INTO payoff_template(type, applicable_foreshadow_type, structure_pattern, rewrite_instruction, intensity_level, meta)
                VALUES (:type, CAST(:applicable_foreshadow_type AS text[]), :structure_pattern, :rewrite_instruction, :intensity_level, '{}'::jsonb)
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "type": p_type,
                "applicable_foreshadow_type": fs_types,
                "structure_pattern": pattern,
                "rewrite_instruction": instruction,
                "intensity_level": int(intensity),
            },
        )
    await session.execute(text("INSERT INTO schema_meta(version) VALUES ('2026.02.18_01')"))
    await session.commit()


async def fetch_system_info(session: AsyncSession) -> dict:
    tables = [
        "book",
        "chapter",
        "source",
        "material_card",
        "material_embedding",
        "chapter_ref_inbox",
        "chunk",
        "chunk_embedding",
        "chapter_version",
        "chapter_text_version",
        "draft_run",
        "chapter_outline_detail",
        "outline",
        "jobs",
        "runs",
        "ingest_runs",
        "schema_meta",
        "skill_run",
        "character",
        "character_version",
        "timeline_event",
        "chapter_timeline_event",
        "chapter_fact",
        "character_growth_log",
        "world_fact",
        "plot_hook",
        "profile",
        "profile_version",
        "volume",
        "volume_plan",
        "volume_plan_item",
        "volume_plan_audit",
        "book_profile_link",
        "structure_template",
        "template_usage_log",
        "structure_template_source",
        "template_asset",
        "splitbook",
        "chapter_tension_metrics",
        "arc_target",
        "template_variant",
        "repair_effect_sample",
        "repair_txn",
        "report",
        "app_config",
        "app_settings",
        "book_settings",
        "chapter_settings",
        "settings_preset",
        "settings_audit_log",
        "ab_batch_run",
        "ab_batch_item",
        "book_profile_audit_log",
        "prompt_template",
        "extraction_run",
        "asset_bundle",
        "asset_bundle_item",
        "book_default_assets",
        "asset_usage_log",
        "asset_score_stat",
        "asset_selection_trace",
        "asset_policy_proposal",
        "asset_policy_audit_log",
        "foreshadow",
        "foreshadow_event",
        "structure_combo",
        "payoff_template",
        "growth_milestone",
        "tag_dictionary",
        "tag_alias",
    ]
    table_state: dict[str, bool] = {}
    for table_name in tables:
        res = await session.execute(
            text(
                """
                SELECT EXISTS(
                  SELECT 1 FROM information_schema.tables
                  WHERE table_schema='public' AND table_name=:table_name
                )
                """
            ),
            {"table_name": table_name},
        )
        table_state[table_name] = bool(res.scalar())

    ext = await session.execute(text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')"))
    if table_state.get("schema_meta"):
        version_res = await session.execute(text("SELECT version FROM schema_meta ORDER BY applied_at DESC LIMIT 1"))
        schema_version = version_res.scalar()
    else:
        schema_version = None
    return {
        "time": datetime.now(timezone.utc).isoformat(),
        "pgvector_enabled": bool(ext.scalar()),
        "tables": table_state,
        "schema_version": schema_version,
    }


async def create_book(session: AsyncSession, title: str, author: str | None, language: str, notes: str | None) -> dict:
    profile = await session.execute(text("SELECT profile_id FROM profile ORDER BY created_at ASC LIMIT 1"))
    profile_id = profile.scalar()
    if profile_id is None:
        created = await create_profile(session, "Default Profile", "Auto created", {}, [], [])
        profile_id = created["profile_id"]

    result = await session.execute(
        text(
            """
            INSERT INTO book(profile_id, title, author, language, notes)
            VALUES (:profile_id, :title, :author, :language, :notes)
            RETURNING book_id, profile_id, title, author, language, notes, created_at
            """
        ),
        {"profile_id": str(profile_id), "title": title, "author": author, "language": language, "notes": notes},
    )
    await session.commit()
    row = result.mappings().one()
    return dict(row)


async def list_books(session: AsyncSession, query: str = "", limit: int = 50) -> list[dict]:
    result = await session.execute(
        text(
            """
            SELECT book_id, profile_id, title, author, language, notes, created_at
            FROM book
            WHERE (:query = '' OR title ILIKE '%' || :query || '%')
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"query": (query or "").strip(), "limit": int(limit)},
    )
    return [dict(r) for r in result.mappings().all()]


async def create_chapter(
    session: AsyncSession,
    book_id: str,
    chapter_no: int,
    title: str,
    arc_id: str | None = None,
    arc_index: int | None = None,
) -> dict:
    result = await session.execute(
        text(
            """
            INSERT INTO chapter(book_id, "order", title, arc_id, arc_index)
            VALUES (:book_id, :chapter_no, :title, :arc_id, :arc_index)
            RETURNING chapter_id, book_id, "order" AS chapter_no, title, arc_id, arc_index, created_at
            """
        ),
        {
            "book_id": book_id,
            "chapter_no": chapter_no,
            "title": title or "",
            "arc_id": arc_id,
            "arc_index": arc_index,
        },
    )
    await session.commit()
    return dict(result.mappings().one())


async def list_chapters(session: AsyncSession, book_id: str, query: str = "", limit: int = 200) -> list[dict]:
    result = await session.execute(
        text(
            """
            SELECT chapter_id, book_id, "order" AS chapter_no, title, arc_id, arc_index, created_at
            FROM chapter
            WHERE book_id=:book_id
              AND (:query = '' OR title ILIKE '%' || :query || '%')
            ORDER BY "order" ASC
            LIMIT :limit
            """
        ),
        {"book_id": book_id, "query": (query or "").strip(), "limit": int(limit)},
    )
    return [dict(r) for r in result.mappings().all()]


async def _table_exists(session: AsyncSession, table_name: str) -> bool:
    res = await session.execute(
        text(
            """
            SELECT EXISTS(
              SELECT 1 FROM information_schema.tables
              WHERE table_schema='public' AND table_name=:table_name
            )
            """
        ),
        {"table_name": table_name},
    )
    return bool(res.scalar())


async def unified_search(session: AsyncSession, q: str, limit: int = 20) -> list[dict]:
    query = (q or "").strip()
    if not query:
        return []
    lim = max(1, min(int(limit), 50))
    n = len(query)
    threshold = 0.1 if n <= 2 else (0.2 if n <= 5 else 0.28)
    trgm_enabled = True
    try:
        ext = await session.execute(text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='pg_trgm')"))
        trgm_enabled = bool(ext.scalar())
    except Exception:
        trgm_enabled = False
        await session.rollback()

    if trgm_enabled:
        try:
            await session.execute(text("SELECT set_limit(:threshold)"), {"threshold": threshold})
        except Exception:
            trgm_enabled = False
            await session.rollback()

    per_type_limit = lim
    items: list[dict] = []

    books_sql = (
        """
        SELECT
          'book'::text AS type,
          book_id::text AS id,
          title,
          'book'::text AS subtitle,
          similarity(title, :q) AS score
        FROM book
        WHERE (title % :q OR title ILIKE '%' || :q || '%')
        ORDER BY score DESC
        LIMIT :lim
        """
        if trgm_enabled
        else """
        SELECT
          'book'::text AS type,
          book_id::text AS id,
          title,
          'book'::text AS subtitle,
          CASE WHEN title ILIKE '%' || :q || '%' THEN 0.5 ELSE 0.0 END AS score
        FROM book
        WHERE title ILIKE '%' || :q || '%'
        ORDER BY score DESC, created_at DESC
        LIMIT :lim
        """
    )
    books = await session.execute(text(books_sql), {"q": query, "lim": per_type_limit})
    items.extend(dict(r) for r in books.mappings().all())

    chapters_sql = (
        """
        SELECT
          'chapter'::text AS type,
          c.chapter_id::text AS id,
          ('Ch ' || c."order" || ' - ' || coalesce(c.title,'')) AS title,
          ('book=' || c.book_id::text || ' arc=' || coalesce(c.arc_id,'')) AS subtitle,
          similarity(coalesce(c.title,''), :q) AS score,
          c.book_id::text AS book_id
        FROM chapter c
        WHERE (coalesce(c.title,'') % :q OR coalesce(c.title,'') ILIKE '%' || :q || '%')
        ORDER BY score DESC
        LIMIT :lim
        """
        if trgm_enabled
        else """
        SELECT
          'chapter'::text AS type,
          c.chapter_id::text AS id,
          ('Ch ' || c."order" || ' - ' || coalesce(c.title,'')) AS title,
          ('book=' || c.book_id::text || ' arc=' || coalesce(c.arc_id,'')) AS subtitle,
          CASE WHEN coalesce(c.title,'') ILIKE '%' || :q || '%' THEN 0.5 ELSE 0.0 END AS score,
          c.book_id::text AS book_id
        FROM chapter c
        WHERE coalesce(c.title,'') ILIKE '%' || :q || '%'
        ORDER BY score DESC, c."order" ASC
        LIMIT :lim
        """
    )
    chapters = await session.execute(text(chapters_sql), {"q": query, "lim": per_type_limit})
    items.extend(dict(r) for r in chapters.mappings().all())

    if await _table_exists(session, "material_card"):
        materials_sql = (
            """
            SELECT
              'material'::text AS type,
              m.card_id::text AS id,
              coalesce(m.title, '(untitled)') AS title,
              ('tag=' || coalesce(m.tag,'')) AS subtitle,
              similarity(coalesce(m.title,''), :q) AS score,
              m.book_id::text AS book_id
            FROM material_card m
            WHERE (coalesce(m.title,'') % :q OR coalesce(m.title,'') ILIKE '%' || :q || '%')
            ORDER BY score DESC
            LIMIT :lim
            """
            if trgm_enabled
            else """
            SELECT
              'material'::text AS type,
              m.card_id::text AS id,
              coalesce(m.title, '(untitled)') AS title,
              ('tag=' || coalesce(m.tag,'')) AS subtitle,
              CASE WHEN coalesce(m.title,'') ILIKE '%' || :q || '%' THEN 0.5 ELSE 0.0 END AS score,
              m.book_id::text AS book_id
            FROM material_card m
            WHERE coalesce(m.title,'') ILIKE '%' || :q || '%'
            ORDER BY score DESC, m.created_at DESC
            LIMIT :lim
            """
        )
        materials = await session.execute(text(materials_sql), {"q": query, "lim": per_type_limit})
        items.extend(dict(r) for r in materials.mappings().all())

    if await _table_exists(session, "skill_run"):
        skill_sql = (
            """
            SELECT
              'skill_run'::text AS type,
              sr.skill_run_id::text AS id,
              sr.skill_name AS title,
              ('book=' || sr.book_id::text || ' at=' || to_char(sr.created_at, 'YYYY-MM-DD HH24:MI')) AS subtitle,
              similarity(sr.skill_name, :q) AS score,
              sr.book_id::text AS book_id
            FROM skill_run sr
            WHERE (sr.skill_name % :q OR sr.skill_name ILIKE '%' || :q || '%')
            ORDER BY score DESC
            LIMIT :lim
            """
            if trgm_enabled
            else """
            SELECT
              'skill_run'::text AS type,
              sr.skill_run_id::text AS id,
              sr.skill_name AS title,
              ('book=' || sr.book_id::text || ' at=' || to_char(sr.created_at, 'YYYY-MM-DD HH24:MI')) AS subtitle,
              CASE WHEN sr.skill_name ILIKE '%' || :q || '%' THEN 0.5 ELSE 0.0 END AS score,
              sr.book_id::text AS book_id
            FROM skill_run sr
            WHERE sr.skill_name ILIKE '%' || :q || '%'
            ORDER BY score DESC, sr.created_at DESC
            LIMIT :lim
            """
        )
        skill_runs = await session.execute(text(skill_sql), {"q": query, "lim": per_type_limit})
        items.extend(dict(r) for r in skill_runs.mappings().all())

    items.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    return items[:lim]


async def create_job(session: AsyncSession, capability_id: str, payload: dict, request_id: str) -> dict:
    now = datetime.now(timezone.utc)
    progress = {"pct": 0, "phase": "queued", "message": None, "counters": {}}
    payload = dict(payload or {})
    payload.setdefault("request_id", request_id)
    book_id = payload.get("book_id")
    chapter_id = payload.get("chapter_id")
    job_type = capability_id.upper().replace(".", "_")
    result = await session.execute(
        text(
            """
            INSERT INTO jobs(book_id, chapter_id, job_type, capability_id, status, stage, progress_value, progress, payload, request_id, created_at, updated_at)
            VALUES (:book_id, :chapter_id, :job_type, :capability_id, 'queued', 'QUEUED', 0.0, CAST(:progress AS jsonb), CAST(:payload AS jsonb), :request_id, :created_at, :updated_at)
            RETURNING job_id, book_id, chapter_id, job_type, capability_id, status, stage, progress_value, progress, run_id, result, logs, error, created_at, updated_at
            """
        ),
        {
            "book_id": book_id,
            "chapter_id": chapter_id,
            "job_type": job_type,
            "capability_id": capability_id,
            "progress": json.dumps(progress),
            "payload": json.dumps(payload),
            "request_id": request_id,
            "created_at": now,
            "updated_at": now,
        },
    )
    await session.commit()
    return dict(result.mappings().one())


async def get_job(session: AsyncSession, job_id: UUID) -> dict | None:
    result = await session.execute(
        text(
            """
            SELECT job_id, book_id, chapter_id, job_type, capability_id, status, stage, progress_value, progress, run_id, payload, result, logs, error, created_at, updated_at
            FROM jobs
            WHERE job_id=:job_id
            """
        ),
        {"job_id": str(job_id)},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def list_jobs(
    session: AsyncSession,
    status: str | None = None,
    limit: int = 30,
) -> list[dict]:
    sql = """
      SELECT job_id, book_id, chapter_id, job_type, capability_id, status, stage, progress_value, progress, run_id, payload, result, logs, error, created_at, updated_at
      FROM jobs
    """
    params: dict[str, object] = {"limit": limit}
    if status:
        sql += " WHERE status = :status"
        params["status"] = status
    sql += " ORDER BY created_at DESC LIMIT :limit"
    result = await session.execute(text(sql), params)
    return [dict(r) for r in result.mappings().all()]


async def append_job_log(session: AsyncSession, job_id: str, level: str, phase: str, message: str) -> None:
    line = f"[{level}] [{phase}] {message}"
    await session.execute(
        text(
            """
            UPDATE jobs
            SET logs = CASE
              WHEN COALESCE(array_length(logs, 1), 0) >= 200
                THEN logs[2:200] || ARRAY[:line]
              ELSE array_append(logs, :line)
            END,
            updated_at=now()
            WHERE job_id=:job_id
            """
        ),
        {"job_id": job_id, "line": line[:1000]},
    )
    await session.commit()


async def get_settings(session: AsyncSession) -> dict:
    result = await session.execute(text("SELECT key, value FROM app_config"))
    out: dict[str, object] = {}
    for row in result.mappings().all():
        out[str(row["key"])] = row["value"]
    return out


async def update_settings(session: AsyncSession, updates: dict) -> dict:
    for key, value in updates.items():
        await session.execute(
            text(
                """
                INSERT INTO app_config(key, value, updated_at)
                VALUES (:key, CAST(:value AS jsonb), now())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at=now()
                """
            ),
            {"key": key, "value": json.dumps(value)},
        )
    await session.commit()
    return await get_settings(session)


DEFAULT_SCOPED_SETTINGS = {
    "ingest": {"chunk_size": 600, "overlap": 120, "encoding": "utf-8"},
    "embedding": {"model": "bge-m3:latest", "batch": 64},
    "simguard": {
        "enabled": True,
        "scope_default": ["material_card"],
        "sim_threshold": 0.86,
        "top_k": 5,
        "max_hits": 20,
        "short_chunk_boost": 0.02,
    },
    "eval": {
        "enabled": True,
        "targets": {
            "hook": 0.75,
            "conflict": 0.70,
            "pacing": 0.70,
            "clarity": 0.68,
            "character": 0.70,
            "stakes": 0.72,
            "foreshadow": 0.65,
            "payoff": 0.68,
        },
    },
    "draft": {"default_words": 2200, "pov": "第三人称", "tone": "热血+克制"},
    "humanize": {"enabled": False, "level_default": "mid", "remove_cliches": True, "reduce_ai_markers": True},
    "autopatch": {"enabled": True, "max_changes": 8, "max_nodes_touched": 5, "strictness": "mid"},
    "ab": {"penalty": 0.8, "include_baseline": True},
    "orchestrator": {
        "max_structure_weight": 4,
        "max_tasks_per_chapter": 3,
        "ban_strong_cliff": False,
        "replay": {
            "defer_max_rounds": 3,
            "defer_expire_grace": 0.12,
            "tuning": {
                "avg_filtered_medium": 1.5,
                "avg_filtered_high": 3.0,
                "avg_filtered_low": 0.3,
                "max_round_hits_red": 3,
                "expired_hits_red": 4,
            },
        },
        "context_budget": {
            "character_facts": {"max_items": 8, "max_chars": 1000},
            "timeline_facts": {"max_items": 8, "max_chars": 1000},
            "open_foreshadows": {"max_items": 6, "max_chars": 900},
            "growth_milestones": {"max_items": 6, "max_chars": 900},
        },
    },
    "assets": {
        "risk": {"block_threshold": 0.25},
        "inject": {"hooks_n": 2, "beats_n": 2, "styles_n": 1, "templates_n": 1, "max_chars": 2000},
        "select": {"epsilon": 0.1, "top_k": 10},
        "cooldown": {
            "window_uses": 20,
            "time_window_days": 14,
            "hard_cap": 3,
            "penalty_per_use": 0.12,
            "pinned_penalty_multiplier": 0.5,
        },
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = json.loads(json.dumps(base))
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _clamp_int(value: object, low: int, high: int, fallback: int) -> int:
    try:
        n = int(value)
    except Exception:
        return fallback
    return max(low, min(high, n))


def _clamp_float(value: object, low: float, high: float, fallback: float) -> float:
    try:
        n = float(value)
    except Exception:
        return fallback
    return max(low, min(high, n))


def normalize_scoped_settings(settings: dict | None) -> dict:
    merged = _deep_merge(DEFAULT_SCOPED_SETTINGS, settings or {})
    ingest = merged.get("ingest") or {}
    embedding = merged.get("embedding") or {}
    simguard = merged.get("simguard") or {}
    draft = merged.get("draft") or {}
    autopatch = merged.get("autopatch") or {}
    ab = merged.get("ab") or {}
    orchestrator = merged.get("orchestrator") if isinstance(merged.get("orchestrator"), dict) else {}
    assets = merged.get("assets") if isinstance(merged.get("assets"), dict) else {}
    assets_risk = assets.get("risk") if isinstance(assets.get("risk"), dict) else {}
    assets_inject = assets.get("inject") if isinstance(assets.get("inject"), dict) else {}
    assets_select = assets.get("select") if isinstance(assets.get("select"), dict) else {}
    assets_cooldown = assets.get("cooldown") if isinstance(assets.get("cooldown"), dict) else {}

    ingest["chunk_size"] = _clamp_int(ingest.get("chunk_size"), 200, 4000, 600)
    ingest["overlap"] = _clamp_int(ingest.get("overlap"), 0, 1000, 120)
    ingest["encoding"] = str(ingest.get("encoding") or "utf-8")

    embedding["batch"] = _clamp_int(embedding.get("batch"), 1, 256, 64)
    embedding["model"] = str(embedding.get("model") or "bge-m3:latest")

    simguard["sim_threshold"] = _clamp_float(simguard.get("sim_threshold"), 0.0, 1.0, 0.86)
    simguard["top_k"] = _clamp_int(simguard.get("top_k"), 1, 20, 5)
    simguard["max_hits"] = _clamp_int(simguard.get("max_hits"), 1, 100, 20)
    simguard["short_chunk_boost"] = _clamp_float(simguard.get("short_chunk_boost"), 0.0, 0.2, 0.02)
    if not isinstance(simguard.get("scope_default"), list):
        simguard["scope_default"] = ["material_card"]

    draft["default_words"] = _clamp_int(draft.get("default_words"), 300, 10000, 2200)
    draft["pov"] = str(draft.get("pov") or "第三人称")
    draft["tone"] = str(draft.get("tone") or "热血+克制")

    autopatch["max_changes"] = _clamp_int(autopatch.get("max_changes"), 1, 30, 8)
    autopatch["max_nodes_touched"] = _clamp_int(autopatch.get("max_nodes_touched"), 1, 20, 5)
    autopatch["strictness"] = str(autopatch.get("strictness") or "mid")

    ab["penalty"] = _clamp_float(ab.get("penalty"), 0.0, 5.0, 0.8)
    ab["include_baseline"] = bool(ab.get("include_baseline", True))

    orchestrator["max_structure_weight"] = _clamp_int(orchestrator.get("max_structure_weight"), 2, 7, 4)
    orchestrator["max_tasks_per_chapter"] = _clamp_int(orchestrator.get("max_tasks_per_chapter"), 1, 5, 3)
    orchestrator["ban_strong_cliff"] = bool(orchestrator.get("ban_strong_cliff", False))
    replay = orchestrator.get("replay") if isinstance(orchestrator.get("replay"), dict) else {}
    replay["defer_max_rounds"] = _clamp_int(replay.get("defer_max_rounds"), 1, 8, 3)
    replay["defer_expire_grace"] = _clamp_float(replay.get("defer_expire_grace"), 0.0, 0.5, 0.12)
    tuning = replay.get("tuning") if isinstance(replay.get("tuning"), dict) else {}
    tuning["avg_filtered_medium"] = _clamp_float(tuning.get("avg_filtered_medium"), 0.1, 10.0, 1.5)
    tuning["avg_filtered_high"] = _clamp_float(tuning.get("avg_filtered_high"), 0.2, 12.0, 3.0)
    if tuning["avg_filtered_high"] < tuning["avg_filtered_medium"]:
        tuning["avg_filtered_high"] = tuning["avg_filtered_medium"]
    tuning["avg_filtered_low"] = _clamp_float(tuning.get("avg_filtered_low"), 0.0, 2.0, 0.3)
    tuning["max_round_hits_red"] = _clamp_int(tuning.get("max_round_hits_red"), 1, 30, 3)
    tuning["expired_hits_red"] = _clamp_int(tuning.get("expired_hits_red"), 1, 30, 4)
    replay["tuning"] = tuning
    orchestrator["replay"] = replay
    budget = orchestrator.get("context_budget") if isinstance(orchestrator.get("context_budget"), dict) else {}
    for key, dflt in {
        "character_facts": {"max_items": 8, "max_chars": 1000},
        "timeline_facts": {"max_items": 8, "max_chars": 1000},
        "open_foreshadows": {"max_items": 6, "max_chars": 900},
        "growth_milestones": {"max_items": 6, "max_chars": 900},
    }.items():
        cur = budget.get(key) if isinstance(budget.get(key), dict) else {}
        budget[key] = {
            "max_items": _clamp_int(cur.get("max_items"), 1, 20, dflt["max_items"]),
            "max_chars": _clamp_int(cur.get("max_chars"), 120, 6000, dflt["max_chars"]),
        }
    orchestrator["context_budget"] = budget

    assets_risk["block_threshold"] = _clamp_float(assets_risk.get("block_threshold"), 0.0, 1.0, 0.25)
    assets_inject["hooks_n"] = _clamp_int(assets_inject.get("hooks_n"), 0, 6, 2)
    assets_inject["beats_n"] = _clamp_int(assets_inject.get("beats_n"), 0, 6, 2)
    assets_inject["styles_n"] = _clamp_int(assets_inject.get("styles_n"), 0, 3, 1)
    assets_inject["templates_n"] = _clamp_int(assets_inject.get("templates_n"), 0, 3, 1)
    assets_inject["max_chars"] = _clamp_int(assets_inject.get("max_chars"), 200, 6000, 2000)
    assets_select["epsilon"] = _clamp_float(assets_select.get("epsilon"), 0.0, 1.0, 0.1)
    assets_select["top_k"] = _clamp_int(assets_select.get("top_k"), 1, 100, 10)
    assets_cooldown["window_uses"] = _clamp_int(assets_cooldown.get("window_uses"), 1, 200, 20)
    assets_cooldown["time_window_days"] = _clamp_int(assets_cooldown.get("time_window_days"), 1, 90, 14)
    assets_cooldown["hard_cap"] = _clamp_int(assets_cooldown.get("hard_cap"), 1, 20, 3)
    assets_cooldown["penalty_per_use"] = _clamp_float(assets_cooldown.get("penalty_per_use"), 0.0, 1.0, 0.12)
    assets_cooldown["pinned_penalty_multiplier"] = _clamp_float(
        assets_cooldown.get("pinned_penalty_multiplier"), 0.0, 1.0, 0.5
    )
    assets["risk"] = assets_risk
    assets["inject"] = assets_inject
    assets["select"] = assets_select
    assets["cooldown"] = assets_cooldown

    merged["ingest"] = ingest
    merged["embedding"] = embedding
    merged["simguard"] = simguard
    merged["draft"] = draft
    merged["autopatch"] = autopatch
    merged["ab"] = ab
    merged["orchestrator"] = orchestrator
    merged["assets"] = assets
    return merged


async def get_global_settings_scoped(session: AsyncSession) -> dict:
    result = await session.execute(text("SELECT settings FROM app_settings WHERE singleton_id=1"))
    row = result.mappings().first()
    raw = dict(row)["settings"] if row else {}
    return normalize_scoped_settings(raw or {})


def get_default_scoped_settings_template() -> dict:
    return normalize_scoped_settings(DEFAULT_SCOPED_SETTINGS)


async def set_global_settings_scoped(session: AsyncSession, settings_value: dict) -> dict:
    normalized = normalize_scoped_settings(settings_value)
    await session.execute(
        text(
            """
            INSERT INTO app_settings(singleton_id, settings, updated_at)
            VALUES (1, CAST(:settings AS jsonb), now())
            ON CONFLICT (singleton_id)
            DO UPDATE SET settings=EXCLUDED.settings, updated_at=now()
            """
        ),
        {"settings": json.dumps(normalized)},
    )
    await session.commit()
    return normalized


async def get_book_settings(session: AsyncSession, book_id: str) -> dict | None:
    result = await session.execute(text("SELECT settings FROM book_settings WHERE book_id=:book_id"), {"book_id": book_id})
    row = result.mappings().first()
    if not row:
        return None
    value = dict(row).get("settings") or {}
    return value if isinstance(value, dict) else {}


async def set_book_settings(session: AsyncSession, book_id: str, settings_value: dict) -> dict:
    current = await get_book_settings(session, book_id) or {}
    merged = _deep_merge(current, settings_value or {})
    await session.execute(
        text(
            """
            INSERT INTO book_settings(book_id, settings, updated_at)
            VALUES (:book_id, CAST(:settings AS jsonb), now())
            ON CONFLICT (book_id)
            DO UPDATE SET settings=EXCLUDED.settings, updated_at=now()
            """
        ),
        {"book_id": book_id, "settings": json.dumps(merged)},
    )
    await session.commit()
    return merged


async def get_chapter_settings(session: AsyncSession, chapter_id: str) -> dict | None:
    result = await session.execute(
        text("SELECT settings FROM chapter_settings WHERE chapter_id=:chapter_id"),
        {"chapter_id": chapter_id},
    )
    row = result.mappings().first()
    if not row:
        return None
    value = dict(row).get("settings") or {}
    return value if isinstance(value, dict) else {}


async def set_chapter_settings(session: AsyncSession, chapter_id: str, settings_value: dict) -> dict:
    current = await get_chapter_settings(session, chapter_id) or {}
    merged = _deep_merge(current, settings_value or {})
    await session.execute(
        text(
            """
            INSERT INTO chapter_settings(chapter_id, settings, updated_at)
            VALUES (:chapter_id, CAST(:settings AS jsonb), now())
            ON CONFLICT (chapter_id)
            DO UPDATE SET settings=EXCLUDED.settings, updated_at=now()
            """
        ),
        {"chapter_id": chapter_id, "settings": json.dumps(merged)},
    )
    await session.commit()
    return merged


async def get_effective_settings(session: AsyncSession, chapter_id: str) -> dict | None:
    chapter_row = await session.execute(
        text("SELECT chapter_id, book_id FROM chapter WHERE chapter_id=:chapter_id"),
        {"chapter_id": chapter_id},
    )
    chapter = chapter_row.mappings().first()
    if not chapter:
        return None
    global_cfg = await get_global_settings_scoped(session)
    book_cfg = await get_book_settings(session, str(chapter["book_id"])) or {}
    chapter_cfg = await get_chapter_settings(session, chapter_id) or {}
    effective = normalize_scoped_settings(_deep_merge(_deep_merge(global_cfg, book_cfg), chapter_cfg))
    return {
        "effective": effective,
        "sources": {
            "global": global_cfg,
            "book": book_cfg,
            "chapter": chapter_cfg,
        },
    }


def _flatten_settings(obj: dict | None, prefix: str = "") -> dict[str, object]:
    out: dict[str, object] = {}
    if not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            out.update(_flatten_settings(v, key))
        else:
            out[key] = v
    return out


def diff_settings(a: dict | None, b: dict | None) -> list[dict]:
    fa = _flatten_settings(a or {})
    fb = _flatten_settings(b or {})
    keys = sorted(set(fa.keys()) | set(fb.keys()))
    changes: list[dict] = []
    for key in keys:
        in_a = key in fa
        in_b = key in fb
        if in_a and not in_b:
            changes.append({"op": "remove", "key": key, "a": fa[key]})
        elif (not in_a) and in_b:
            changes.append({"op": "add", "key": key, "b": fb[key]})
        else:
            va = fa[key]
            vb = fb[key]
            if json.dumps(va, ensure_ascii=False, sort_keys=True) != json.dumps(vb, ensure_ascii=False, sort_keys=True):
                changes.append({"op": "change", "key": key, "a": va, "b": vb})
    return changes


async def list_settings_presets(session: AsyncSession, limit: int = 100) -> list[dict]:
    result = await session.execute(
        text(
            """
            SELECT preset_id, name, description, settings, created_at, updated_at
            FROM settings_preset
            ORDER BY updated_at DESC, created_at DESC
            LIMIT :limit
            """
        ),
        {"limit": max(1, min(limit, 500))},
    )
    return [dict(r) for r in result.mappings().all()]


async def get_settings_preset(session: AsyncSession, preset_id: str) -> dict | None:
    result = await session.execute(
        text(
            """
            SELECT preset_id, name, description, settings, created_at, updated_at
            FROM settings_preset
            WHERE preset_id=:preset_id
            """
        ),
        {"preset_id": preset_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def create_settings_preset(session: AsyncSession, name: str, description: str, settings_value: dict) -> dict:
    result = await session.execute(
        text(
            """
            INSERT INTO settings_preset(name, description, settings, updated_at)
            VALUES (:name, :description, CAST(:settings AS jsonb), now())
            RETURNING preset_id, name, description, settings, created_at, updated_at
            """
        ),
        {"name": name, "description": description, "settings": json.dumps(settings_value or {})},
    )
    await session.commit()
    return dict(result.mappings().one())


async def update_settings_preset(
    session: AsyncSession,
    preset_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    settings_value: dict | None = None,
) -> dict | None:
    current = await get_settings_preset(session, preset_id)
    if not current:
        return None
    result = await session.execute(
        text(
            """
            UPDATE settings_preset
            SET
              name=:name,
              description=:description,
              settings=CAST(:settings AS jsonb),
              updated_at=now()
            WHERE preset_id=:preset_id
            RETURNING preset_id, name, description, settings, created_at, updated_at
            """
        ),
        {
            "preset_id": preset_id,
            "name": name if name is not None else current["name"],
            "description": description if description is not None else (current.get("description") or ""),
            "settings": json.dumps(settings_value if settings_value is not None else (current.get("settings") or {})),
        },
    )
    await session.commit()
    row = result.mappings().first()
    return dict(row) if row else None


async def delete_settings_preset(session: AsyncSession, preset_id: str) -> bool:
    result = await session.execute(text("DELETE FROM settings_preset WHERE preset_id=:preset_id"), {"preset_id": preset_id})
    await session.commit()
    return bool(result.rowcount and result.rowcount > 0)


async def _get_scope_settings_no_commit(
    session: AsyncSession,
    *,
    scope: str,
    book_id: str | None = None,
    chapter_id: str | None = None,
) -> tuple[dict, str | None]:
    if scope == "global":
        row = await session.execute(text("SELECT settings FROM app_settings WHERE singleton_id=1"))
        r = row.mappings().first()
        return normalize_scoped_settings((dict(r).get("settings") if r else {}) or {}), None
    if scope == "book":
        if not book_id:
            raise RuntimeError("BOOK_ID_REQUIRED")
        row = await session.execute(text("SELECT settings FROM book_settings WHERE book_id=:book_id"), {"book_id": book_id})
        r = row.mappings().first()
        return (dict(r).get("settings") if r else {}) or {}, book_id
    if scope == "chapter":
        if not chapter_id:
            raise RuntimeError("CHAPTER_ID_REQUIRED")
        row = await session.execute(
            text("SELECT settings FROM chapter_settings WHERE chapter_id=:chapter_id"),
            {"chapter_id": chapter_id},
        )
        r = row.mappings().first()
        return (dict(r).get("settings") if r else {}) or {}, chapter_id
    raise RuntimeError("INVALID_SCOPE")


async def _set_scope_settings_no_commit(
    session: AsyncSession,
    *,
    scope: str,
    settings_value: dict,
    book_id: str | None = None,
    chapter_id: str | None = None,
) -> dict:
    if scope == "global":
        normalized = normalize_scoped_settings(settings_value or {})
        await session.execute(
            text(
                """
                INSERT INTO app_settings(singleton_id, settings, updated_at)
                VALUES (1, CAST(:settings AS jsonb), now())
                ON CONFLICT (singleton_id)
                DO UPDATE SET settings=EXCLUDED.settings, updated_at=now()
                """
            ),
            {"settings": json.dumps(normalized)},
        )
        return normalized
    if scope == "book":
        if not book_id:
            raise RuntimeError("BOOK_ID_REQUIRED")
        await session.execute(
            text(
                """
                INSERT INTO book_settings(book_id, settings, updated_at)
                VALUES (:book_id, CAST(:settings AS jsonb), now())
                ON CONFLICT (book_id)
                DO UPDATE SET settings=EXCLUDED.settings, updated_at=now()
                """
            ),
            {"book_id": book_id, "settings": json.dumps(settings_value or {})},
        )
        return settings_value or {}
    if scope == "chapter":
        if not chapter_id:
            raise RuntimeError("CHAPTER_ID_REQUIRED")
        await session.execute(
            text(
                """
                INSERT INTO chapter_settings(chapter_id, settings, updated_at)
                VALUES (:chapter_id, CAST(:settings AS jsonb), now())
                ON CONFLICT (chapter_id)
                DO UPDATE SET settings=EXCLUDED.settings, updated_at=now()
                """
            ),
            {"chapter_id": chapter_id, "settings": json.dumps(settings_value or {})},
        )
        return settings_value or {}
    raise RuntimeError("INVALID_SCOPE")


async def _insert_settings_audit_log_no_commit(
    session: AsyncSession,
    *,
    action: str,
    scope: str,
    scope_id: str | None,
    preset_id: str | None = None,
    mode: str | None = None,
    before_settings: dict | None = None,
    after_settings: dict | None = None,
    note: str = "",
    actor: str = "desktop_user",
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO settings_audit_log(
              actor, action, scope, scope_id, preset_id, mode, before_settings, after_settings, note
            )
            VALUES (
              :actor, :action, :scope, :scope_id, :preset_id, :mode,
              CAST(:before_settings AS jsonb), CAST(:after_settings AS jsonb), :note
            )
            """
        ),
        {
            "actor": actor,
            "action": action,
            "scope": scope,
            "scope_id": scope_id,
            "preset_id": preset_id,
            "mode": mode,
            "before_settings": json.dumps(before_settings) if before_settings is not None else None,
            "after_settings": json.dumps(after_settings) if after_settings is not None else None,
            "note": note or "",
        },
    )


async def apply_settings_preset(
    session: AsyncSession,
    *,
    preset_id: str,
    scope: str,
    book_id: str | None = None,
    chapter_id: str | None = None,
    mode: str = "merge",
) -> dict:
    preset = await get_settings_preset(session, preset_id)
    if not preset:
        raise RuntimeError("PRESET_NOT_FOUND")
    settings_value = preset.get("settings") or {}
    if not isinstance(settings_value, dict):
        settings_value = {}
    mode_value = str(mode or "merge").lower()
    before, scope_id = await _get_scope_settings_no_commit(
        session, scope=scope, book_id=book_id, chapter_id=chapter_id
    )
    if mode_value == "replace":
        after = settings_value
    else:
        after = _deep_merge(before, settings_value)
    after = normalize_scoped_settings(after) if scope == "global" else after
    changed = len(diff_settings(before, after))
    applied = await _set_scope_settings_no_commit(
        session, scope=scope, settings_value=after, book_id=book_id, chapter_id=chapter_id
    )
    await _insert_settings_audit_log_no_commit(
        session,
        action="preset_apply",
        scope=scope,
        scope_id=scope_id,
        preset_id=preset_id,
        mode=mode_value,
        before_settings=before,
        after_settings=applied,
        note=f"apply preset {preset.get('name') or preset_id}",
    )
    await session.commit()
    out: dict[str, object] = {"scope": scope, "settings": applied, "changed": changed}
    if scope_id:
        out["scope_id"] = scope_id
    if scope == "book":
        out["book_id"] = scope_id
    if scope == "chapter":
        out["chapter_id"] = scope_id
    return out


async def list_settings_audit(
    session: AsyncSession,
    *,
    scope: str | None = None,
    scope_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    sql = """
      SELECT audit_id, actor, action, scope, scope_id, preset_id, mode, before_settings, after_settings, note, created_at
      FROM settings_audit_log
    """
    clauses: list[str] = []
    params: dict[str, object] = {"limit": max(1, min(limit, 500))}
    if scope:
        clauses.append("scope=:scope")
        params["scope"] = scope
    if scope_id:
        clauses.append("scope_id=:scope_id")
        params["scope_id"] = scope_id
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT :limit"
    result = await session.execute(text(sql), params)
    return [dict(r) for r in result.mappings().all()]


async def rollback_settings_audit(
    session: AsyncSession,
    *,
    audit_id: str,
    note: str = "",
    actor: str = "desktop_user",
) -> dict:
    row = await session.execute(
        text(
            """
            SELECT audit_id, action, scope, scope_id, preset_id, before_settings, after_settings
            FROM settings_audit_log
            WHERE audit_id=:audit_id
            FOR UPDATE
            """
        ),
        {"audit_id": audit_id},
    )
    audit = row.mappings().first()
    if not audit:
        raise RuntimeError("AUDIT_NOT_FOUND")
    if str(audit.get("action") or "") != "preset_apply":
        raise RuntimeError("AUDIT_NOT_ROLLBACKABLE")
    scope = str(audit.get("scope") or "")
    scope_id = str(audit.get("scope_id")) if audit.get("scope_id") else None
    rollback_target = audit.get("before_settings") or {}
    if not isinstance(rollback_target, dict):
        raise RuntimeError("INVALID_AUDIT_BEFORE_SETTINGS")
    before_current, _ = await _get_scope_settings_no_commit(
        session,
        scope=scope,
        book_id=scope_id if scope == "book" else None,
        chapter_id=scope_id if scope == "chapter" else None,
    )
    if json.dumps(before_current, ensure_ascii=False, sort_keys=True) == json.dumps(
        rollback_target, ensure_ascii=False, sort_keys=True
    ):
        raise RuntimeError("ROLLBACK_NOOP")
    after = normalize_scoped_settings(rollback_target) if scope == "global" else rollback_target
    changed = len(diff_settings(before_current, after))
    applied = await _set_scope_settings_no_commit(
        session,
        scope=scope,
        settings_value=after,
        book_id=scope_id if scope == "book" else None,
        chapter_id=scope_id if scope == "chapter" else None,
    )
    await _insert_settings_audit_log_no_commit(
        session,
        action="preset_rollback",
        scope=scope,
        scope_id=scope_id,
        preset_id=str(audit.get("preset_id")) if audit.get("preset_id") else None,
        mode=None,
        before_settings=before_current,
        after_settings=applied,
        note=(note or "").strip() or f"rollback of audit_id={audit_id}",
        actor=actor,
    )
    await session.commit()
    out: dict[str, object] = {
        "ok": True,
        "rolled_back_from": audit_id,
        "scope": scope,
        "changed": changed,
    }
    if scope_id:
        out["scope_id"] = scope_id
    return out


async def health_checks(session: AsyncSession) -> dict:
    checks: dict[str, object] = {}
    t0 = datetime.now(timezone.utc)
    await session.execute(text("SELECT 1"))
    latency_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
    checks["postgres"] = {"ok": True, "latency_ms": latency_ms}

    ext = await session.execute(text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')"))
    checks["pgvector"] = {"ok": bool(ext.scalar())}

    idx = await session.execute(
        text(
            """
            SELECT EXISTS(
              SELECT 1 FROM pg_indexes
              WHERE tablename='chunk' AND indexname LIKE '%fts%'
            )
            """
        )
    )
    checks["fts_index"] = {"ok": bool(idx.scalar())}

    running = await session.execute(text("SELECT COUNT(*) FROM jobs WHERE status='running'"))
    failed = await session.execute(
        text("SELECT COUNT(*) FROM jobs WHERE status='failed' AND created_at > now() - interval '24 hours'")
    )
    checks["jobs"] = {"running": int(running.scalar() or 0), "failed_last_24h": int(failed.scalar() or 0)}

    total, used, free = shutil.disk_usage(".")
    checks["disk"] = {"ok": (free / (1024**3)) >= 5, "free_gb": round(free / (1024**3), 2)}

    status = "ok"
    if not checks["disk"]["ok"] or not checks["pgvector"]["ok"]:
        status = "degraded"
    return {"status": status, "checks": checks}


async def create_skill_run(
    session: AsyncSession,
    book_id: str,
    skill_name: str,
    schema_ver: int,
    output: dict,
) -> dict:
    result = await session.execute(
        text(
            """
            INSERT INTO skill_run(book_id, skill_name, schema_ver, output)
            VALUES (:book_id, :skill_name, :schema_ver, CAST(:output AS jsonb))
            RETURNING skill_run_id, book_id, skill_name, schema_ver, output, created_at
            """
        ),
        {
            "book_id": book_id,
            "skill_name": skill_name,
            "schema_ver": schema_ver,
            "output": json.dumps(output),
        },
    )
    await session.commit()
    return dict(result.mappings().one())


def _profile_snapshot_from_parts(
    *,
    name: str | None,
    note: str | None,
    features: dict | None,
    dos: list[str] | None,
    donts: list[str] | None,
) -> dict:
    return {
        "name": name or "",
        "note": note or "",
        "features": dict(features or {}),
        "dos": list(dos or []),
        "donts": list(donts or []),
    }


def _profile_snapshot_from_row(row: dict | None) -> dict:
    row = row or {}
    return _profile_snapshot_from_parts(
        name=str(row.get("name") or ""),
        note=str(row.get("note") or ""),
        features=row.get("features") if isinstance(row.get("features"), dict) else {},
        dos=row.get("dos") if isinstance(row.get("dos"), list) else [],
        donts=row.get("donts") if isinstance(row.get("donts"), list) else [],
    )


async def _next_profile_version_no_commit(session: AsyncSession, profile_id: str) -> int:
    res = await session.execute(
        text("SELECT COALESCE(MAX(version), 0) + 1 FROM profile_version WHERE profile_id=:profile_id"),
        {"profile_id": profile_id},
    )
    return int(res.scalar() or 1)


async def _insert_profile_version_no_commit(
    session: AsyncSession,
    *,
    profile_id: str,
    version: int,
    snapshot: dict,
    actor: str,
    action: str,
    note: str,
    parent_version: int | None = None,
    source_text_ver_ids: list[str] | None = None,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO profile_version(
              profile_id, version, snapshot, actor, action, note, parent_version, source_text_ver_ids
            )
            VALUES (
              :profile_id, :version, CAST(:snapshot AS jsonb), :actor, :action, :note, :parent_version, CAST(:source_text_ver_ids AS jsonb)
            )
            """
        ),
        {
            "profile_id": profile_id,
            "version": int(version),
            "snapshot": json.dumps(snapshot, ensure_ascii=False),
            "actor": actor or "desktop_user",
            "action": action or "manual_edit",
            "note": note or "",
            "parent_version": parent_version,
            "source_text_ver_ids": json.dumps(source_text_ver_ids or [], ensure_ascii=False),
        },
    )


async def create_profile(
    session: AsyncSession,
    name: str,
    note: str | None,
    features: dict | None = None,
    dos: list[str] | None = None,
    donts: list[str] | None = None,
) -> dict:
    result = await session.execute(
        text(
            """
            INSERT INTO profile(name, note, active_version, features, dos, donts, updated_at)
            VALUES (:name, :note, 1, CAST(:features AS jsonb), CAST(:dos AS text[]), CAST(:donts AS text[]), now())
            RETURNING profile_id, name, note, active_version, features, dos, donts, created_at, updated_at
            """
        ),
        {
            "name": name,
            "note": note,
            "features": json.dumps(features or {}),
            "dos": dos or [],
            "donts": donts or [],
        },
    )
    row = dict(result.mappings().one())
    await _insert_profile_version_no_commit(
        session,
        profile_id=str(row["profile_id"]),
        version=1,
        snapshot=_profile_snapshot_from_row(row),
        actor="desktop_user",
        action="create",
        note=(note or "").strip() or "create profile",
        parent_version=None,
        source_text_ver_ids=[],
    )
    await session.commit()
    return row


async def list_profiles(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        text(
            """
            SELECT profile_id, name, note, active_version, features, dos, donts, created_at, updated_at
            FROM profile
            ORDER BY updated_at DESC, created_at DESC
            """
        )
    )
    return [dict(r) for r in result.mappings().all()]


async def get_profile(session: AsyncSession, profile_id: str) -> dict | None:
    result = await session.execute(
        text(
            """
            SELECT profile_id, name, note, active_version, features, dos, donts, created_at, updated_at
            FROM profile
            WHERE profile_id=:profile_id
            """
        ),
        {"profile_id": profile_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def update_profile(
    session: AsyncSession,
    profile_id: str,
    *,
    name: str | None = None,
    note: str | None = None,
    features: dict | None = None,
    dos: list[str] | None = None,
    donts: list[str] | None = None,
    create_version: bool = True,
    version_action: str = "manual_edit",
    version_note: str | None = None,
    version_actor: str = "desktop_user",
    source_text_ver_ids: list[str] | None = None,
) -> dict | None:
    current = await get_profile(session, profile_id)
    if not current:
        return None
    next_name = name if name is not None else current["name"]
    next_note = note if note is not None else current.get("note")
    next_features = features if features is not None else (current.get("features") or {})
    next_dos = dos if dos is not None else (current.get("dos") or [])
    next_donts = donts if donts is not None else (current.get("donts") or [])
    active_version = int(current.get("active_version") or 1)
    next_active_version = active_version
    if create_version:
        next_active_version = await _next_profile_version_no_commit(session, profile_id)
        await _insert_profile_version_no_commit(
            session,
            profile_id=profile_id,
            version=next_active_version,
            snapshot=_profile_snapshot_from_parts(
                name=next_name,
                note=next_note,
                features=next_features,
                dos=next_dos,
                donts=next_donts,
            ),
            actor=version_actor,
            action=version_action,
            note=(version_note or "").strip() or version_action,
            parent_version=active_version,
            source_text_ver_ids=source_text_ver_ids or [],
        )
    result = await session.execute(
        text(
            """
            UPDATE profile
            SET
              name=:name,
              note=:note,
              active_version=:active_version,
              features=CAST(:features AS jsonb),
              dos=CAST(:dos AS text[]),
              donts=CAST(:donts AS text[]),
              updated_at=now()
            WHERE profile_id=:profile_id
            RETURNING profile_id, name, note, active_version, features, dos, donts, created_at, updated_at
            """
        ),
        {
            "profile_id": profile_id,
            "name": next_name,
            "note": next_note,
            "active_version": next_active_version,
            "features": json.dumps(next_features),
            "dos": next_dos,
            "donts": next_donts,
        },
    )
    await session.commit()
    row = result.mappings().first()
    return dict(row) if row else None


async def bind_book_profile(session: AsyncSession, book_id: str, profile_id: str | None) -> dict | None:
    result = await session.execute(
        text(
            """
            UPDATE book
            SET profile_id=:profile_id, updated_at=now()
            WHERE book_id=:book_id
            RETURNING book_id, profile_id, title, author, language, notes, created_at
            """
        ),
        {"book_id": book_id, "profile_id": profile_id},
    )
    if profile_id:
        await session.execute(
            text("UPDATE book_profile_link SET role='experiment' WHERE book_id=:book_id AND role='main' AND profile_id<>:profile_id"),
            {"book_id": book_id, "profile_id": profile_id},
        )
        await session.execute(
            text(
                """
                INSERT INTO book_profile_link(book_id, profile_id, role)
                VALUES (:book_id, :profile_id, 'main')
                ON CONFLICT (book_id, profile_id)
                DO UPDATE SET role='main'
                """
            ),
            {"book_id": book_id, "profile_id": profile_id},
        )
    else:
        await session.execute(
            text("UPDATE book_profile_link SET role='experiment' WHERE book_id=:book_id AND role='main'"),
            {"book_id": book_id},
        )
    await session.commit()
    row = result.mappings().first()
    return dict(row) if row else None


async def list_profile_versions(session: AsyncSession, profile_id: str, limit: int = 50) -> dict | None:
    prof = await get_profile(session, profile_id)
    if not prof:
        return None
    res = await session.execute(
        text(
            """
            SELECT profile_id, version, created_at, actor, action, note, parent_version, source_text_ver_ids
            FROM profile_version
            WHERE profile_id=:profile_id
            ORDER BY version DESC
            LIMIT :limit
            """
        ),
        {"profile_id": profile_id, "limit": max(1, min(int(limit), 200))},
    )
    return {
        "profile_id": profile_id,
        "active_version": int(prof.get("active_version") or 1),
        "items": [dict(r) for r in res.mappings().all()],
    }


async def get_profile_version(session: AsyncSession, profile_id: str, version: int) -> dict | None:
    res = await session.execute(
        text(
            """
            SELECT profile_id, version, snapshot, created_at, actor, action, note, parent_version, source_text_ver_ids
            FROM profile_version
            WHERE profile_id=:profile_id AND version=:version
            """
        ),
        {"profile_id": profile_id, "version": int(version)},
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def set_profile_active_version(
    session: AsyncSession,
    profile_id: str,
    version: int,
    *,
    note: str | None = None,
    actor: str = "desktop_user",
) -> dict | None:
    current = await get_profile(session, profile_id)
    if not current:
        return None
    target = await get_profile_version(session, profile_id, version)
    if not target:
        raise RuntimeError("PROFILE_VERSION_NOT_FOUND")
    snapshot = target.get("snapshot") or {}
    if not isinstance(snapshot, dict):
        raise RuntimeError("PROFILE_SNAPSHOT_INVALID")
    current_active = int(current.get("active_version") or 1)
    next_version = await _next_profile_version_no_commit(session, profile_id)
    await _insert_profile_version_no_commit(
        session,
        profile_id=profile_id,
        version=next_version,
        snapshot=snapshot,
        actor=actor,
        action="rollback",
        note=(note or "").strip() or f"rollback to v{version}",
        parent_version=current_active,
        source_text_ver_ids=[],
    )
    result = await session.execute(
        text(
            """
            UPDATE profile
            SET
              active_version=:active_version,
              name=:name,
              note=:note,
              features=CAST(:features AS jsonb),
              dos=CAST(:dos AS text[]),
              donts=CAST(:donts AS text[]),
              updated_at=now()
            WHERE profile_id=:profile_id
            RETURNING profile_id, name, note, active_version, features, dos, donts, created_at, updated_at
            """
        ),
        {
            "profile_id": profile_id,
            "active_version": next_version,
            "name": str(snapshot.get("name") or current.get("name") or ""),
            "note": str(snapshot.get("note") or current.get("note") or ""),
            "features": json.dumps(snapshot.get("features") if isinstance(snapshot.get("features"), dict) else {}),
            "dos": snapshot.get("dos") if isinstance(snapshot.get("dos"), list) else [],
            "donts": snapshot.get("donts") if isinstance(snapshot.get("donts"), list) else [],
        },
    )
    await session.commit()
    row = result.mappings().first()
    return dict(row) if row else None


async def diff_profile_versions(session: AsyncSession, profile_id: str, from_version: int, to_version: int) -> dict:
    from_row = await get_profile_version(session, profile_id, from_version)
    to_row = await get_profile_version(session, profile_id, to_version)
    if not from_row or not to_row:
        raise RuntimeError("PROFILE_VERSION_NOT_FOUND")
    return {
        "profile_id": profile_id,
        "from": int(from_version),
        "to": int(to_version),
        "changes": diff_settings(from_row.get("snapshot") or {}, to_row.get("snapshot") or {}),
    }


async def clone_profile(
    session: AsyncSession,
    profile_id: str,
    *,
    new_name: str,
    note: str | None = None,
    actor: str = "desktop_user",
) -> dict:
    current = await get_profile(session, profile_id)
    if not current:
        raise RuntimeError("PROFILE_NOT_FOUND")
    source_active = int(current.get("active_version") or 1)
    source_ver = await get_profile_version(session, profile_id, source_active)
    snapshot = (source_ver or {}).get("snapshot") if source_ver else None
    if not isinstance(snapshot, dict):
        snapshot = _profile_snapshot_from_row(current)
    res = await session.execute(
        text(
            """
            INSERT INTO profile(name, note, active_version, features, dos, donts, updated_at)
            VALUES (:name, :note, 1, CAST(:features AS jsonb), CAST(:dos AS text[]), CAST(:donts AS text[]), now())
            RETURNING profile_id, name, note, active_version, features, dos, donts, created_at, updated_at
            """
        ),
        {
            "name": new_name,
            "note": note if note is not None else (current.get("note") or ""),
            "features": json.dumps(snapshot.get("features") if isinstance(snapshot.get("features"), dict) else {}),
            "dos": snapshot.get("dos") if isinstance(snapshot.get("dos"), list) else [],
            "donts": snapshot.get("donts") if isinstance(snapshot.get("donts"), list) else [],
        },
    )
    row = dict(res.mappings().one())
    await _insert_profile_version_no_commit(
        session,
        profile_id=str(row["profile_id"]),
        version=1,
        snapshot=_profile_snapshot_from_row(row),
        actor=actor,
        action="create",
        note=(note or "").strip() or f"clone from {profile_id} v{source_active}",
        parent_version=None,
        source_text_ver_ids=[],
    )
    await session.commit()
    return row


async def add_book_profile_link(session: AsyncSession, book_id: str, profile_id: str, role: str = "experiment") -> dict:
    role_norm = "main" if role == "main" else "experiment"
    await session.execute(
        text(
            """
            INSERT INTO book_profile_link(book_id, profile_id, role)
            VALUES (:book_id, :profile_id, :role)
            ON CONFLICT (book_id, profile_id)
            DO UPDATE SET role=EXCLUDED.role
            """
        ),
        {"book_id": book_id, "profile_id": profile_id, "role": role_norm},
    )
    if role_norm == "main":
        await session.execute(
            text("UPDATE book SET profile_id=:profile_id, updated_at=now() WHERE book_id=:book_id"),
            {"book_id": book_id, "profile_id": profile_id},
        )
        await session.execute(
            text("UPDATE book_profile_link SET role='experiment' WHERE book_id=:book_id AND profile_id<>:profile_id AND role='main'"),
            {"book_id": book_id, "profile_id": profile_id},
        )
    await session.commit()
    res = await session.execute(
        text(
            """
            SELECT book_id, profile_id, role, created_at
            FROM book_profile_link
            WHERE book_id=:book_id AND profile_id=:profile_id
            """
        ),
        {"book_id": book_id, "profile_id": profile_id},
    )
    return dict(res.mappings().one())


async def list_book_profiles(session: AsyncSession, book_id: str) -> dict | None:
    book_res = await session.execute(
        text(
            """
            SELECT b.book_id, b.profile_id, p.name, p.active_version
            FROM book b
            LEFT JOIN profile p ON p.profile_id = b.profile_id
            WHERE b.book_id=:book_id
            """
        ),
        {"book_id": book_id},
    )
    book_row = book_res.mappings().first()
    if not book_row:
        return None
    exp_res = await session.execute(
        text(
            """
            SELECT l.profile_id, p.name, p.active_version, l.role, l.created_at
            FROM book_profile_link l
            JOIN profile p ON p.profile_id=l.profile_id
            WHERE l.book_id=:book_id
            ORDER BY CASE WHEN l.role='main' THEN 0 ELSE 1 END, l.created_at DESC
            """
        ),
        {"book_id": book_id},
    )
    items = [dict(r) for r in exp_res.mappings().all()]
    main_profile_id = str(book_row.get("profile_id")) if book_row.get("profile_id") else None
    experiments = [x for x in items if str(x.get("profile_id")) != str(main_profile_id)]
    main = None
    if main_profile_id:
        main = {
            "profile_id": main_profile_id,
            "name": book_row.get("name"),
            "active_version": int(book_row.get("active_version") or 1),
        }
    return {"book_id": book_id, "main": main, "experiments": experiments}


async def create_splitbook(
    session: AsyncSession,
    *,
    name: str,
    author: str | None = None,
    source_path: str | None = None,
    note: str | None = None,
) -> dict:
    result = await session.execute(
        text(
            """
            INSERT INTO splitbook(name, author, source_path, note)
            VALUES (:name, :author, :source_path, :note)
            RETURNING splitbook_id, name, author, source_path, note, ingest_status, embed_status, allow_guard, stats, created_at, updated_at
            """
        ),
        {"name": name, "author": author, "source_path": source_path, "note": note},
    )
    await session.commit()
    return dict(result.mappings().one())


async def list_splitbooks(session: AsyncSession, limit: int = 100) -> list[dict]:
    result = await session.execute(
        text(
            """
            SELECT splitbook_id, name, author, source_path, note, ingest_status, embed_status, allow_guard, stats, created_at, updated_at
            FROM splitbook
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"limit": max(1, min(int(limit), 500))},
    )
    return [dict(r) for r in result.mappings().all()]


async def get_splitbook(session: AsyncSession, splitbook_id: str) -> dict | None:
    result = await session.execute(
        text(
            """
            SELECT splitbook_id, name, author, source_path, note, ingest_status, embed_status, allow_guard, stats, created_at, updated_at
            FROM splitbook
            WHERE splitbook_id=:splitbook_id
            """
        ),
        {"splitbook_id": splitbook_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def update_splitbook_allow_guard(session: AsyncSession, splitbook_id: str, allow_guard: bool) -> dict | None:
    result = await session.execute(
        text(
            """
            UPDATE splitbook
            SET allow_guard=:allow_guard, updated_at=now()
            WHERE splitbook_id=:splitbook_id
            RETURNING splitbook_id, name, author, source_path, note, ingest_status, embed_status, allow_guard, stats, created_at, updated_at
            """
        ),
        {"splitbook_id": splitbook_id, "allow_guard": allow_guard},
    )
    await session.commit()
    row = result.mappings().first()
    return dict(row) if row else None


async def update_splitbook_status(
    session: AsyncSession,
    splitbook_id: str,
    *,
    ingest_status: str | None = None,
    embed_status: str | None = None,
    stats: dict | None = None,
) -> dict | None:
    current = await get_splitbook(session, splitbook_id)
    if not current:
        return None
    merged_stats = dict(current.get("stats") or {})
    if stats:
        merged_stats.update(stats)
    result = await session.execute(
        text(
            """
            UPDATE splitbook
            SET ingest_status=:ingest_status, embed_status=:embed_status, stats=CAST(:stats AS jsonb), updated_at=now()
            WHERE splitbook_id=:splitbook_id
            RETURNING splitbook_id, name, author, source_path, note, ingest_status, embed_status, allow_guard, stats, created_at, updated_at
            """
        ),
        {
            "splitbook_id": splitbook_id,
            "ingest_status": ingest_status if ingest_status is not None else current.get("ingest_status"),
            "embed_status": embed_status if embed_status is not None else current.get("embed_status"),
            "stats": json.dumps(merged_stats),
        },
    )
    await session.commit()
    row = result.mappings().first()
    return dict(row) if row else None


async def create_template(
    session: AsyncSession,
    profile_id: str,
    name: str,
    level: str,
    tags: list[str],
    schema_ver: int,
    graph: dict,
    meta: dict,
) -> dict:
    result = await session.execute(
        text(
            """
            INSERT INTO structure_template(profile_id, name, level, tags, schema_ver, graph, meta)
            VALUES (:profile_id, :name, :level, CAST(:tags AS text[]), :schema_ver, CAST(:graph AS jsonb), CAST(:meta AS jsonb))
            RETURNING template_id, profile_id, name, level, tags, schema_ver, graph, meta, created_at
            """
        ),
        {
            "profile_id": profile_id,
            "name": name,
            "level": level,
            "tags": tags,
            "schema_ver": schema_ver,
            "graph": json.dumps(graph),
            "meta": json.dumps(meta),
        },
    )
    await session.commit()
    return dict(result.mappings().one())


async def list_templates(session: AsyncSession, profile_id: str, level: str | None, tag: str | None) -> list[dict]:
    sql = """
        SELECT template_id, profile_id, name, level, tags, schema_ver, graph, meta, created_at
        FROM structure_template
        WHERE profile_id = :profile_id
    """
    params: dict = {"profile_id": profile_id}
    if level:
        sql += " AND level = :level"
        params["level"] = level
    if tag:
        sql += " AND :tag = ANY(tags)"
        params["tag"] = tag
    sql += " ORDER BY created_at DESC"
    result = await session.execute(text(sql), params)
    return [dict(r) for r in result.mappings().all()]


async def list_template_assets(
    session: AsyncSession,
    *,
    asset_type: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    sql = """
      SELECT asset_id, asset_type, name, description, tags, source_splitbook_id, source_span, created_at
      FROM template_asset
      WHERE 1=1
    """
    params: dict[str, object] = {"limit": max(1, min(int(limit), 200)), "offset": max(0, int(offset))}
    if asset_type:
        sql += " AND asset_type = :asset_type"
        params["asset_type"] = asset_type
    if tag:
        sql += " AND :tag = ANY(tags)"
        params["tag"] = tag
    if q and q.strip():
        sql += " AND (name ILIKE :contains OR description ILIKE :contains)"
        params["contains"] = f"%{q.strip()}%"
    sql += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
    res = await session.execute(text(sql), params)
    return [dict(r) for r in res.mappings().all()]


async def get_template_asset(session: AsyncSession, asset_id: str) -> dict | None:
    res = await session.execute(
        text(
            """
            SELECT asset_id, asset_type, name, description, tags, source_splitbook_id, source_span, created_at
            FROM template_asset
            WHERE asset_id=:asset_id
            """
        ),
        {"asset_id": asset_id},
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def log_template_usage(
    session: AsyncSession,
    template_id: str,
    book_id: str | None,
    chapter_id: str | None,
    usage_type: str,
    feedback: dict,
) -> dict:
    result = await session.execute(
        text(
            """
            INSERT INTO template_usage_log(template_id, book_id, chapter_id, usage_type, feedback)
            VALUES (:template_id, :book_id, :chapter_id, :usage_type, CAST(:feedback AS jsonb))
            RETURNING usage_id, template_id, book_id, chapter_id, usage_type, feedback, created_at
            """
        ),
        {
            "template_id": template_id,
            "book_id": book_id,
            "chapter_id": chapter_id,
            "usage_type": usage_type,
            "feedback": json.dumps(feedback),
        },
    )
    await session.commit()
    return dict(result.mappings().one())


async def recommend_templates(session: AsyncSession, profile_id: str, level: str | None, top_k: int) -> list[dict]:
    sql = """
      SELECT t.template_id, t.profile_id, t.name, t.level, t.tags, t.schema_ver, t.graph, t.meta, t.created_at,
             COUNT(u.usage_id) AS usage_count
      FROM structure_template t
      LEFT JOIN template_usage_log u ON u.template_id = t.template_id
      WHERE t.profile_id = :profile_id
    """
    params: dict = {"profile_id": profile_id, "top_k": top_k}
    if level:
        sql += " AND t.level = :level"
        params["level"] = level
    sql += " GROUP BY t.template_id ORDER BY usage_count DESC, t.created_at DESC LIMIT :top_k"
    result = await session.execute(text(sql), params)
    return [dict(r) for r in result.mappings().all()]


async def add_template_source(
    session: AsyncSession,
    template_id: str,
    source_book_id: str | None,
    source_chunk_ids: list[str],
    note: str | None,
) -> dict:
    result = await session.execute(
        text(
            """
            INSERT INTO structure_template_source(template_id, source_book_id, source_chunk_ids, note)
            VALUES (:template_id, :source_book_id, CAST(:source_chunk_ids AS uuid[]), :note)
            RETURNING template_source_id, template_id, source_book_id, source_chunk_ids, note
            """
        ),
        {
            "template_id": template_id,
            "source_book_id": source_book_id,
            "source_chunk_ids": source_chunk_ids,
            "note": note,
        },
    )
    await session.commit()
    return dict(result.mappings().one())


async def list_arc_targets(session: AsyncSession, book_id: str) -> list[dict]:
    res = await session.execute(
        text(
            """
            SELECT book_id, arc_id, target_shape, target_points, weights, created_at, updated_at
            FROM arc_target
            WHERE book_id=:book_id
            ORDER BY arc_id ASC
            """
        ),
        {"book_id": book_id},
    )
    return [dict(r) for r in res.mappings().all()]


async def upsert_arc_target(
    session: AsyncSession,
    *,
    book_id: str,
    arc_id: str,
    target_shape: str,
    target_points: list[float],
    weights: dict,
) -> dict:
    res = await session.execute(
        text(
            """
            INSERT INTO arc_target(book_id, arc_id, target_shape, target_points, weights)
            VALUES (:book_id, :arc_id, :target_shape, CAST(:target_points AS real[]), CAST(:weights AS jsonb))
            ON CONFLICT (book_id, arc_id)
            DO UPDATE SET
              target_shape=EXCLUDED.target_shape,
              target_points=EXCLUDED.target_points,
              weights=EXCLUDED.weights,
              updated_at=now()
            RETURNING book_id, arc_id, target_shape, target_points, weights, created_at, updated_at
            """
        ),
        {
            "book_id": book_id,
            "arc_id": arc_id,
            "target_shape": target_shape,
            "target_points": target_points,
            "weights": json.dumps(weights),
        },
    )
    await session.commit()
    return dict(res.mappings().one())


async def list_template_variants(
    session: AsyncSession,
    *,
    enabled: str = "all",
    base_template_id: str | None = None,
) -> list[dict]:
    sql = """
      SELECT variant_id, base_template_id, unique_key, name, scope, recipe, enabled, weight, stats, created_at
      FROM template_variant
      WHERE 1=1
    """
    params: dict[str, object] = {}
    if enabled == "true":
        sql += " AND enabled=true"
    elif enabled == "false":
        sql += " AND enabled=false"
    if base_template_id:
        sql += " AND base_template_id=:base_template_id"
        params["base_template_id"] = base_template_id
    sql += " ORDER BY created_at DESC"
    res = await session.execute(text(sql), params)
    return [dict(r) for r in res.mappings().all()]


async def get_template_variant(session: AsyncSession, variant_id: str) -> dict | None:
    res = await session.execute(
        text(
            """
            SELECT variant_id, base_template_id, unique_key, name, scope, recipe, enabled, weight, stats, created_at
            FROM template_variant
            WHERE variant_id=:variant_id
            """
        ),
        {"variant_id": variant_id},
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def set_template_variant_enabled(
    session: AsyncSession,
    *,
    variant_id: str,
    enabled: bool,
    weight: float | None = None,
) -> dict:
    if weight is None:
        res = await session.execute(
            text(
                """
                UPDATE template_variant
                SET enabled=:enabled
                WHERE variant_id=:variant_id
                RETURNING variant_id, base_template_id, unique_key, name, scope, recipe, enabled, weight, stats, created_at
                """
            ),
            {"variant_id": variant_id, "enabled": enabled},
        )
    else:
        res = await session.execute(
            text(
                """
                UPDATE template_variant
                SET enabled=:enabled, weight=:weight
                WHERE variant_id=:variant_id
                RETURNING variant_id, base_template_id, unique_key, name, scope, recipe, enabled, weight, stats, created_at
                """
            ),
            {"variant_id": variant_id, "enabled": enabled, "weight": float(weight)},
        )
    row = res.mappings().first()
    if not row:
        raise RuntimeError("VARIANT_NOT_FOUND")
    await session.commit()
    return dict(row)


async def create_repair_effect_sample(
    session: AsyncSession,
    *,
    book_id: str,
    arc_id: str | None,
    chapter_no: int,
    before_eval_run_id: str,
    after_eval_run_id: str,
    applied_mechanics: list[str],
    delta: dict,
    context: dict,
) -> dict:
    res = await session.execute(
        text(
            """
            INSERT INTO repair_effect_sample(
              book_id, arc_id, chapter_no, before_eval_run_id, after_eval_run_id,
              applied_mechanics, delta, context
            )
            VALUES (
              :book_id, :arc_id, :chapter_no, :before_eval_run_id, :after_eval_run_id,
              CAST(:applied_mechanics AS text[]), CAST(:delta AS jsonb), CAST(:context AS jsonb)
            )
            RETURNING sample_id, book_id, arc_id, chapter_no, before_eval_run_id, after_eval_run_id,
                      applied_mechanics, delta, context, created_at
            """
        ),
        {
            "book_id": book_id,
            "arc_id": arc_id,
            "chapter_no": chapter_no,
            "before_eval_run_id": before_eval_run_id,
            "after_eval_run_id": after_eval_run_id,
            "applied_mechanics": applied_mechanics,
            "delta": json.dumps(delta),
            "context": json.dumps(context),
        },
    )
    await session.commit()
    return dict(res.mappings().one())


async def list_material_cards(
    session: AsyncSession,
    *,
    book_id: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    sql = """
      SELECT card_id, book_id, source_type, title, content, tag, importance, created_at
      FROM material_card
      WHERE 1=1
    """
    params: dict[str, object] = {"limit": max(1, min(int(limit), 200)), "offset": max(0, int(offset))}
    if book_id:
        sql += " AND book_id = :book_id"
        params["book_id"] = book_id
    if tag:
        sql += " AND tag = :tag"
        params["tag"] = tag
    if q and q.strip():
        sql += " AND (title ILIKE :contains OR content ILIKE :contains)"
        params["contains"] = f"%{q.strip()}%"
    sql += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
    res = await session.execute(text(sql), params)
    return [dict(r) for r in res.mappings().all()]


async def create_material_card(
    session: AsyncSession,
    *,
    book_id: str | None,
    source_type: str,
    title: str,
    content: str,
    tag: str | None,
    importance: int,
) -> dict:
    res = await session.execute(
        text(
            """
            INSERT INTO material_card(book_id, source_type, title, content, tag, importance)
            VALUES (:book_id, :source_type, :title, :content, :tag, :importance)
            RETURNING card_id, book_id, source_type, title, content, tag, importance, created_at
            """
        ),
        {
            "book_id": book_id,
            "source_type": source_type,
            "title": title,
            "content": content,
            "tag": tag,
            "importance": int(importance),
        },
    )
    await session.commit()
    return dict(res.mappings().one())


async def get_material_card(session: AsyncSession, card_id: str) -> dict | None:
    res = await session.execute(
        text(
            """
            SELECT card_id, book_id, source_type, title, content, tag, importance, created_at
            FROM material_card
            WHERE card_id=:card_id
            """
        ),
        {"card_id": card_id},
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def delete_material_card(session: AsyncSession, card_id: str) -> bool:
    res = await session.execute(text("DELETE FROM material_card WHERE card_id=:card_id"), {"card_id": card_id})
    await session.commit()
    return bool(res.rowcount and res.rowcount > 0)


async def upsert_material_embedding(
    session: AsyncSession,
    *,
    card_id: str,
    embedding: list[float],
    model: str,
) -> dict:
    vec = "[" + ",".join(str(float(x)) for x in embedding) + "]"
    res = await session.execute(
        text(
            """
            INSERT INTO material_embedding(card_id, embedding, model, updated_at)
            VALUES (:card_id, CAST(:embedding AS vector), :model, now())
            ON CONFLICT (card_id)
            DO UPDATE SET embedding=EXCLUDED.embedding, model=EXCLUDED.model, updated_at=now()
            RETURNING card_id, model, updated_at
            """
        ),
        {"card_id": card_id, "embedding": vec, "model": model},
    )
    await session.commit()
    return dict(res.mappings().one())


async def search_material_knn(
    session: AsyncSession,
    *,
    query_embedding: list[float],
    k: int = 20,
    book_id: str | None = None,
    tag: str | None = None,
) -> list[dict]:
    sql = """
      SELECT
        c.card_id,
        c.book_id,
        c.source_type,
        c.title,
        c.content,
        c.tag,
        c.importance,
        c.created_at,
        1 - (e.embedding <=> CAST(:qvec AS vector)) AS score
      FROM material_card c
      JOIN material_embedding e ON e.card_id = c.card_id
      WHERE 1=1
    """
    params: dict[str, object] = {
        "qvec": "[" + ",".join(str(float(x)) for x in query_embedding) + "]",
        "k": max(1, min(int(k), 100)),
    }
    if book_id:
        sql += " AND c.book_id = :book_id"
        params["book_id"] = book_id
    if tag:
        sql += " AND c.tag = :tag"
        params["tag"] = tag
    sql += " ORDER BY e.embedding <=> CAST(:qvec AS vector) LIMIT :k"
    res = await session.execute(text(sql), params)
    return [dict(r) for r in res.mappings().all()]


async def import_material_cards_from_chunks(
    session: AsyncSession,
    *,
    book_id: str,
    source_id: str | None = None,
    tag: str | None = None,
    limit: int = 100,
    source_type: str = "splitbook",
    importance: int = 3,
) -> list[str]:
    sql = """
      INSERT INTO material_card(book_id, source_type, title, content, tag, importance)
      SELECT
        c.book_id,
        :source_type,
        ('chunk #' || c.index_in_chapter || ' - ' || COALESCE(ch.title, 'untitled')) AS title,
        c.text AS content,
        :tag AS tag,
        :importance AS importance
      FROM chunk c
      LEFT JOIN chapter ch ON ch.chapter_id = c.chapter_id
      WHERE c.book_id = :book_id
    """
    params: dict[str, object] = {
        "book_id": book_id,
        "source_type": source_type,
        "tag": tag,
        "importance": int(importance),
        "limit": max(1, min(int(limit), 1000)),
    }
    if source_id:
        sql += " AND c.source_id = :source_id"
        params["source_id"] = source_id
    sql += " ORDER BY c.created_at DESC LIMIT :limit RETURNING card_id"
    res = await session.execute(text(sql), params)
    await session.commit()
    return [str(r["card_id"]) for r in res.mappings().all()]


async def create_ref_inbox_item(
    session: AsyncSession,
    *,
    chapter_id: str,
    source_type: str,
    source_id: str | None,
    title: str,
    tag: str | None,
    ref_block: str,
    extracted_points: list[dict],
    status: str = "new",
    sort_key: int = 1000,
) -> dict:
    chapter_row = await session.execute(
        text("SELECT book_id FROM chapter WHERE chapter_id=:chapter_id"),
        {"chapter_id": chapter_id},
    )
    book_id = chapter_row.scalar()
    if not book_id:
        raise RuntimeError("CHAPTER_NOT_FOUND")
    res = await session.execute(
        text(
            """
            INSERT INTO chapter_ref_inbox(
              book_id, chapter_id, source_type, source_id, title, tag,
              ref_block, extracted_points, status, sort_key
            )
            VALUES (
              :book_id, :chapter_id, :source_type, :source_id, :title, :tag,
              :ref_block, CAST(:extracted_points AS jsonb), :status, :sort_key
            )
            RETURNING
              ref_id, book_id, chapter_id, source_type, source_id, title, tag,
              ref_block, extracted_points, status, used_at, sort_key, created_at
            """
        ),
        {
            "book_id": str(book_id),
            "chapter_id": chapter_id,
            "source_type": source_type,
            "source_id": source_id,
            "title": title,
            "tag": tag,
            "ref_block": ref_block,
            "extracted_points": json.dumps(extracted_points, ensure_ascii=False),
            "status": status,
            "sort_key": int(sort_key),
        },
    )
    await session.commit()
    return dict(res.mappings().one())


async def list_ref_inbox_items(
    session: AsyncSession,
    *,
    chapter_id: str,
    status: str | None = None,
    limit: int = 100,
) -> list[dict]:
    sql = """
      SELECT
        ref_id, book_id, chapter_id, source_type, source_id, title, tag,
        ref_block, extracted_points, status, used_at, sort_key, created_at
      FROM chapter_ref_inbox
      WHERE chapter_id=:chapter_id
    """
    params: dict[str, object] = {"chapter_id": chapter_id, "limit": max(1, min(int(limit), 200))}
    if status:
        sql += " AND status=:status"
        params["status"] = status
    sql += " ORDER BY status ASC, sort_key ASC, created_at DESC LIMIT :limit"
    res = await session.execute(text(sql), params)
    return [dict(r) for r in res.mappings().all()]


async def set_ref_inbox_status(
    session: AsyncSession,
    *,
    ref_id: str,
    status: str,
) -> dict | None:
    res = await session.execute(
        text(
            """
            UPDATE chapter_ref_inbox
            SET status=:status,
                used_at = CASE WHEN :status='used' THEN now() ELSE NULL END
            WHERE ref_id=:ref_id
            RETURNING
              ref_id, book_id, chapter_id, source_type, source_id, title, tag,
              ref_block, extracted_points, status, used_at, sort_key, created_at
            """
        ),
        {"ref_id": ref_id, "status": status},
    )
    row = res.mappings().first()
    await session.commit()
    return dict(row) if row else None
