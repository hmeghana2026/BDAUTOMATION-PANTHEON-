"""Streamlit dashboard for BD Automation Platform."""
import os
import sys
import logging
import streamlit as st
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="BD Automation Platform",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session init ────────────────────────────────────────────────────────────

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


# ── Sidebar navigation ───────────────────────────────────────────────────────

st.sidebar.title("🚀 BD Automation")
page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Add Lead", "Pipeline", "Emails", "Meetings & PRDs", "Analytics"],
    index=0,
)

# ── Header stats bar ─────────────────────────────────────────────────────────

def render_stats_bar():
    try:
        stats = db().get_daily_stats()
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Leads Added Today", stats.leads_added)
        col2.metric("Emails Sent Today", stats.emails_sent)
        col3.metric("Replies Today", stats.replies_received)
        col4.metric("Meetings Booked", stats.meetings_booked)
        col5.metric("Email Budget Left", stats.emails_remaining_today, delta=f"/ 50")
    except Exception as e:
        st.warning(f"Could not load stats: {e}")


# ── Pages ─────────────────────────────────────────────────────────────────────

if page == "Dashboard":
    st.title("BD Automation Dashboard")
    render_stats_bar()
    st.divider()

    st.subheader("Pipeline Overview")
    try:
        counts = db().get_pipeline_counts()
        stages = ["new", "researching", "drafted", "sent", "meeting_set", "dead"]
        labels = ["New", "Researching", "Drafted", "Sent", "Meeting Set", "Dead"]
        cols = st.columns(len(stages))
        colors = ["#3b82f6", "#f59e0b", "#8b5cf6", "#10b981", "#059669", "#ef4444"]
        for col, stage, label, color in zip(cols, stages, labels, colors):
            col.markdown(
                f"""<div style="background:{color};color:white;border-radius:8px;
                padding:16px;text-align:center;">
                <div style="font-size:32px;font-weight:700">{counts.get(stage, 0)}</div>
                <div style="font-size:12px;opacity:.85">{label}</div></div>""",
                unsafe_allow_html=True,
            )
    except Exception as e:
        st.error(f"Pipeline data unavailable: {e}")

    st.divider()
    st.subheader("Recent Leads")
    try:
        leads = db().list_leads()[:10]
        if leads:
            data = [
                {
                    "Company": l.company_name,
                    "Vertical": l.vertical,
                    "Geography": l.geography or "—",
                    "Status": l.status,
                    "Added": l.created_at.strftime("%m/%d %H:%M") if l.created_at else "—",
                }
                for l in leads
            ]
            st.dataframe(pd.DataFrame(data), use_container_width=True)
        else:
            st.info("No leads yet. Add one from the sidebar!")
    except Exception as e:
        st.error(f"Could not load leads: {e}")


elif page == "Add Lead":
    st.title("Add New Lead")
    st.caption("Adding a lead triggers automatic research within 2 hours (via Celery).")

    with st.form("add_lead_form"):
        col1, col2 = st.columns(2)
        company_name = col1.text_input("Company Name *", placeholder="Joe's Pizzeria")
        vertical = col2.selectbox("Vertical *", ["restaurant", "vet", "dermatologist"])
        geography = col1.text_input("Geography", placeholder="Austin, TX")
        website = col2.text_input("Website", placeholder="joespizzeria.com")

        st.subheader("Contact Info (optional — auto-discovered if blank)")
        col3, col4 = st.columns(2)
        contact_name = col3.text_input("Contact Name", placeholder="Joe Smith")
        contact_role = col4.text_input("Role", placeholder="Owner")
        contact_email = col3.text_input("Email", placeholder="joe@joespizzeria.com")
        contact_phone = col4.text_input("Phone", placeholder="+1 555 000 0000")

        auto_research = st.checkbox("Auto-research immediately (slower UI)", value=False)
        submitted = st.form_submit_button("Add Lead", type="primary")

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

                st.success(f"Lead created: **{company_name}** (ID: `{lead.id[:8]}…`)")

                if auto_research:
                    with st.spinner("Researching…"):
                        agents = get_agents()
                        result = agents["research"].research_lead(lead)
                        db().update_lead_status(lead.id, "researching")

                        # Update or create contact from research
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
                        st.success("Research complete!")
                        st.json(result.model_dump())
                else:
                    st.info("Research will run automatically in the background via Celery.")

            except Exception as e:
                st.error(f"Failed to add lead: {e}")
                logger.exception("Add lead error")


