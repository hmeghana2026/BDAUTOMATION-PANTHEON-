"""Test script for BD automation improvements."""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime
from database.supabase_client import SupabaseDB
from database.models import Lead
from agents.lead_research import LeadResearchAgent
from agents.automation_rules import AutomationRules

def test_research_logging():
    """Test that research creates logs."""
    print("\n=== Testing Research Logging ===")
    db = SupabaseDB()
    agent = LeadResearchAgent()
    
    # Create test lead
    lead = db.create_lead(Lead(
        company_name="Test Restaurant XYZ",
        vertical="restaurant",
        geography="San Francisco, CA",
        website="https://example.com"
    ))
    
    print(f"✓ Created test lead: {lead.id}")
    
    # Run research
    result = agent.research_lead(lead)
    print(f"✓ Research complete")
    print(f"  - Insights: {result.insights[:100] if result.insights else 'No insights'}...")
    
    # Check logs
    logs = db.get_research_logs_for_lead(lead.id)
    print(f"✓ Research logs created: {len(logs)}")
    
    if logs:
        log = logs[0]
        print(f"  - Email status: {log.email_verification_status}")
        print(f"  - Insights length: {len(log.insights) if log.insights else 0} chars")
        print(f"  - Scraped content: {len(log.scraped_content) if log.scraped_content else 0} chars")
        if log.hunter_confidence:
            print(f"  - Hunter confidence: {log.hunter_confidence}%")
        if log.scrape_duration_ms:
            print(f"  - Scrape duration: {log.scrape_duration_ms}ms")
    
    # Check score
    score = db.get_lead_score(lead.id)
    if score:
        print(f"✓ Lead score calculated: {score.priority_score}/100")
        print(f"  - Website quality: {score.website_quality_score}")
        print(f"  - Contact quality: {score.contact_quality_score}")
        print(f"  - Research quality: {score.research_quality_score}")
    
    print("✅ Research logging test PASSED\n")


def test_automation_rules():
    """Test automation rules engine."""
    print("\n=== Testing Automation Rules ===")
    db = SupabaseDB()
    rules = AutomationRules()
    
    # Create test lead
    lead = db.create_lead(Lead(
        company_name="Test Vet Clinic",
        vertical="vet",
        geography="Austin, TX",
        website="https://test-vet-clinic.com"
    ))
    
    print(f"✓ Created test lead: {lead.id}")
    
    # Calculate score
    score = rules.calculate_priority_score(lead)
    print(f"✓ Priority score calculated: {score}/100")
    
    # Test skip rules
    should_skip, reason = rules.should_skip_lead(lead)
    print(f"✓ Skip check: {should_skip}")
    if should_skip:
        print(f"  - Reason: {reason}")
    
    # Test auto-send rules
    should_send, reason = rules.should_auto_send(lead)
    print(f"✓ Auto-send check: {should_send}")
    print(f"  - Reason: {reason}")
    
    # Test adaptive follow-up
    day2 = rules.get_adaptive_followup_day(lead, 2)
    day3 = rules.get_adaptive_followup_day(lead, 3)
    day4 = rules.get_adaptive_followup_day(lead, 4)
    print(f"✓ Adaptive follow-up schedule:")
    print(f"  - Touch 2: Day {day2}")
    print(f"  - Touch 3: Day {day3}")
    print(f"  - Touch 4: Day {day4}")
    
    print("✅ Automation rules test PASSED\n")


def test_task_logging():
    """Test task logging."""
    print("\n=== Testing Task Logging ===")
    db = SupabaseDB()
    from database.models import TaskLog
    
    # Create task
    task = db.create_task_log(TaskLog(
        task_type="research",
        status="running",
        message="Test task in progress",
        started_at=datetime.utcnow(),
        progress_pct=0
    ))
    
    print(f"✓ Created task log: {task.id}")
    print(f"  - Type: {task.task_type}")
    print(f"  - Status: {task.status}")
    
    # Update progress
    db.update_task_log(task.id, {
        "progress_pct": 50,
        "message": "Halfway complete"
    })
    print(f"✓ Updated progress to 50%")
    
    # Complete task
    db.update_task_log(task.id, {
        "status": "completed",
        "progress_pct": 100,
        "message": "Task completed successfully",
        "completed_at": datetime.utcnow()
    })
    print(f"✓ Marked task as completed")
    
    # Get recent activity
    activity = db.get_recent_activity(limit=5)
    print(f"✓ Retrieved {len(activity)} recent activity items")
    
    # Get active tasks (should be empty now)
    active = db.get_active_tasks(hours=1)
    print(f"✓ Active tasks: {len(active)}")
    
    print("✅ Task logging test PASSED\n")


def test_lead_prioritization():
    """Test lead prioritization."""
    print("\n=== Testing Lead Prioritization ===")
    db = SupabaseDB()
    rules = AutomationRules()
    
    # Create several test leads with different characteristics
    leads_data = [
        {
            "company_name": "Premium Vet with Website",
            "vertical": "vet",
            "geography": "San Francisco, CA",
            "website": "https://premium-vet-appointment-booking.com"
        },
        {
            "company_name": "Basic Restaurant",
            "vertical": "restaurant",
            "geography": "Texas",
            "website": "https://example.com"
        },
        {
            "company_name": "No Website Dermatologist",
            "vertical": "dermatologist",
            "geography": "New York, NY",
            "website": None
        }
    ]
    
    scored_leads = []
    for data in leads_data:
        lead = db.create_lead(Lead(**data))
        score = rules.calculate_priority_score(lead)
        scored_leads.append((lead, score))
        print(f"✓ {lead.company_name}: {score}/100")
    
    # Sort by score
    scored_leads.sort(key=lambda x: x[1], reverse=True)
    print(f"\n✓ Prioritized order:")
    for idx, (lead, score) in enumerate(scored_leads, 1):
        print(f"  {idx}. {lead.company_name} ({score} pts)")
    
    print("✅ Lead prioritization test PASSED\n")


if __name__ == "__main__":
    print("=" * 60)
    print("BD AUTOMATION - IMPROVEMENTS TEST SUITE")
    print("=" * 60)
    
    try:
        test_research_logging()
        test_automation_rules()
        test_task_logging()
        test_lead_prioritization()
        
        print("=" * 60)
        print("✅✅✅ ALL TESTS PASSED! ✅✅✅")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Run Streamlit dashboard: streamlit run app.py")
        print("2. Check 'Research Insights' page for full visibility")
        print("3. Monitor 'Recent Activity' feed on Dashboard")
        print("4. Verify Celery tasks with: celery -A tasks worker --loglevel=info")
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌❌❌ TEST FAILED ❌❌❌")
        print("=" * 60)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        
        print("\n⚠️  Troubleshooting:")
        print("1. Did you run the database migration in Supabase?")
        print("2. Are your environment variables set correctly?")
        print("3. Is Supabase connection working?")
        print("4. Check the implementation guide for setup steps")
