-- V2: Tables for bulk discovery and SMS
CREATE TABLE discovery_campaigns (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  business_type TEXT NOT NULL,
  geographic_center TEXT NOT NULL,
  radius_miles NUMERIC,
  max_results INTEGER DEFAULT 50,
  status TEXT DEFAULT 'discovering' CHECK (status IN (
    'discovering', 'pending_approval', 'approved', 'rejected'
  )),
  discovered_count INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE discovered_businesses (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id UUID REFERENCES discovery_campaigns(id) ON DELETE CASCADE,
  business_name TEXT NOT NULL,
  address TEXT,
  phone TEXT,
  website TEXT,
  email TEXT,
  rating NUMERIC,
  distance_miles NUMERIC,
  channel TEXT CHECK (channel IN ('email', 'sms', 'both', 'none')),
  approved BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sms_messages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  contact_id UUID REFERENCES contacts(id) ON DELETE CASCADE,
  phone_number TEXT NOT NULL,
  message_body TEXT,
  status TEXT DEFAULT 'draft' CHECK (status IN (
    'draft', 'approved', 'sent', 'delivered', 'failed', 'replied'
  )),
  sent_at TIMESTAMP,
  twilio_sid TEXT,
  reply_received BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_campaigns_status ON discovery_campaigns(status);
CREATE INDEX idx_discovered_campaign ON discovered_businesses(campaign_id);
CREATE INDEX idx_discovered_approved ON discovered_businesses(approved);
CREATE INDEX idx_sms_status ON sms_messages(status);
CREATE INDEX idx_sms_contact ON sms_messages(contact_id);

-- Auto-update updated_at on discovery_campaigns
CREATE TRIGGER discovery_campaigns_updated_at
  BEFORE UPDATE ON discovery_campaigns
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