elif page == "Pipeline":
    st.title("Lead Pipeline")

    status_filter = st.selectbox(
        "Filter by status", ["all", "new", "researching", "drafted", "sent", "meeting_set", "dead"],
        index=0,
    )

    try:
        leads = db().list_leads(status=None if status_filter == "all" else status_filter)
        if not leads:
            st.info("No leads match this filter.")
        else:
            for lead in leads:
                with st.expander(f"**{lead.company_name}** — {lead.vertical} | {lead.status.upper()}"):
                    col1, col2, col3 = st.columns([2, 2, 1])
                    col1.write(f"**Geography:** {lead.geography or '—'}")
                    col1.write(f"**Website:** {lead.website or '—'}")
                    col2.write(f"**Created:** {lead.created_at.strftime('%Y-%m-%d') if lead.created_at else '—'}")

                    contacts = db().get_contacts_for_lead(lead.id)
                    if contacts:
                        st.write(f"**Contacts ({len(contacts)}):**")
                        for c in contacts:
                            st.write(f"  - {c.name} ({c.role or 'Unknown'}) — {c.email or 'No email'}")

                    new_status = col3.selectbox(
                        "Update status",
                        ["new", "researching", "drafted", "sent", "meeting_set", "dead"],
                        index=["new", "researching", "drafted", "sent", "meeting_set", "dead"].index(lead.status),
                        key=f"status_{lead.id}",
                    )
                    if col3.button("Update", key=f"update_{lead.id}"):
                        db().update_lead_status(lead.id, new_status)
                        st.rerun()

    except Exception as e:
        st.error(f"Pipeline load failed: {e}")


elif page == "Emails":
    st.title("Email Management")

    tab1, tab2 = st.tabs(["Draft Emails", "Email History"])

    with tab1:
        st.subheader("Draft & Send Emails")
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
                        with st.spinner("Drafting personalized email…"):
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
                        st.subheader("Draft")
                        subject = st.text_input("Subject", value=draft.subject)
                        body = st.text_area("Body", value=draft.body, height=200)

                        col_a, col_b = st.columns(2)
                        if col_a.button("Save as Draft"):
                            draft.subject = subject
                            draft.body = body
                            db().create_email(draft)
                            db().update_lead_status(selected_lead.id, "drafted")
                            st.success("Saved as draft!")
                            del st.session_state["draft_email"]

                        if col_b.button("Send Now", type="primary"):
                            if not sel_contact.email:
                                st.error("Contact has no email address!")
                            else:
                                daily_count = db().count_emails_sent_today()
                                if daily_count >= 50:
                                    st.error("Daily email limit (50) reached. Try tomorrow.")
                                else:
                                    draft.subject = subject
                                    draft.body = body
                                    email_record = db().create_email(draft)
                                    agents = get_agents()
                                    success = agents["followup"].send_initial_sequence(
                                        selected_lead, sel_contact, email_record
                                    )
                                    if success:
                                        st.success(f"Email sent to {sel_contact.email}!")
                                        del st.session_state["draft_email"]
                                    else:
                                        st.error("Send failed. Check logs.")
            except Exception as e:
                st.error(f"Email draft error: {e}")
                logger.exception("Email draft error")

    with tab2:
        st.subheader("Email History")
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
                            "Status": email.status,
                            "Sent At": email.sent_at.strftime("%m/%d %H:%M") if email.sent_at else "—",
                            "Reply": "✓" if email.reply_received else "—",
                        })
            if all_emails:
                st.dataframe(pd.DataFrame(all_emails), use_container_width=True)
            else:
                st.info("No emails yet.")
        except Exception as e:
            st.error(f"Could not load email history: {e}")


