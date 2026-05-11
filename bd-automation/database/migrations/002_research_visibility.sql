-- BD Automation Platform - Research Visibility & Task Logging Migration
-- Run this in Supabase SQL Editor

-- Research logs table for full visibility into agent findings
CREATE TABLE IF NOT EXISTS research_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
  scraped_content TEXT,
  extracted_data JSONB,
  insights TEXT,
  email_verification_status TEXT CHECK (email_verification_status IN (
    'not_found', 'verified', 'unverified', 'skipped'
  )),
  hunter_confidence INTEGER,
  scrape_duration_ms INTEGER,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Task execution logs for real-time progress tracking
CREATE TABLE IF NOT EXISTS task_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id UUID REFERENCES leads(id) ON DELETE SET NULL,
  task_type TEXT CHECK (task_type IN (
    'research', 'draft', 'send', 'followup', 'cleanup'
  )),
  status TEXT CHECK (status IN (
    'pending', 'running', 'completed', 'failed'
  )),
  progress_pct INTEGER DEFAULT 0 CHECK (progress_pct >= 0 AND progress_pct <= 100),
  message TEXT,
  error_details TEXT,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Lead priority scores for smart sequencing
CREATE TABLE IF NOT EXISTS lead_scores (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id UUID REFERENCES leads(id) ON DELETE CASCADE UNIQUE,
  priority_score INTEGER DEFAULT 50 CHECK (priority_score >= 0 AND priority_score <= 100),
  website_quality_score INTEGER DEFAULT 0,
  contact_quality_score INTEGER DEFAULT 0,
  research_quality_score INTEGER DEFAULT 0,
  last_calculated TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_research_logs_lead ON research_logs(lead_id);
CREATE INDEX IF NOT EXISTS idx_research_logs_created ON research_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_task_logs_lead ON task_logs(lead_id);
CREATE INDEX IF NOT EXISTS idx_task_logs_status ON task_logs(status);
CREATE INDEX IF NOT EXISTS idx_task_logs_created ON task_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_lead_scores_priority ON lead_scores(priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_lead_scores_lead ON lead_scores(lead_id);

-- Auto-update trigger for lead_scores
CREATE OR REPLACE FUNCTION update_lead_score_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.last_calculated = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS lead_scores_updated ON lead_scores;
CREATE TRIGGER lead_scores_updated
  BEFORE UPDATE ON lead_scores
  FOR EACH ROW EXECUTE FUNCTION update_lead_score_timestamp();

-- Verify tables were created
DO $$
BEGIN
  RAISE NOTICE 'Migration complete! Created tables:';
  RAISE NOTICE '  - research_logs';
  RAISE NOTICE '  - task_logs';
  RAISE NOTICE '  - lead_scores';
  RAISE NOTICE 'Next step: Update Python code with new models and methods';
END $$;
