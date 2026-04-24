-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE leads (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  company_name TEXT NOT NULL,
  vertical TEXT CHECK (vertical IN ('restaurant', 'vet', 'dermatologist')),
  geography TEXT,
  website TEXT,
  status TEXT DEFAULT 'new' CHECK (status IN (
    'new', 'researching', 'drafted', 'sent', 'meeting_set', 'dead'
  )),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE contacts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  role TEXT,
  email TEXT,
  phone TEXT,
  linkedin_url TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE emails (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  contact_id UUID REFERENCES contacts(id) ON DELETE CASCADE,
  subject TEXT,
  body TEXT,
  status TEXT DEFAULT 'draft' CHECK (status IN (
    'draft', 'approved', 'sent', 'bounced', 'replied'
  )),
  sent_at TIMESTAMP,
  reply_received BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE meetings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  contact_id UUID REFERENCES contacts(id),
  scheduled_at TIMESTAMP,
  transcript TEXT,
  prd_generated TEXT,
  prototype_url TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_emails_status ON emails(status);

-- Auto-update updated_at on leads
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER leads_updated_at
  BEFORE UPDATE ON leads
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
