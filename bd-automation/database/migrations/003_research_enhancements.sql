-- Migration 003: Research Enhancements
-- Adds tables for tiered enrichment, competitor analysis, pain point mining,
-- and signal-based scoring. Also extends lead_scores with a signal_score column.

-- ── signal_templates ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS signal_templates (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vertical    TEXT NOT NULL,
    name        TEXT NOT NULL,
    signals     JSONB NOT NULL DEFAULT '[]',
    min_score   INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signal_templates_vertical ON signal_templates (vertical);

-- ── tiered_research_results ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tiered_research_results (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id     UUID NOT NULL REFERENCES leads (id) ON DELETE CASCADE,
    tiers_run   INTEGER[] NOT NULL DEFAULT '{}',
    results     JSONB NOT NULL DEFAULT '{}',
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tiered_research_lead_id ON tiered_research_results (lead_id);
CREATE INDEX IF NOT EXISTS idx_tiered_research_executed_at ON tiered_research_results (executed_at DESC);

-- ── competitor_analyses ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS competitor_analyses (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id          UUID NOT NULL REFERENCES leads (id) ON DELETE CASCADE,
    config           JSONB NOT NULL DEFAULT '{}',
    competitors      JSONB NOT NULL DEFAULT '[]',
    capability_gaps  JSONB NOT NULL DEFAULT '[]',
    outreach_points  JSONB NOT NULL DEFAULT '[]',
    generated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_competitor_analyses_lead_id ON competitor_analyses (lead_id);
CREATE INDEX IF NOT EXISTS idx_competitor_analyses_generated_at ON competitor_analyses (generated_at DESC);

-- ── pain_point_analyses ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pain_point_analyses (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id               UUID NOT NULL REFERENCES leads (id) ON DELETE CASCADE,
    reviews_analyzed      INTEGER NOT NULL DEFAULT 0,
    pain_points           JSONB NOT NULL DEFAULT '[]',
    solution_mapping      JSONB NOT NULL DEFAULT '[]',
    outreach_intelligence JSONB NOT NULL DEFAULT '{}',
    generated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pain_point_analyses_lead_id ON pain_point_analyses (lead_id);
CREATE INDEX IF NOT EXISTS idx_pain_point_analyses_generated_at ON pain_point_analyses (generated_at DESC);

-- ── extend lead_scores with signal_score ─────────────────────────────────────
ALTER TABLE lead_scores
    ADD COLUMN IF NOT EXISTS signal_score INTEGER DEFAULT 0;