elif page == "Meetings & PRDs":
    st.title("Meetings & PRDs")

    tab1, tab2, tab3 = st.tabs(["Log Meeting", "Generate PRD", "Meeting History"])

    with tab1:
        st.subheader("Log a New Meeting")
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

        if sel_contact and st.button("Log Meeting", type="primary"):
            try:
                from database.models import Meeting
                meeting = db().create_meeting(
                    Meeting(
                        contact_id=sel_contact.id,
                        scheduled_at=datetime.combine(scheduled_at, datetime.min.time()),
                    )
                )
                db().update_lead_status(sel_lead.id, "meeting_set")
                st.success(f"Meeting logged! ID: `{meeting.id[:8]}…`")
                st.session_state["active_meeting_id"] = meeting.id
            except Exception as e:
                st.error(f"Failed to log meeting: {e}")

    with tab2:
        st.subheader("Generate PRD from Transcript")

        input_method = st.radio("Input method", ["Paste transcript", "Upload audio"])
        transcript_text = ""

        if input_method == "Paste transcript":
            transcript_text = st.text_area("Meeting Transcript", height=250,
                placeholder="Paste full meeting transcript here…")
        else:
            audio_file = st.file_uploader("Upload audio (mp3, m4a, wav)", type=["mp3", "m4a", "wav"])
            if audio_file and st.button("Transcribe"):
                with st.spinner("Transcribing…"):
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=f".{audio_file.name.split('.')[-1]}", delete=False) as tmp:
                        tmp.write(audio_file.read())
                        tmp_path = tmp.name
                    try:
                        agents = get_agents()
                        transcript_text = agents["prd"].transcribe_audio(tmp_path)
                        st.session_state["transcript"] = transcript_text
                        st.success("Transcription complete!")
                    except Exception as e:
                        st.error(f"Transcription failed: {e}")

        if "transcript" in st.session_state:
            transcript_text = st.session_state["transcript"]
            st.text_area("Transcript (from audio)", value=transcript_text, height=150, disabled=True)

        client_name = st.text_input("Client Name", placeholder="Joe's Pizzeria")

        if transcript_text and st.button("Generate PRD", type="primary"):
            with st.spinner("Generating PRD…"):
                try:
                    agents = get_agents()
                    prd = agents["prd"].generate_prd(transcript_text, client_name=client_name or "Client")
                    st.session_state["generated_prd"] = prd
                    st.session_state["prd_client"] = client_name
                except Exception as e:
                    st.error(f"PRD generation failed: {e}")

        if "generated_prd" in st.session_state:
            prd = st.session_state["generated_prd"]
            st.subheader("Generated PRD")
            st.markdown(prd)

            col_a, col_b = st.columns(2)
            if col_a.button("Generate HTML Prototype"):
                with st.spinner("Building prototype…"):
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
                        st.success("PRD saved to meeting record!")
                    except Exception as e:
                        st.error(f"Save failed: {e}")
                else:
                    st.warning("No active meeting logged. Log one in the 'Log Meeting' tab first.")

    with tab3:
        st.subheader("Meeting History")
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
                st.dataframe(pd.DataFrame(data), use_container_width=True)
            else:
                st.info("No meetings logged yet.")
        except Exception as e:
            st.error(f"Could not load meetings: {e}")


elif page == "Analytics":
    st.title("Analytics")
    render_stats_bar()
    st.divider()

    try:
        leads = db().list_leads()
        if not leads:
            st.info("No data yet. Add leads to see analytics.")
        else:
            # Pipeline funnel
            counts = db().get_pipeline_counts()
            stages = ["new", "researching", "drafted", "sent", "meeting_set"]
            labels = ["New", "Researching", "Drafted", "Sent", "Meeting Set"]
            values = [counts.get(s, 0) for s in stages]

            df_funnel = pd.DataFrame({"Stage": labels, "Count": values})
            st.subheader("Pipeline Funnel")
            st.bar_chart(df_funnel.set_index("Stage"))

            # Vertical breakdown
            st.subheader("Leads by Vertical")
            vertical_counts = {}
            for l in leads:
                vertical_counts[l.vertical] = vertical_counts.get(l.vertical, 0) + 1
            df_vert = pd.DataFrame(
                [{"Vertical": k, "Count": v} for k, v in vertical_counts.items()]
            )
            if not df_vert.empty:
                st.bar_chart(df_vert.set_index("Vertical"))

            # Reply rate
            total_sent = counts.get("sent", 0) + counts.get("meeting_set", 0)
            if total_sent:
                st.subheader("Conversion Rates")
                col1, col2, col3 = st.columns(3)
                col1.metric("Research Rate", f"{int(100*(counts.get('researching',0)+counts.get('drafted',0)+counts.get('sent',0)+counts.get('meeting_set',0)) / max(len(leads),1))}%")
                col2.metric("Send Rate", f"{int(100*(total_sent) / max(len(leads),1))}%")
                col3.metric("Meeting Rate", f"{int(100*counts.get('meeting_set',0) / max(total_sent,1))}%")

    except Exception as e:
        st.error(f"Analytics error: {e}")
        logger.exception("Analytics error")
