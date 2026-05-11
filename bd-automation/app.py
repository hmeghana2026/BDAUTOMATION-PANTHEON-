"""Streamlit dashboard for BD Automation Platform — Nothing Design System."""
import os
import sys
import logging
import streamlit as st
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Page config & design system ──────────────────────────────────────────────

st.set_page_config(
    page_title="BD Automation",
    page_icon="⚫",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_design_system():
    st.markdown("""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Doto:wght@400;700&family=Space+Grotesk:wght@300;400;500;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
    """, unsafe_allow_html=True)

    css_path = os.path.join(os.path.dirname(__file__), "static", "styles.css")
    if os.path.exists(css_path):
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_design_system()


# ── Nothing Design helpers ────────────────────────────────────────────────────

def metric_card(label: str, value: str, delta: str = None, color: str = None):
    delta_html = f'<div class="stats-delta">{delta}</div>' if delta else ''
    color_class = f'text-{color}' if color else ''
    st.markdown(f"""
    <div class="stats-card">
        <div class="stats-label">{label}</div>
        <div class="stats-value {color_class}">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def pipeline_card(label: str, count: int, status: str = ""):
    status_class = f'status-{status}' if status else ''
    st.markdown(f"""
    <div class="pipeline-card">
        <div class="pipeline-count {status_class}">{count}</div>
        <div class="pipeline-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)


def lead_card_header(company: str, status: str, date: str = ""):
    status_colors = {
        'new': 'text-secondary',
        'researching': 'text-warning',
        'drafted': 'text-warning',
        'sent': 'text-secondary',
        'meeting_set': 'text-success',
        'dead': 'text-error',
    }
    color_class = status_colors.get(status, 'text-secondary')
    date_display = f'<span class="text-secondary" style="font-size:12px;margin-left:8px;">{date}</span>' if date else ''
    st.markdown(f"""
    <div class="lead-header">
        <div class="lead-title">{company}</div>
        <div class="lead-status {color_class}">{status.upper().replace('_', ' ')}{date_display}</div>
    </div>
    """, unsafe_allow_html=True)


def section_header(title: str, subtitle: str = ""):
    subtitle_html = f'<p class="text-secondary" style="margin-top:8px;font-size:14px;">{subtitle}</p>' if subtitle else ''
    st.markdown(f"""
    <div style="margin:48px 0 24px 0;">
        <h2>{title}</h2>
        {subtitle_html}
    </div>
    """, unsafe_allow_html=True)


def label_value(label: str, value: str, color: str = None):
    color_class = f'text-{color}' if color else 'text-primary'
    st.markdown(f"""
    <div style="margin:8px 0;">
        <span class="label" style="margin-right:12px;">{label}</span>
        <span class="{color_class}" style="font-family:var(--font-body);font-size:16px;">{value}</span>
    </div>
    """, unsafe_allow_html=True)


def empty_state(text: str):
    st.markdown(f"""
    <div style="padding:96px 48px;text-align:center;">
        <p class="text-secondary" style="font-family:var(--font-mono);font-size:14px;letter-spacing:0.08em;">{text}</p>
    </div>
    """, unsafe_allow_html=True)


# ── Session init ──────────────────────────────────────────────────────────────

@st.cache_resource
def get_db():
    from database.supabase_client import SupabaseDB
    return SupabaseDB()


@st.cache_resource
def get_agents():
    from agents.lead_research import LeadResearchAgent
    from agents.email_drafter import EmailDrafterAgent
    from agents.followup import FollowUpAgent
    from agents.prd_generator import PRDGeneratorAgent
    return {
        "research": LeadResearchAgent(),
        "drafter": EmailDrafterAgent(),
        "followup": FollowUpAgent(),
        "prd": PRDGeneratorAgent(),
    }


def db():
    return get_db()


# ── Sidebar navigation ────────────────────────────────────────────────────────

st.sidebar.markdown("# BD AUTOMATION")
page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Add Lead", "Bulk Discovery", "Pipeline", "Emails", "Meetings & PRDs", "Analytics", "Research Insights"],
    index=0,
)


# ── Activity feed & active tasks ──────────────────────────────────────────────

_TASK_STATUS_ICONS = {
    "completed": "✓",
    "failed": "✗",
    "running": "→",
    "pending": "·",
}

_TASK_STATUS_COLORS = {
    "completed": "success",
    "failed": "error",
    "running": "warning",
    "pending": "secondary",
}


def render_active_tasks():
    try:
        tasks = db().get_active_tasks(hours=2)
        if not tasks:
            return
        st.markdown('<p class="label" style="margin-bottom:12px;">ACTIVE TASKS</p>', unsafe_allow_html=True)
        for t in tasks:
            icon = _TASK_STATUS_ICONS.get(t.status, "·")
            color = _TASK_STATUS_COLORS.get(t.status, "secondary")
            pct = t.progress_pct or 0
            msg = t.message or t.task_type.upper()
            st.markdown(f"""
            <div style="background:var(--surface);border:1px solid var(--border-visible);border-radius:8px;padding:12px 16px;margin-bottom:8px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                    <span style="font-family:var(--font-body);font-size:14px;color:var(--text-primary);">{msg}</span>
                    <span class="text-{color}" style="font-family:var(--font-mono);font-size:11px;letter-spacing:0.06em;">{icon} {t.status.upper()}</span>
                </div>
                <div style="background:var(--border);border-radius:2px;height:2px;">
                    <div style="background:var(--accent);width:{pct}%;height:2px;border-radius:2px;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("<hr>", unsafe_allow_html=True)
    except Exception:
        pass


def render_activity_feed(limit: int = 10):
    section_header("Recent Activity", "Audit log of all automation")
    try:
        activity = db().get_recent_activity(limit=limit)
        if not activity:
            empty_state("NO ACTIVITY YET — ADD LEADS TO GET STARTED")
            return
        for t in activity:
            icon = _TASK_STATUS_ICONS.get(t.status, "·")
            color = _TASK_STATUS_COLORS.get(t.status, "secondary")
            ts = t.created_at.strftime("%m/%d %H:%M") if t.created_at else "—"
            msg = t.message or t.task_type.upper()
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--border);">
                <div>
                    <span class="text-{color}" style="font-family:var(--font-mono);font-size:13px;margin-right:10px;">{icon}</span>
                    <span style="font-family:var(--font-body);font-size:14px;color:var(--text-primary);">{msg}</span>
                </div>
                <span class="label">{ts}</span>
            </div>
            """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Could not load activity: {e}")


# ── Stats bar ─────────────────────────────────────────────────────────────────

def render_stats_bar():
    try:
        stats = db().get_daily_stats()
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            metric_card("LEADS ADDED", str(stats.leads_added), f"+{stats.leads_added} today")
        with col2:
            metric_card("EMAILS SENT", str(stats.emails_sent), f"+{stats.emails_sent} today")
        with col3:
            metric_card("REPLIES", str(stats.replies_received), f"+{stats.replies_received} today", color="success")
        with col4:
            metric_card("MEETINGS", str(stats.meetings_booked), f"+{stats.meetings_booked} today", color="success")
        with col5:
            metric_card(
                "BUDGET LEFT",
                f"{stats.emails_remaining_today}/50",
                color="warning" if stats.emails_remaining_today < 10 else None,
            )
    except Exception as e:
        st.warning(f"Could not load stats: {e}")


# ── Pages ─────────────────────────────────────────────────────────────────────

if page == "Dashboard":
    section_header("Dashboard", "Real-time BD automation metrics")
    render_active_tasks()
    render_stats_bar()
    st.markdown("<hr>", unsafe_allow_html=True)

    section_header("Pipeline Overview")
    try:
        counts = db().get_pipeline_counts()
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            pipeline_card("NEW", counts.get('new', 0), 'new')
        with col2:
            pipeline_card("RESEARCHING", counts.get('researching', 0), 'researching')
        with col3:
            pipeline_card("DRAFTED", counts.get('drafted', 0), 'drafted')
        with col4:
            pipeline_card("SENT", counts.get('sent', 0), 'sent')
        with col5:
            pipeline_card("MEETING SET", counts.get('meeting_set', 0), 'meeting_set')
        with col6:
            pipeline_card("DEAD", counts.get('dead', 0), 'dead')
    except Exception as e:
        st.error(f"Pipeline data unavailable: {e}")

    st.markdown("<hr>", unsafe_allow_html=True)
    section_header("Recent Leads")
    try:
        leads = db().list_leads()[:10]
        if leads:
            data = [
                {
                    "Company": l.company_name,
                    "Vertical": l.vertical.upper(),
                    "Geography": l.geography or "—",
                    "Status": l.status.upper().replace('_', ' '),
                    "Added": l.created_at.strftime("%m/%d %H:%M") if l.created_at else "—",
                }
                for l in leads
            ]
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
        else:
            empty_state("NO LEADS YET — ADD ONE FROM THE SIDEBAR")
    except Exception as e:
        st.error(f"Could not load leads: {e}")

    st.markdown("<hr>", unsafe_allow_html=True)
    render_activity_feed(limit=10)


elif page == "Add Lead":
    section_header("Add New Lead", "Triggers automatic research within 30 minutes")

    with st.form("add_lead_form"):
        col1, col2 = st.columns(2)
        company_name = col1.text_input("Company Name", placeholder="Joe's Pizzeria")
        vertical = col2.selectbox("Vertical", ["restaurant", "vet", "dermatologist"])
        geography = col1.text_input("Geography", placeholder="Austin, TX")
        website = col2.text_input("Website", placeholder="joespizzeria.com")

        st.markdown("<hr style='margin:32px 0;'>", unsafe_allow_html=True)
        st.markdown('<p class="label">CONTACT INFO (OPTIONAL — AUTO-DISCOVERED IF BLANK)</p>',
                    unsafe_allow_html=True)

        col3, col4 = st.columns(2)
        contact_name = col3.text_input("Contact Name", placeholder="Joe Smith")
        contact_role = col4.text_input("Role", placeholder="Owner")
        contact_email = col3.text_input("Email", placeholder="joe@joespizzeria.com")
        contact_phone = col4.text_input("Phone", placeholder="+1 555 000 0000")

        auto_research = st.checkbox("Auto-research immediately (slower UI)", value=False)
        submitted = st.form_submit_button("ADD LEAD", type="primary")

    if submitted:
        if not company_name:
            st.error("Company name is required.")
        else:
            try:
                from database.models import Lead, Contact
                lead = db().create_lead(
                    Lead(
                        company_name=company_name,
                        vertical=vertical,
                        geography=geography or None,
                        website=website or None,
                    )
                )
                if contact_name:
                    db().create_contact(
                        Contact(
                            lead_id=lead.id,
                            name=contact_name,
                            role=contact_role or None,
                            email=contact_email or None,
                            phone=contact_phone or None,
                        )
                    )
                st.success(f"✓ Lead created: **{company_name}** (ID: `{lead.id[:8]}…`)")
                if auto_research:
                    with st.spinner("[RESEARCHING...]"):
                        agents = get_agents()
                        result = agents["research"].research_lead(lead)
                        db().update_lead_status(lead.id, "researching")
                        if result.owner_name and not contact_name:
                            from database.models import Contact
                            db().create_contact(
                                Contact(
                                    lead_id=lead.id,
                                    name=result.owner_name,
                                    role=result.owner_role,
                                    email=result.email,
                                    phone=result.phone,
                                )
                            )
                        st.success("✓ Research complete!")
                else:
                    st.info("→ Research will run automatically in the background via Celery.")
            except Exception as e:
                st.error(f"Failed to add lead: {e}")
                logger.exception("Add lead error")


elif page == "Bulk Discovery":
    section_header("Bulk Discovery", "Find 50-200 businesses at once via Google Maps")

    tab_launch, tab_queue = st.tabs(["Launch Campaign", "Approval Queue"])

    with tab_launch:
        section_header("New Discovery Campaign", "Search by business type + location radius")

        with st.form("bulk_discovery_form"):
            col1, col2 = st.columns(2)
            business_type = col1.text_input("Business Type", placeholder="restaurant")
            geographic_center = col2.text_input("Location", placeholder="Austin, TX")
            radius_miles = col1.number_input("Radius (miles)", min_value=1.0, max_value=50.0, value=10.0, step=1.0)
            max_results = col2.number_input("Max Results", min_value=10, max_value=200, value=50, step=10)
            submitted = st.form_submit_button("DISCOVER BUSINESSES", type="primary")

        if submitted:
            if not business_type or not geographic_center:
                st.error("Business type and location are required.")
            else:
                try:
                    from database.models import DiscoveryCampaign
                    campaign = db().create_campaign(DiscoveryCampaign(
                        business_type=business_type,
                        geographic_center=geographic_center,
                        radius_miles=radius_miles,
                        max_results=int(max_results),
                        status="discovering",
                    ))
                    from tasks import bulk_discover
                    bulk_discover.delay(campaign.id)
                    st.success(
                        f"Campaign launched! ID: `{campaign.id[:8]}…` — "
                        f"Discovering {int(max_results)} {business_type}s near {geographic_center}. "
                        f"Reload the Approval Queue in a few minutes."
                    )
                except Exception as e:
                    st.error(f"Failed to launch campaign: {e}")
                    logger.exception("Bulk discovery launch error")

        st.markdown("<hr>", unsafe_allow_html=True)
        section_header("Recent Campaigns")
        try:
            campaigns = db().list_campaigns()
            if campaigns:
                data = [
                    {
                        "ID": c.id[:8] + "…",
                        "Type": c.business_type,
                        "Location": c.geographic_center,
                        "Radius (mi)": c.radius_miles,
                        "Max": c.max_results,
                        "Found": c.discovered_count,
                        "Status": c.status.upper().replace("_", " "),
                        "Created": c.created_at.strftime("%m/%d %H:%M") if c.created_at else "—",
                    }
                    for c in campaigns
                ]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            else:
                empty_state("NO CAMPAIGNS YET — LAUNCH ONE ABOVE")
        except Exception as e:
            st.error(f"Could not load campaigns: {e}")

    with tab_queue:
        section_header("Approval Queue", "Review discovered leads and approve for outreach")

        try:
            campaigns = db().list_campaigns(status="pending_approval")
            if not campaigns:
                all_campaigns = db().list_campaigns()
                campaigns = all_campaigns

            if not campaigns:
                empty_state("NO CAMPAIGNS YET — LAUNCH A DISCOVERY CAMPAIGN FIRST")
            else:
                campaign_options = {
                    f"{c.business_type} @ {c.geographic_center} ({c.discovered_count} found)": c
                    for c in campaigns
                }
                selected_label = st.selectbox("Select Campaign", list(campaign_options.keys()))
                selected_campaign = campaign_options.get(selected_label)

                if selected_campaign:
                    businesses = db().list_discovered_businesses(selected_campaign.id)

                    if not businesses:
                        empty_state("NO BUSINESSES DISCOVERED YET — CHECK BACK SOON")
                    else:
                        st.markdown(
                            f'<p class="label" style="margin-bottom:16px;">'
                            f'{len(businesses)} BUSINESSES DISCOVERED — SELECT TO APPROVE</p>',
                            unsafe_allow_html=True,
                        )

                        biz_data = []
                        for b in businesses:
                            biz_data.append({
                                "id": b.id,
                                "Approve": b.approved,
                                "Business": b.business_name,
                                "Address": b.address or "—",
                                "Phone": b.phone or "—",
                                "Email": b.email or "—",
                                "Channel": b.channel or "none",
                                "Rating": b.rating or "—",
                            })

                        df = pd.DataFrame(biz_data)
                        edited_df = st.data_editor(
                            df.drop(columns=["id"]),
                            column_config={
                                "Approve": st.column_config.CheckboxColumn("Approve", default=False),
                                "Channel": st.column_config.SelectboxColumn(
                                    "Channel",
                                    options=["email", "sms", "both", "none"],
                                ),
                            },
                            use_container_width=True,
                            hide_index=True,
                            num_rows="fixed",
                        )

                        col_a, col_b = st.columns(2)
                        if col_a.button("SAVE APPROVALS", type="primary"):
                            try:
                                approved_indices = edited_df[edited_df["Approve"] == True].index.tolist()
                                for i, row in edited_df.iterrows():
                                    biz_id = df.iloc[i]["id"]
                                    db().update_discovered_business(biz_id, {
                                        "approved": bool(row["Approve"]),
                                        "channel": row["Channel"],
                                    })
                                st.success(f"[SAVED] {len(approved_indices)} businesses approved for outreach")
                            except Exception as e:
                                st.error(f"Save failed: {e}")

                        if col_b.button("SEND APPROVED TO OUTREACH"):
                            try:
                                approved_bizs = [
                                    b for b, row in zip(businesses, edited_df.itertuples())
                                    if row.Approve
                                ]
                                email_count = 0
                                sms_count = 0
                                from database.models import Contact, SMSMessage
                                from agents.sms_drafter import SMSDrafterAgent
                                from agents.email_drafter import EmailDrafterAgent
                                from database.models import ResearchResult, Lead

                                sms_agent = SMSDrafterAgent()
                                email_agent = EmailDrafterAgent()

                                for biz in approved_bizs:
                                    channel = biz.channel or "none"
                                    if channel == "none":
                                        continue

                                    lead = db().create_lead(Lead(
                                        company_name=biz.business_name,
                                        vertical=selected_campaign.business_type
                                            if selected_campaign.business_type in ["restaurant", "vet", "dermatologist"]
                                            else "restaurant",
                                        geography=selected_campaign.geographic_center,
                                        website=biz.website,
                                        status="new",
                                    ))
                                    contact = db().create_contact(Contact(
                                        lead_id=lead.id,
                                        name=biz.business_name,
                                        role="Owner",
                                        email=biz.email if channel in ("email", "both") else None,
                                        phone=biz.phone if channel in ("sms", "both") else None,
                                    ))

                                    if channel in ("email", "both") and biz.email:
                                        research = ResearchResult(
                                            company_name=biz.business_name,
                                            vertical=lead.vertical,
                                            insights=f"Local {lead.vertical} in {selected_campaign.geographic_center}",
                                        )
                                        draft = email_agent.draft_email(lead, contact, research)
                                        db().create_email(draft)
                                        db().update_lead_status(lead.id, "drafted")
                                        email_count += 1

                                    if channel in ("sms", "both") and biz.phone:
                                        msg = sms_agent.draft_sms(
                                            biz.business_name, lead.vertical, biz.phone
                                        )
                                        if msg:
                                            db().create_sms(SMSMessage(
                                                contact_id=contact.id,
                                                phone_number=biz.phone,
                                                message_body=msg,
                                                status="draft",
                                            ))
                                            sms_count += 1

                                st.success(
                                    f"[QUEUED] {email_count} emails drafted, {sms_count} SMS drafted. "
                                    f"Celery will send them respecting daily caps."
                                )
                                db().update_campaign(selected_campaign.id, {"status": "approved"})
                            except Exception as e:
                                st.error(f"Outreach queue failed: {e}")
                                logger.exception("Approval queue outreach error")

        except Exception as e:
            st.error(f"Approval queue error: {e}")
            logger.exception("Approval queue error")


elif page == "Pipeline":
    section_header("Lead Pipeline", "Manage leads across all stages")

    status_filter = st.selectbox(
        "Filter by status",
        ["all", "new", "researching", "drafted", "sent", "meeting_set", "dead"],
        index=0,
    )

    try:
        leads = db().list_leads(status=None if status_filter == "all" else status_filter)
        if not leads:
            empty_state(f"NO LEADS WITH STATUS: {status_filter.upper()}")
        else:
            for lead in leads:
                with st.expander(f"**{lead.company_name}**", expanded=False):
                    lead_card_header(
                        lead.company_name,
                        lead.status,
                        lead.created_at.strftime("%m/%d/%y") if lead.created_at else "",
                    )
                    st.markdown("<hr style='margin:16px 0;'>", unsafe_allow_html=True)

                    label_value("VERTICAL", lead.vertical.upper())
                    label_value("GEOGRAPHY", lead.geography or "—")
                    label_value("WEBSITE", lead.website or "—")

                    contacts = db().get_contacts_for_lead(lead.id)
                    if contacts:
                        st.markdown('<p class="label" style="margin-top:24px;">CONTACTS</p>',
                                    unsafe_allow_html=True)
                        for c in contacts:
                            st.markdown(f"→ {c.name} ({c.role or 'Unknown'}) — {c.email or 'No email'}")

                    st.markdown("<hr style='margin:24px 0 16px 0;'>", unsafe_allow_html=True)
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        new_status = st.selectbox(
                            "Update status",
                            ["new", "researching", "drafted", "sent", "meeting_set", "dead"],
                            index=["new", "researching", "drafted", "sent", "meeting_set", "dead"].index(lead.status),
                            key=f"status_{lead.id}",
                        )
                    with col_b:
                        if st.button("UPDATE", key=f"update_{lead.id}", type="primary"):
                            db().update_lead_status(lead.id, new_status)
                            st.rerun()
    except Exception as e:
        st.error(f"Pipeline load failed: {e}")


elif page == "Emails":
    section_header("Email Management")

    tab1, tab2 = st.tabs(["Draft Emails", "Email History"])

    with tab1:
        section_header("Draft & Send", "Compose personalized outreach")
        try:
            leads = db().list_leads(status="researching")
            if not leads:
                leads = db().list_leads()
            lead_options = {f"{l.company_name} ({l.id[:6]})": l for l in leads}
            selected_label = st.selectbox("Select Lead", list(lead_options.keys()))
            selected_lead = lead_options.get(selected_label)
        except Exception as e:
            st.error(f"Could not load leads: {e}")
            selected_lead = None

        if selected_lead:
            try:
                contacts = db().get_contacts_for_lead(selected_lead.id)
                if not contacts:
                    st.warning("No contacts for this lead. Research first or add contacts manually.")
                else:
                    contact_options = {f"{c.name} ({c.email or 'no email'})": c for c in contacts}
                    sel_contact_label = st.selectbox("Contact", list(contact_options.keys()))
                    sel_contact = contact_options[sel_contact_label]

                    if st.button("Draft Email", type="primary"):
                        with st.spinner("[DRAFTING...]"):
                            from database.models import ResearchResult
                            research = ResearchResult(
                                company_name=selected_lead.company_name,
                                vertical=selected_lead.vertical,
                                insights=f"Local {selected_lead.vertical} business in {selected_lead.geography or 'the area'}",
                            )
                            agents = get_agents()
                            draft = agents["drafter"].draft_email(selected_lead, sel_contact, research)
                            st.session_state["draft_email"] = draft
                            st.session_state["draft_contact"] = sel_contact
                            st.session_state["draft_lead"] = selected_lead

                    if "draft_email" in st.session_state:
                        draft = st.session_state["draft_email"]
                        st.markdown('<p class="label" style="margin-top:32px;">DRAFT</p>',
                                    unsafe_allow_html=True)
                        subject = st.text_input("Subject", value=draft.subject)
                        body = st.text_area("Body", value=draft.body, height=200)

                        col_a, col_b = st.columns(2)
                        if col_a.button("SAVE AS DRAFT"):
                            draft.subject = subject
                            draft.body = body
                            db().create_email(draft)
                            db().update_lead_status(selected_lead.id, "drafted")
                            st.success("[SAVED]")
                            del st.session_state["draft_email"]
                        if col_b.button("SEND NOW", type="primary"):
                            if not sel_contact.email:
                                st.error("[ERROR: No email address for this contact]")
                            else:
                                daily_count = db().count_emails_sent_today()
                                if daily_count >= 50:
                                    st.error("[ERROR: Daily limit of 50 emails reached]")
                                else:
                                    draft.subject = subject
                                    draft.body = body
                                    email_record = db().create_email(draft)
                                    agents = get_agents()
                                    success = agents["followup"].send_initial_sequence(
                                        selected_lead, sel_contact, email_record
                                    )
                                    if success:
                                        st.success(f"[SENT] → {sel_contact.email}")
                                        del st.session_state["draft_email"]
                                    else:
                                        st.error("[ERROR: Send failed — check logs]")
            except Exception as e:
                st.error(f"Email draft error: {e}")
                logger.exception("Email draft error")

    with tab2:
        section_header("Email History", "All outreach activity")
        try:
            leads = db().list_leads()
            all_emails = []
            for lead in leads[:20]:
                contacts = db().get_contacts_for_lead(lead.id)
                for contact in contacts:
                    emails = db().get_emails_for_contact(contact.id)
                    for email in emails:
                        all_emails.append({
                            "Company": lead.company_name,
                            "Contact": contact.name,
                            "Email": contact.email or "—",
                            "Subject": (email.subject or "")[:50],
                            "Status": email.status.upper(),
                            "Sent At": email.sent_at.strftime("%m/%d %H:%M") if email.sent_at else "—",
                            "Reply": "✓" if email.reply_received else "—",
                        })
            if all_emails:
                st.dataframe(pd.DataFrame(all_emails), use_container_width=True, hide_index=True)
            else:
                empty_state("NO EMAILS YET")
        except Exception as e:
            st.error(f"Could not load email history: {e}")


elif page == "Meetings & PRDs":
    section_header("Meetings & PRDs")

    tab1, tab2, tab3 = st.tabs(["Log Meeting", "Generate PRD", "Meeting History"])

    with tab1:
        section_header("Log a New Meeting")
        try:
            leads = db().list_leads(status="sent")
            if not leads:
                leads = db().list_leads()
            lead_map = {f"{l.company_name}": l for l in leads}
            sel_lead_name = st.selectbox("Lead", list(lead_map.keys()))
            sel_lead = lead_map[sel_lead_name]
            contacts = db().get_contacts_for_lead(sel_lead.id)
            contact_map = {c.name: c for c in contacts} if contacts else {}
            sel_contact_name = st.selectbox("Contact", list(contact_map.keys()) or ["(none)"])
            sel_contact = contact_map.get(sel_contact_name)
        except Exception as e:
            st.error(f"Load error: {e}")
            sel_contact = None

        scheduled_at = st.date_input("Meeting Date", value=datetime.utcnow().date())

        if sel_contact and st.button("LOG MEETING", type="primary"):
            try:
                from database.models import Meeting
                meeting = db().create_meeting(
                    Meeting(
                        contact_id=sel_contact.id,
                        scheduled_at=datetime.combine(scheduled_at, datetime.min.time()),
                    )
                )
                db().update_lead_status(sel_lead.id, "meeting_set")
                st.success(f"[LOGGED] Meeting ID: `{meeting.id[:8]}…`")
                st.session_state["active_meeting_id"] = meeting.id
            except Exception as e:
                st.error(f"Failed to log meeting: {e}")

    with tab2:
        section_header("Generate PRD", "From meeting transcript or audio")

        input_method = st.radio("Input method", ["Paste transcript", "Upload audio"])
        transcript_text = ""

        if input_method == "Paste transcript":
            transcript_text = st.text_area("Meeting Transcript", height=250,
                placeholder="Paste full meeting transcript here…")
        else:
            audio_file = st.file_uploader("Upload audio (mp3, m4a, wav)", type=["mp3", "m4a", "wav"])
            if audio_file and st.button("Transcribe"):
                with st.spinner("[TRANSCRIBING...]"):
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=f".{audio_file.name.split('.')[-1]}", delete=False) as tmp:
                        tmp.write(audio_file.read())
                        tmp_path = tmp.name
                    try:
                        agents = get_agents()
                        transcript_text = agents["prd"].transcribe_audio(tmp_path)
                        st.session_state["transcript"] = transcript_text
                        st.success("[DONE] Transcription complete")
                    except Exception as e:
                        st.error(f"Transcription failed: {e}")

        if "transcript" in st.session_state:
            transcript_text = st.session_state["transcript"]
            st.text_area("Transcript (from audio)", value=transcript_text, height=150, disabled=True)

        client_name = st.text_input("Client Name", placeholder="Joe's Pizzeria")

        if transcript_text and st.button("GENERATE PRD", type="primary"):
            with st.spinner("[GENERATING...]"):
                try:
                    agents = get_agents()
                    prd = agents["prd"].generate_prd(transcript_text, client_name=client_name or "Client")
                    st.session_state["generated_prd"] = prd
                    st.session_state["prd_client"] = client_name
                except Exception as e:
                    st.error(f"PRD generation failed: {e}")

        if "generated_prd" in st.session_state:
            prd = st.session_state["generated_prd"]
            st.markdown('<p class="label" style="margin-top:32px;">GENERATED PRD</p>',
                        unsafe_allow_html=True)
            st.markdown(prd)

            col_a, col_b = st.columns(2)
            if col_a.button("Generate HTML Prototype"):
                with st.spinner("[BUILDING...]"):
                    try:
                        agents = get_agents()
                        html = agents["prd"].generate_prototype_html(
                            prd, title=st.session_state.get("prd_client", "Prototype")
                        )
                        st.download_button(
                            "Download HTML Prototype",
                            data=html,
                            file_name="prototype.html",
                            mime="text/html",
                        )
                    except Exception as e:
                        st.error(f"Prototype generation failed: {e}")
            if col_b.button("Save PRD to Meeting"):
                if "active_meeting_id" in st.session_state:
                    try:
                        db().update_meeting(
                            st.session_state["active_meeting_id"],
                            {"prd_generated": prd, "transcript": transcript_text},
                        )
                        st.success("[SAVED] PRD saved to meeting record")
                    except Exception as e:
                        st.error(f"Save failed: {e}")
                else:
                    st.warning("No active meeting. Log one in the 'Log Meeting' tab first.")

    with tab3:
        section_header("Meeting History")
        try:
            meetings = db().get_meetings()
            if meetings:
                data = [
                    {
                        "Contact ID": m.contact_id[:8] + "…",
                        "Scheduled": m.scheduled_at.strftime("%Y-%m-%d") if m.scheduled_at else "—",
                        "PRD": "✓" if m.prd_generated else "—",
                        "Prototype": "✓" if m.prototype_url else "—",
                    }
                    for m in meetings
                ]
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            else:
                empty_state("NO MEETINGS LOGGED YET")
        except Exception as e:
            st.error(f"Could not load meetings: {e}")


elif page == "Analytics":
    section_header("Analytics", "Pipeline performance overview")
    render_stats_bar()
    st.markdown("<hr>", unsafe_allow_html=True)

    try:
        leads = db().list_leads()
        if not leads:
            empty_state("NO DATA YET — ADD LEADS TO SEE ANALYTICS")
        else:
            counts = db().get_pipeline_counts()
            stages = ["new", "researching", "drafted", "sent", "meeting_set"]
            labels = ["New", "Researching", "Drafted", "Sent", "Meeting Set"]
            values = [counts.get(s, 0) for s in stages]

            section_header("Pipeline Funnel")
            df_funnel = pd.DataFrame({"Stage": labels, "Count": values})
            st.bar_chart(df_funnel.set_index("Stage"))

            section_header("Leads by Vertical")
            vertical_counts = {}
            for l in leads:
                vertical_counts[l.vertical] = vertical_counts.get(l.vertical, 0) + 1
            df_vert = pd.DataFrame(
                [{"Vertical": k, "Count": v} for k, v in vertical_counts.items()]
            )
            if not df_vert.empty:
                st.bar_chart(df_vert.set_index("Vertical"))

            total_sent = counts.get("sent", 0) + counts.get("meeting_set", 0)
            if total_sent:
                section_header("Conversion Rates")
                col1, col2, col3 = st.columns(3)
                with col1:
                    metric_card(
                        "RESEARCH RATE",
                        f"{int(100*(counts.get('researching',0)+counts.get('drafted',0)+counts.get('sent',0)+counts.get('meeting_set',0)) / max(len(leads),1))}%",
                    )
                with col2:
                    metric_card("SEND RATE", f"{int(100*total_sent / max(len(leads),1))}%")
                with col3:
                    metric_card(
                        "MEETING RATE",
                        f"{int(100*counts.get('meeting_set',0) / max(total_sent,1))}%",
                        color="success",
                    )

            # ── SMS Metrics (V2) ──────────────────────────────────────────
            try:
                sms_sent_today = db().count_sms_sent_today()
                campaigns = db().list_campaigns()
                total_discovered = sum(c.discovered_count for c in campaigns)

                section_header("SMS & Discovery Metrics")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    metric_card("SMS SENT TODAY", str(sms_sent_today),
                                color="warning" if sms_sent_today >= 45 else None)
                with col2:
                    metric_card("SMS BUDGET LEFT", f"{max(0, 50 - sms_sent_today)}/50")
                with col3:
                    metric_card("CAMPAIGNS RUN", str(len(campaigns)))
                with col4:
                    metric_card("BUSINESSES FOUND", str(total_discovered))
            except Exception:
                pass

    except Exception as e:
        st.error(f"Analytics error: {e}")
        logger.exception("Analytics error")


elif page == "Research Insights":
    section_header("Research Insights", "Full visibility into what the agent discovered for each lead")

    try:
        leads = db().list_leads()
        if not leads:
            empty_state("NO LEADS YET — ADD ONE FROM THE SIDEBAR")
        else:
            lead_options = {f"{l.company_name} ({l.status.upper()})": l for l in leads}
            selected_label = st.selectbox("Select Lead", list(lead_options.keys()))
            selected_lead = lead_options.get(selected_label)

            if selected_lead:
                st.markdown("<hr>", unsafe_allow_html=True)

                # Priority score row
                from agents.automation_rules import AutomationRules
                rules = AutomationRules(db=db())
                components = rules.calculate_score_components(selected_lead)

                lead_card_header(
                    selected_lead.company_name,
                    selected_lead.status,
                    selected_lead.created_at.strftime("%m/%d/%y") if selected_lead.created_at else "",
                )

                st.markdown('<p class="label" style="margin:24px 0 12px 0;">PRIORITY SCORE</p>',
                            unsafe_allow_html=True)
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    metric_card("TOTAL", f"{components['total']}/100",
                                color="success" if components["total"] >= 60 else "warning" if components["total"] >= 40 else "error")
                with col2:
                    metric_card("WEBSITE", f"{components['website']}/20")
                with col3:
                    metric_card("CONTACT", f"{components['contact']}/15")
                with col4:
                    metric_card("RESEARCH", f"{components['research']}/30")

                st.markdown("<hr>", unsafe_allow_html=True)

                col_left, col_right = st.columns(2)

                with col_left:
                    st.markdown('<p class="label" style="margin-bottom:12px;">DISCOVERED CONTACTS</p>',
                                unsafe_allow_html=True)
                    contacts = db().get_contacts_for_lead(selected_lead.id)
                    if contacts:
                        for c in contacts:
                            email_status = ""
                            logs = db().get_research_logs_for_lead(selected_lead.id)
                            if logs and logs[0].email_verification_status:
                                status_colors = {"verified": "success", "unverified": "error",
                                                 "not_found": "error", "skipped": "secondary"}
                                ev = logs[0].email_verification_status
                                email_status = f'<span class="text-{status_colors.get(ev, "secondary")}" style="font-size:11px;font-family:var(--font-mono);margin-left:8px;">{ev.upper()}</span>'
                            st.markdown(f"""
                            <div class="lead-card" style="margin-bottom:8px;">
                                <div style="font-size:15px;font-weight:500;color:var(--text-display);">{c.name}</div>
                                <div class="label" style="margin-top:4px;">{c.role or "Unknown role"}</div>
                                <div style="margin-top:8px;font-size:14px;color:var(--text-primary);">
                                    {c.email or "No email"}{email_status}
                                </div>
                                {"<div style='font-size:14px;color:var(--text-secondary);'>" + c.phone + "</div>" if c.phone else ""}
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        empty_state("NO CONTACTS FOUND")

                    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
                    if st.button("Re-run Research", type="primary"):
                        with st.spinner("[RESEARCHING...]"):
                            try:
                                from agents.lead_research import LeadResearchAgent
                                agent = LeadResearchAgent(db=db())
                                result = agent.research_lead(selected_lead)
                                db().update_lead_status(selected_lead.id, "researching")
                                st.success(f"[DONE] Research updated for {selected_lead.company_name}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Research failed: {e}")

                with col_right:
                    st.markdown('<p class="label" style="margin-bottom:12px;">RESEARCH HISTORY</p>',
                                unsafe_allow_html=True)
                    logs = db().get_research_logs_for_lead(selected_lead.id)
                    if logs:
                        for log in logs:
                            ts = log.created_at.strftime("%m/%d %H:%M") if log.created_at else "—"
                            ev_color = {"verified": "success", "unverified": "error",
                                        "not_found": "error", "skipped": "secondary"}.get(
                                log.email_verification_status or "skipped", "secondary")
                            confidence_html = f'<div style="margin-top:4px;"><span class="label">HUNTER CONFIDENCE</span> <span class="text-primary">{log.hunter_confidence}%</span></div>' if log.hunter_confidence else ""
                            duration_html = f'<div style="margin-top:4px;"><span class="label">SCRAPE</span> <span class="text-secondary">{log.scrape_duration_ms}ms</span></div>' if log.scrape_duration_ms else ""
                            insights_html = f'<div style="margin-top:8px;font-size:13px;color:var(--text-secondary);line-height:1.5;">{(log.insights or "")[:200]}{"…" if log.insights and len(log.insights) > 200 else ""}</div>' if log.insights else ""
                            st.markdown(f"""
                            <div style="background:var(--surface);border:1px solid var(--border-visible);border-radius:8px;padding:16px;margin-bottom:8px;">
                                <div style="display:flex;justify-content:space-between;align-items:center;">
                                    <span class="label">{ts}</span>
                                    <span class="text-{ev_color}" style="font-family:var(--font-mono);font-size:11px;letter-spacing:0.06em;">{(log.email_verification_status or "skipped").upper()}</span>
                                </div>
                                {confidence_html}
                                {duration_html}
                                {insights_html}
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        empty_state("NO RESEARCH LOGS — RUN RESEARCH FIRST")

    except Exception as e:
        st.error(f"Research Insights error: {e}")
        logger.exception("Research Insights error")
