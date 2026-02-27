-- ==============
-- Extensions
-- ==============
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Optional: pgvector (if installed)
-- CREATE EXTENSION IF NOT EXISTS vector;

-- ==============
-- Enums / Types
-- ==============
DO $$ BEGIN
  CREATE TYPE entity_type_enum AS ENUM (
    'character','location','faction','artifact','pathway','skill','ritual','organization','other'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE fact_type_enum AS ENUM (
    'pathway','sequence','potion_recipe','ritual','rule','warning','pollution','organization','artifact','ability','other'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE conflict_type_enum AS ENUM (
    'man_vs_man','man_vs_self','man_vs_world','man_vs_system','man_vs_unknown','none'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE pair_type_enum AS ENUM (
    'direct','indirect','twist','subversion','false_lead'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE job_status_enum AS ENUM (
    'queued','running','succeeded','failed'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ==============
-- Core: book / chapter / scene / chunk
-- ==============
CREATE TABLE IF NOT EXISTS book (
  book_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text NOT NULL,
  meta        jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chapter (
  chapter_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id      uuid NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  chapter_no   int  NOT NULL,
  title        text NOT NULL DEFAULT '',
  start_offset int  NOT NULL DEFAULT 0,
  end_offset   int  NOT NULL DEFAULT 0,
  text_hash    text NOT NULL DEFAULT '',
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE(book_id, chapter_no)
);

CREATE INDEX IF NOT EXISTS idx_chapter_book ON chapter(book_id);

CREATE TABLE IF NOT EXISTS scene (
  scene_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id       uuid NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  chapter_id    uuid NOT NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  chapter_no    int  NOT NULL,
  scene_no      int  NOT NULL,
  start_offset  int  NOT NULL,
  end_offset    int  NOT NULL,
  text_hash     text NOT NULL DEFAULT '',
  segmentation_reason jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE(book_id, chapter_no, scene_no)
);

CREATE INDEX IF NOT EXISTS idx_scene_book_chapter ON scene(book_id, chapter_no);
CREATE INDEX IF NOT EXISTS idx_scene_chapter ON scene(chapter_id);

-- Store evidence text (recommended). If you already store raw text elsewhere, keep chunk minimal.
CREATE TABLE IF NOT EXISTS chunk (
  chunk_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scene_id     uuid NOT NULL REFERENCES scene(scene_id) ON DELETE CASCADE,
  idx          int  NOT NULL DEFAULT 0,
  start_offset int  NOT NULL,
  end_offset   int  NOT NULL,
  text         text NOT NULL,
  text_hash    text NOT NULL DEFAULT '',
  UNIQUE(scene_id, idx)
);

CREATE INDEX IF NOT EXISTS idx_chunk_scene ON chunk(scene_id);

-- ==============
-- Entities (canonicalization + mentions)
-- ==============
CREATE TABLE IF NOT EXISTS entity (
  entity_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id      uuid NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  entity_type  entity_type_enum NOT NULL,
  canonical_name text NOT NULL,
  aliases      text[] NOT NULL DEFAULT ARRAY[]::text[],
  first_seen_scene_id uuid NULL,
  last_seen_scene_id  uuid NULL,
  attributes   jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE(book_id, entity_type, canonical_name)
);

CREATE INDEX IF NOT EXISTS idx_entity_book_type ON entity(book_id, entity_type);

CREATE TABLE IF NOT EXISTS entity_mention (
  mention_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id    uuid NOT NULL REFERENCES entity(entity_id) ON DELETE CASCADE,
  scene_id     uuid NOT NULL REFERENCES scene(scene_id) ON DELETE CASCADE,
  chunk_id     uuid NULL REFERENCES chunk(chunk_id) ON DELETE SET NULL,
  surface      text NOT NULL,
  start_offset int  NOT NULL,
  end_offset   int  NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_entity_mention_scene ON entity_mention(scene_id);
CREATE INDEX IF NOT EXISTS idx_entity_mention_entity ON entity_mention(entity_id);

-- ==============
-- SceneRecord (raw JSON output for debugging/replay)
-- ==============
CREATE TABLE IF NOT EXISTS scene_record (
  scene_id     uuid PRIMARY KEY REFERENCES scene(scene_id) ON DELETE CASCADE,
  record       jsonb NOT NULL,
  schema_version text NOT NULL DEFAULT 'scenerecord.v1',
  prompt_version text NOT NULL DEFAULT 'extract.v1',
  model_id     text NOT NULL DEFAULT '',
  confidence_overall float NOT NULL DEFAULT 0.0,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

-- ==============
-- Facts / Events / Conflict
-- ==============
CREATE TABLE IF NOT EXISTS fact (
  fact_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id      uuid NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  scene_id     uuid NOT NULL REFERENCES scene(scene_id) ON DELETE CASCADE,
  fact_type    fact_type_enum NOT NULL,
  subject      text NOT NULL DEFAULT '',
  predicate    text NOT NULL DEFAULT '',
  object       text NOT NULL DEFAULT '',
  constraints  text NOT NULL DEFAULT '',
  cost_or_risk text NOT NULL DEFAULT '',
  importance   int  NOT NULL DEFAULT 1 CHECK (importance >= 0 AND importance <= 3),
  confidence   float NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
  evidence     jsonb NOT NULL DEFAULT '[]'::jsonb,
  entity_refs  uuid[] NOT NULL DEFAULT ARRAY[]::uuid[],
  schema_version text NOT NULL DEFAULT 'fact.v1',
  prompt_version text NOT NULL DEFAULT 'extract.v1',
  model_id     text NOT NULL DEFAULT '',
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fact_book_type ON fact(book_id, fact_type);
CREATE INDEX IF NOT EXISTS idx_fact_scene ON fact(scene_id);
CREATE INDEX IF NOT EXISTS idx_fact_importance ON fact(book_id, importance);

CREATE TABLE IF NOT EXISTS event (
  event_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id      uuid NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  scene_id     uuid NOT NULL REFERENCES scene(scene_id) ON DELETE CASCADE,
  beat         text NOT NULL DEFAULT '',
  what         text NOT NULL DEFAULT '',
  cause        text NOT NULL DEFAULT '',
  result       text NOT NULL DEFAULT '',
  tension_score int NOT NULL DEFAULT 0 CHECK (tension_score >= 0 AND tension_score <= 10),
  importance   int  NOT NULL DEFAULT 1 CHECK (importance >= 0 AND importance <= 3),
  confidence   float NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
  evidence     jsonb NOT NULL DEFAULT '[]'::jsonb,
  schema_version text NOT NULL DEFAULT 'event.v1',
  prompt_version text NOT NULL DEFAULT 'extract.v1',
  model_id     text NOT NULL DEFAULT '',
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_event_book ON event(book_id);
CREATE INDEX IF NOT EXISTS idx_event_scene ON event(scene_id);
CREATE INDEX IF NOT EXISTS idx_event_tension ON event(book_id, tension_score);

CREATE TABLE IF NOT EXISTS conflict (
  scene_id     uuid PRIMARY KEY REFERENCES scene(scene_id) ON DELETE CASCADE,
  conflict_type conflict_type_enum NOT NULL DEFAULT 'none',
  side_a_goal  text NOT NULL DEFAULT '',
  side_b_goal  text NOT NULL DEFAULT '',
  stakes       text NOT NULL DEFAULT '',
  escalation   text NOT NULL DEFAULT '',
  turning_point text NOT NULL DEFAULT '',
  outcome      text NOT NULL DEFAULT '',
  tension_score int NOT NULL DEFAULT 0 CHECK (tension_score >= 0 AND tension_score <= 10),
  confidence   float NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
  evidence     jsonb NOT NULL DEFAULT '[]'::jsonb,
  schema_version text NOT NULL DEFAULT 'conflict.v1',
  prompt_version text NOT NULL DEFAULT 'extract.v1',
  model_id     text NOT NULL DEFAULT '',
  updated_at   timestamptz NOT NULL DEFAULT now()
);

-- ==============
-- Foreshadow / Payoff / Pair graph
-- ==============
CREATE TABLE IF NOT EXISTS foreshadow_seed (
  seed_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id      uuid NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  scene_id     uuid NOT NULL REFERENCES scene(scene_id) ON DELETE CASCADE,
  seed         text NOT NULL DEFAULT '',
  why          text NOT NULL DEFAULT '',
  promise      text NOT NULL DEFAULT '',
  importance   int  NOT NULL DEFAULT 1 CHECK (importance >= 0 AND importance <= 3),
  confidence   float NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
  entity_tags  text[] NOT NULL DEFAULT ARRAY[]::text[],
  evidence     jsonb NOT NULL DEFAULT '[]'::jsonb,
  schema_version text NOT NULL DEFAULT 'seed.v1',
  prompt_version text NOT NULL DEFAULT 'extract.v1',
  model_id     text NOT NULL DEFAULT '',
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_seed_book ON foreshadow_seed(book_id);
CREATE INDEX IF NOT EXISTS idx_seed_scene ON foreshadow_seed(scene_id);
CREATE INDEX IF NOT EXISTS idx_seed_importance ON foreshadow_seed(book_id, importance);

CREATE TABLE IF NOT EXISTS payoff_candidate (
  payoff_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id      uuid NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  scene_id     uuid NOT NULL REFERENCES scene(scene_id) ON DELETE CASCADE,
  payoff       text NOT NULL DEFAULT '',
  trigger      text NOT NULL DEFAULT '',
  effect       text NOT NULL DEFAULT '',
  resolves     text NOT NULL DEFAULT '',
  importance   int  NOT NULL DEFAULT 1 CHECK (importance >= 0 AND importance <= 3),
  confidence   float NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
  entity_tags  text[] NOT NULL DEFAULT ARRAY[]::text[],
  evidence     jsonb NOT NULL DEFAULT '[]'::jsonb,
  schema_version text NOT NULL DEFAULT 'payoff.v1',
  prompt_version text NOT NULL DEFAULT 'extract.v1',
  model_id     text NOT NULL DEFAULT '',
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payoff_book ON payoff_candidate(book_id);
CREATE INDEX IF NOT EXISTS idx_payoff_scene ON payoff_candidate(scene_id);
CREATE INDEX IF NOT EXISTS idx_payoff_importance ON payoff_candidate(book_id, importance);

CREATE TABLE IF NOT EXISTS foreshadow_pair (
  pair_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id      uuid NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  seed_id      uuid NOT NULL REFERENCES foreshadow_seed(seed_id) ON DELETE CASCADE,
  payoff_id    uuid NOT NULL REFERENCES payoff_candidate(payoff_id) ON DELETE CASCADE,
  pair_type    pair_type_enum NOT NULL DEFAULT 'direct',
  confidence   float NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
  rationale    text NOT NULL DEFAULT '',
  evidence     jsonb NOT NULL DEFAULT '{}'::jsonb,
  schema_version text NOT NULL DEFAULT 'pair.v1',
  prompt_version text NOT NULL DEFAULT 'pair.v1',
  model_id     text NOT NULL DEFAULT '',
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE(book_id, seed_id, payoff_id)
);

CREATE INDEX IF NOT EXISTS idx_pair_book ON foreshadow_pair(book_id);
CREATE INDEX IF NOT EXISTS idx_pair_seed ON foreshadow_pair(seed_id);
CREATE INDEX IF NOT EXISTS idx_pair_payoff ON foreshadow_pair(payoff_id);

-- ==============
-- Embeddings (optional, needs pgvector)
-- ==============
-- If you use pgvector, uncomment:
-- CREATE TABLE IF NOT EXISTS embedding (
--   emb_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
--   book_id     uuid NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
--   item_type   text NOT NULL, -- seed/payoff/fact/event/chunk
--   item_id     uuid NOT NULL,
--   model       text NOT NULL DEFAULT '',
--   vector      vector(1024),  -- change dimension to your embedding model
--   text        text NOT NULL DEFAULT '',
--   created_at  timestamptz NOT NULL DEFAULT now(),
--   UNIQUE(book_id, item_type, item_id, model)
-- );
-- CREATE INDEX IF NOT EXISTS idx_embedding_book ON embedding(book_id);
-- CREATE INDEX IF NOT EXISTS idx_embedding_item ON embedding(item_type, item_id);

-- ==============
-- Job System
-- ==============
CREATE TABLE IF NOT EXISTS job (
  job_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  type       text NOT NULL,
  book_id    uuid NOT NULL REFERENCES book(book_id) ON DELETE CASCADE,
  chapter_id uuid NULL REFERENCES chapter(chapter_id) ON DELETE CASCADE,
  scene_id   uuid NULL REFERENCES scene(scene_id) ON DELETE CASCADE,
  status     job_status_enum NOT NULL DEFAULT 'queued',
  payload    jsonb NOT NULL DEFAULT '{}'::jsonb,
  result     jsonb NOT NULL DEFAULT '{}'::jsonb,
  error      text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_job_book_status ON job(book_id, status);
CREATE INDEX IF NOT EXISTS idx_job_type_status ON job(type, status);
CREATE INDEX IF NOT EXISTS idx_job_scene ON job(scene_id);

-- ==============
-- Convenience: trigger to auto-update updated_at
-- ==============
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
  CREATE TRIGGER trg_scene_record_updated
  BEFORE UPDATE ON scene_record
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TRIGGER trg_job_updated
  BEFORE UPDATE ON job
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TRIGGER trg_conflict_updated
  BEFORE UPDATE ON conflict
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
