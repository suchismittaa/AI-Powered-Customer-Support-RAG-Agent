"""
app.py — SupportAI v3 — Earthy Forest Edition
Palette: Deep forest greens + warm browns + cream whites
"""

import time
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="SupportAI — Enterprise Support Platform",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Serif+Display&display=swap');
@import url('https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css');

html, body, [class*="css"], .stApp { font-family: 'Inter', sans-serif !important; }
.stApp { background: #f7f3ed; }
#MainMenu, footer, header { visibility: hidden; }

/* ── Brand bar ── */
.brand-bar {
    background: #243830;
    border-left: 3px solid #4d8b62;
    border-radius: 4px;
    padding: 16px 24px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-top: none;
    border-right: none;
    border-bottom: none;
}
.brand-title {
    font-family: 'DM Serif Display', serif;
    font-size: 1.5rem;
    color: #c8dac0;
    letter-spacing: 0.5px;
}
.brand-subtitle {
    font-size: 0.7rem;
    color: #4d8b62;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-top: 3px;
}
.brand-badge {
    background: #4d8b6218;
    border: 0.5px solid #4d8b6235;
    color: #7aaa87;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.68rem;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: 6px;
}
.live-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: #7aaa87;
    display: inline-block;
}

/* ── Login ── */
.login-wrap {
    background: #faf8f5;
    border: 0.5px solid #c49a7a30;
    border-top: 2px solid #4d8b62;
    border-radius: 4px;
    padding: 40px 36px;
    max-width: 400px;
    margin: 50px auto 0;
}
.login-wordmark {
    font-family: 'DM Serif Display', serif;
    font-size: 2rem;
    color: #243830;
    text-align: center;
    margin-bottom: 4px;
}
.login-tagline {
    text-align: center;
    color: #7a9080;
    font-size: 0.7rem;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 28px;
}

/* ── Chat bubbles ── */
.chat-row { display: flex; margin: 10px 0; align-items: flex-end; gap: 9px; }
.chat-row.user { flex-direction: row-reverse; }

.avatar {
    width: 30px; height: 30px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 600; flex-shrink: 0;
}
.avatar-user { background: #5c3d2e; color: #c49a7a; }
.avatar-ai   { background: #4d8b62; color: #e8f0ea; }

.bubble { max-width: 70%; padding: 12px 16px; border-radius: 12px; font-size: 0.88rem; line-height: 1.65; }
.bubble-user { background: #5c3d2e; color: #e8d5c4; border-bottom-right-radius: 3px; }
.bubble-ai   { background: #faf8f5; color: #2d3a2e; border: 0.5px solid #c49a7a25; border-bottom-left-radius: 3px; }

.bubble-time { font-size: 0.62rem; color: #a09080; margin-top: 4px; }
.bubble-time-r { text-align: right; }
.bubble-time-l { text-align: left; }

/* ── Tags ── */
.tag {
    display: inline-flex; align-items: center; gap: 3px;
    border-radius: 4px; padding: 2px 8px;
    font-size: 0.65rem; font-weight: 500; letter-spacing: 0.3px;
}
.tag-l1    { background: #4d8b6215; color: #2d6b47; border: 0.5px solid #4d8b6228; }
.tag-l2    { background: #9c6b5215; color: #7a4f3a; border: 0.5px solid #9c6b5228; }
.tag-src   { background: #9c6b5212; color: #7a4f3a; border: 0.5px solid #9c6b5220; }
.tag-cache { background: #7aaa8712; color: #4d8b62; border: 0.5px solid #7aaa8725; }

/* ── Source panel ── */
.source-panel {
    background: #f0ece6;
    border: 0.5px solid #c49a7a25;
    border-left: 2px solid #9c6b52;
    border-radius: 4px;
    padding: 9px 13px;
    margin-top: 7px;
    font-size: 0.73rem;
    color: #7a6b5a;
}

/* ── Confidence bar ── */
.conf-row {
    display: inline-flex; align-items: center; gap: 7px;
    font-size: 0.67rem; color: #7a9080; margin-top: 5px;
    text-transform: uppercase; letter-spacing: 0.5px;
}
.conf-track { width: 70px; height: 3px; background: #c49a7a20; border-radius: 2px; overflow: hidden; }
.conf-fill  { height: 100%; border-radius: 2px; }

/* ── Metric cards ── */
.metric-card {
    background: #faf8f5;
    border: 0.5px solid #c49a7a25;
    border-top: 2px solid #4d8b6240;
    border-radius: 4px;
    padding: 20px 18px;
    text-align: center;
}
.metric-value {
    font-family: 'DM Serif Display', serif;
    font-size: 2.2rem;
    color: #243830;
    line-height: 1;
}
.metric-label { font-size: 0.62rem; color: #7a9080; font-weight: 500; margin-top: 6px; letter-spacing: 1.5px; text-transform: uppercase; }
.metric-sub   { font-size: 0.62rem; color: #a09878; margin-top: 3px; }

/* ── Section headers ── */
.section-header {
    font-family: 'DM Serif Display', serif;
    font-size: 1.1rem; color: #243830;
    margin: 22px 0 12px;
    padding-bottom: 8px;
    border-bottom: 0.5px solid #c49a7a30;
}

/* ── Welcome banner ── */
.welcome-banner {
    background: #f0ece6;
    border: 0.5px solid #c49a7a30;
    border-left: 3px solid #4d8b62;
    border-radius: 4px;
    padding: 14px 18px;
    margin-bottom: 18px;
    font-size: 0.86rem;
    color: #5a6b5a;
    line-height: 1.6;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] { background: #243830 !important; border-right: 1px solid #4d8b6220 !important; }
[data-testid="stSidebar"] * { color: #7aaa87 !important; }
[data-testid="stSidebar"] .stButton button {
    background: transparent !important;
    border: 0.5px solid #4d8b6225 !important;
    color: #4d8b62 !important;
    border-radius: 8px !important;
    font-size: 0.8rem !important;
    transition: all 0.15s !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: #4d8b6215 !important;
    border-color: #4d8b6245 !important;
    color: #7aaa87 !important;
}

/* ── Inputs ── */
.stTextInput input {
    background: #f0ece6 !important;
    border: 0.5px solid #c49a7a30 !important;
    border-radius: 8px !important;
    color: #2d3a2e !important;
}
.stChatInput > div {
    background: #faf8f5 !important;
    border: 0.5px solid #c49a7a30 !important;
    border-radius: 10px !important;
}
.stChatInput > div:focus-within { border-color: #4d8b6260 !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] { gap: 0; border-bottom: 0.5px solid #c49a7a25; }
.stTabs [data-baseweb="tab"] {
    border-radius: 0; font-size: 0.73rem; font-weight: 500;
    padding: 9px 18px; color: #7a9080 !important;
    letter-spacing: 0.8px; text-transform: uppercase;
    border-bottom: 2px solid transparent;
}
.stTabs [aria-selected="true"] {
    background: transparent !important;
    color: #4d8b62 !important;
    border-bottom: 2px solid #4d8b62 !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #f0ece6; }
::-webkit-scrollbar-thumb { background: #c49a7a40; border-radius: 2px; }

/* ── Empty state ── */
.empty-state { text-align: center; padding: 70px 20px; }
.empty-title { font-family: 'DM Serif Display', serif; font-size: 1.1rem; color: #7a9080; }
.empty-sub   { font-size: 0.82rem; color: #a09878; margin-top: 8px; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading SupportAI engine...")
def load_rag():
    try:
        from rag_chain import get_rag_chain
        return get_rag_chain(), None
    except Exception as e:
        return None, str(e)

def is_logged_in():
    return "user" in st.session_state and st.session_state["user"] is not None

def current_user():
    return st.session_state.get("user", {})

def is_admin():
    return current_user().get("role") == "admin"

def kb_ready(rag_chain):
    if not rag_chain or not rag_chain.is_ready:
        st.error("Knowledge base not ready. Run python ingest.py then refresh.")
        return False
    return True

def _now():
    return datetime.utcnow().isoformat()

def _brand(title, subtitle):
    st.markdown(f"""
    <div class="brand-bar">
      <div>
        <div class="brand-title">{title}</div>
        <div class="brand-subtitle">{subtitle}</div>
      </div>
      <div class="brand-badge"><span class="live-dot"></span> Live</div>
    </div>""", unsafe_allow_html=True)


# ── AUTH PAGE ─────────────────────────────────────────────────────────────────
def render_auth_page():
    from auth import login_user, register_user
    _, col, _ = st.columns([1, 1.3, 1])
    with col:
        st.markdown("""
        <div class="login-wrap">
          <div class="login-wordmark">SupportAI</div>
          <div class="login-tagline">Enterprise Support Platform</div>
        </div>""", unsafe_allow_html=True)

        tab_l, tab_r = st.tabs(["Sign In", "Create Account"])

        with tab_l:
            st.markdown("<br>", unsafe_allow_html=True)
            email = st.text_input("Email address", placeholder="you@company.com", key="li_email")
            pw    = st.text_input("Password", type="password", key="li_pw")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Sign In", use_container_width=True, type="primary"):
                if email and pw:
                    ok, msg, session = login_user(email, pw)
                    if ok:
                        st.session_state["user"] = {
                            "user_id": session.user_id, "email": session.email,
                            "name": session.name, "role": session.role,
                            "org_id": session.org_id,
                        }
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.error("Please enter your email and password.")
            st.markdown("<hr style='border:none;border-top:0.5px solid #c49a7a25;margin:18px 0'>", unsafe_allow_html=True)
            st.markdown("<div style='font-size:0.72rem;color:#a09878;text-align:center'>Demo: admin@demo.com / Admin@1234</div>", unsafe_allow_html=True)

        with tab_r:
            st.markdown("<br>", unsafe_allow_html=True)
            rn = st.text_input("Full name", key="rn")
            re = st.text_input("Email", key="re")
            ro = st.text_input("Organisation ID", placeholder="acme-corp", key="ro")
            rp = st.text_input("Password (min 8 chars)", type="password", key="rp")
            rp2= st.text_input("Confirm password", type="password", key="rp2")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Create Account", use_container_width=True, type="primary"):
                if all([rn, re, ro, rp, rp2]):
                    if rp == rp2:
                        ok, msg = register_user(re, rn, rp, "agent", ro)
                        (st.success if ok else st.error)(msg)
                    else:
                        st.error("Passwords do not match.")
                else:
                    st.error("Please fill in all fields.")


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
def render_sidebar(rag_chain):
    user = current_user()
    with st.sidebar:
        st.markdown("""
        <div style="padding:18px 4px 14px">
          <div style="font-family:'DM Serif Display',serif;font-size:1.3rem;color:#c8dac0;letter-spacing:0.5px">
            SupportAI
          </div>
          <div style="font-size:0.6rem;color:#4d8b62;margin-top:3px;letter-spacing:2px;text-transform:uppercase">
            Enterprise Platform
          </div>
        </div>""", unsafe_allow_html=True)

        st.markdown("<hr style='border:none;border-top:0.5px solid #4d8b6225;margin:0 0 14px'>", unsafe_allow_html=True)

        role_c = {"admin": "#c49a7a", "agent": "#7aaa87", "viewer": "#7a9080"}.get(user.get("role",""), "#7a9080")
        st.markdown(f"""
        <div style="background:#ffffff07;border:0.5px solid #4d8b6220;border-left:2px solid {role_c};
                    border-radius:8px;padding:11px 13px;margin-bottom:14px">
          <div style="font-weight:500;color:#c8dac0;font-size:0.87rem">{user.get('name','')}</div>
          <div style="font-size:0.68rem;color:#4d8b62;margin-top:2px">{user.get('email','')}</div>
          <div style="margin-top:7px;display:flex;gap:5px">
            <span style="background:{role_c}20;color:{role_c};border:0.5px solid {role_c}35;
                         border-radius:4px;padding:1px 8px;font-size:0.6rem;font-weight:500;
                         letter-spacing:1px;text-transform:uppercase">{user.get('role','').upper()}</span>
            <span style="background:#ffffff08;color:#4d6b52;border:0.5px solid #ffffff12;
                         border-radius:4px;padding:1px 8px;font-size:0.6rem">{user.get('org_id','')}</span>
          </div>
        </div>""", unsafe_allow_html=True)

        st.markdown("<div style='font-size:0.6rem;color:#2d5040;font-weight:500;letter-spacing:1.5px;margin-bottom:6px;text-transform:uppercase'>Navigation</div>", unsafe_allow_html=True)
        pages = ["Chat", "Dashboard"]
        if is_admin():
            pages += ["Evaluation", "Admin"]
        if "current_page" not in st.session_state:
            st.session_state["current_page"] = "Chat"
        icons = {"Chat": "message-2", "Dashboard": "chart-bar", "Evaluation": "test-pipe", "Admin": "users"}
        for p in pages:
            if st.button(f"  {p}", key=f"nav_{p}", use_container_width=True):
                st.session_state["current_page"] = p
                st.rerun()

        st.markdown("<hr style='border:none;border-top:0.5px solid #4d8b6220;margin:14px 0'>", unsafe_allow_html=True)

        kb_ok = rag_chain and rag_chain.is_ready
        sc = "#7aaa87" if kb_ok else "#c49a7a"
        st.markdown(f"""
        <div style="background:#ffffff06;border:0.5px solid #4d8b6218;border-radius:8px;padding:10px 12px">
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
            <span style="width:6px;height:6px;border-radius:50%;background:{sc};display:inline-block"></span>
            <span style="font-size:0.72rem;color:{sc}">{"Operational" if kb_ok else "Offline"}</span>
          </div>
          <div style="font-size:0.65rem;color:#2d5040">{rag_chain.doc_count if rag_chain else 0} chunks indexed</div>
          <div style="font-size:0.65rem;color:#1e3828;margin-top:2px">LLaMA 3.1 · Groq</div>
        </div>""", unsafe_allow_html=True)

        st.markdown("<hr style='border:none;border-top:0.5px solid #4d8b6220;margin:14px 0'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.6rem;color:#2d5040;font-weight:500;letter-spacing:1.5px;margin-bottom:6px;text-transform:uppercase'>Quick Questions</div>", unsafe_allow_html=True)
        for ex in ["Reset my password", "Cancel subscription", "API rate limits", "Refund policy", "SLA guarantee"]:
            if st.button(ex, key=f"q_{ex[:12]}", use_container_width=True):
                st.session_state["prefill_query"] = ex
                st.session_state["current_page"] = "Chat"
                st.rerun()

        st.markdown("<hr style='border:none;border-top:0.5px solid #4d8b6220;margin:14px 0'>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Clear", use_container_width=True):
                from auth import clear_conversation_history
                clear_conversation_history(user["user_id"], user["org_id"])
                st.session_state["messages"] = []
                st.rerun()
        with c2:
            if st.button("Sign Out", use_container_width=True):
                st.session_state.clear()
                st.rerun()


# ── CHAT PAGE ─────────────────────────────────────────────────────────────────
def render_chat_page(rag_chain):
    from auth import save_message, get_conversation_history, save_feedback
    user = current_user()

    _brand("SupportAI Chat", "Retrieval-Augmented Support Assistant")

    if not kb_ready(rag_chain):
        return

    if "messages" not in st.session_state:
        st.session_state["messages"] = get_conversation_history(
            user["user_id"], user["org_id"], limit=40)

    if not st.session_state["messages"]:
        st.markdown(f"""
        <div class="welcome-banner">
          Welcome, <strong style="color:#2d6b47">{user['name']}</strong>.
          Ask anything about billing, accounts, shipping, refunds, or technical issues.
          Every answer comes from the knowledge base — grounded and accurate.
        </div>""", unsafe_allow_html=True)

    for i, msg in enumerate(st.session_state["messages"]):
        _render_msg(msg, i, user, save_feedback)

    prefill = st.session_state.pop("prefill_query", "")
    query   = st.chat_input("Ask a support question...") or prefill

    if query:
        user_msg = {"role": "user", "content": query, "timestamp": _now()}
        st.session_state["messages"].append(user_msg)
        save_message(user["user_id"], user["org_id"], "user", query)

        with st.spinner("Searching knowledge base..."):
            try:
                result = rag_chain.ask(query)
                ai_msg = {
                    "role": "assistant", "content": result.answer,
                    "sources": result.sources, "triage_level": result.triage_level,
                    "triage_reason": result.triage_reason,
                    "confidence_score": result.confidence_score,
                    "from_cache": result.from_cache,
                    "query": query, "timestamp": _now(),
                }
                save_message(user["user_id"], user["org_id"], "assistant",
                             result.answer, result.sources, result.triage_level,
                             result.triage_reason, result.confidence_score, result.from_cache)
            except Exception as e:
                ai_msg = {
                    "role": "assistant", "content": f"Error: {e}",
                    "sources": [], "triage_level": "L2",
                    "triage_reason": "Processing error", "confidence_score": 0.0,
                    "from_cache": False, "query": query, "timestamp": _now(),
                }
        st.session_state["messages"].append(ai_msg)
        st.rerun()


def _render_msg(msg, idx, user, save_fb):
    is_user = msg["role"] == "user"
    initials = user.get("name", "U")[:1].upper()
    ts = msg.get("timestamp", "")[:16].replace("T", " ")

    if is_user:
        st.markdown(f"""
        <div class="chat-row user">
          <div class="avatar avatar-user">{initials}</div>
          <div>
            <div class="bubble bubble-user">{msg['content']}</div>
            <div class="bubble-time bubble-time-r">{ts}</div>
          </div>
        </div>""", unsafe_allow_html=True)
        return

    ans   = msg["content"].replace("\n", "<br>")
    triage= msg.get("triage_level", "L1")
    conf  = msg.get("confidence_score", 0.0) or 0.0
    badge = (f'<span class="tag tag-l1">&#10003; Resolved &middot; L1</span>'
             if triage == "L1"
             else f'<span class="tag tag-l2">&#9651; Escalate &middot; L2</span>')
    if msg.get("from_cache"):
        badge += ' <span class="tag tag-cache">&#9670; Cached</span>'

    bar_pct = int(conf * 100)
    bar_col = "#4d8b62" if conf > 0.6 else "#9c6b52" if conf > 0.35 else "#7a4f3a"

    st.markdown(f"""
    <div class="chat-row">
      <div class="avatar avatar-ai">AI</div>
      <div style="flex:1;min-width:0">
        <div class="bubble bubble-ai">{ans}</div>
        <div style="margin-top:7px;display:flex;flex-wrap:wrap;gap:5px;align-items:center">{badge}</div>
        <div class="conf-row">
          Confidence
          <div class="conf-track">
            <div class="conf-fill" style="width:{bar_pct}%;background:{bar_col}"></div>
          </div>
          {bar_pct}%
        </div>
        <div class="bubble-time bubble-time-l">{ts}</div>
      </div>
    </div>""", unsafe_allow_html=True)

    sources = msg.get("sources", [])
    if sources:
        pills = " &nbsp;".join(
            f'<span class="tag tag-src">&#128196; {s}</span>' for s in sources)
        st.markdown(f"""
        <div class="source-panel">
          <span style="font-size:0.63rem;color:#9c6b52;letter-spacing:1px;text-transform:uppercase">
            Sources used
          </span><br>
          <div style="margin-top:5px">{pills}</div>
          <div style="margin-top:5px;font-size:0.65rem;color:#a09878">{msg.get('triage_reason','')}</div>
        </div>""", unsafe_allow_html=True)

    if triage == "L2":
        with st.expander("This query has been flagged for human review", expanded=True):
            st.warning("Classification: L2 — This question is complex or sensitive. "
                       "Please verify with a human support agent before acting on this response.")

    fc1, fc2, _ = st.columns([1, 1, 12])
    with fc1:
        if st.button("Helpful", key=f"up_{idx}"):
            save_fb(user["user_id"], user["org_id"], msg.get("query",""), msg["content"], "positive")
            st.toast("Feedback recorded.")
    with fc2:
        if st.button("Not helpful", key=f"dn_{idx}"):
            save_fb(user["user_id"], user["org_id"], msg.get("query",""), msg["content"], "negative")
            st.toast("Feedback recorded.")


# ── DASHBOARD ─────────────────────────────────────────────────────────────────
def render_dashboard_page(rag_chain):
    from auth import get_org_stats
    user  = current_user()
    stats = get_org_stats(user["org_id"])
    _brand("Analytics", "Organisation Performance Dashboard")

    total  = stats.get("total_queries") or 0
    l1     = stats.get("l1_count") or 0
    l2     = stats.get("l2_count") or 0
    conf   = stats.get("avg_confidence") or 0.0
    cached = stats.get("cached_count") or 0
    pos_fb = stats.get("positive_feedback") or 0
    neg_fb = stats.get("negative_feedback") or 0
    active = stats.get("active_users") or 0

    st.markdown('<div class="section-header">Performance Metrics</div>', unsafe_allow_html=True)
    for col, lbl, val, sub in zip(
        st.columns(5),
        ["Total Queries","L1 Resolved","L2 Escalated","Avg Confidence","Active Users"],
        [str(total), str(l1), str(l2), f"{conf*100:.1f}%" if conf else "—", str(active)],
        ["All time","Auto-answered","Human review","KB match score", f"Org: {user['org_id']}"],
    ):
        col.markdown(f"""
        <div class="metric-card">
          <div class="metric-value">{val}</div>
          <div class="metric-label">{lbl}</div>
          <div class="metric-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="section-header">Triage Split</div>', unsafe_allow_html=True)
        if total > 0:
            import pandas as pd
            st.bar_chart(pd.DataFrame({"Level":["L1","L2"],"Count":[l1,l2]}).set_index("Level"))
        else:
            st.markdown('<div class="empty-state"><div class="empty-title">No data yet</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="section-header">Satisfaction</div>', unsafe_allow_html=True)
        total_fb = pos_fb + neg_fb
        if total_fb > 0:
            sat = round(pos_fb / total_fb * 100, 1)
            st.markdown(f"""<div class="metric-card">
              <div class="metric-value">{sat}%</div>
              <div class="metric-label">Satisfaction Rate</div>
            </div>""", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:0.8rem;color:#7a9080;margin-top:10px'>{pos_fb} positive &nbsp; {neg_fb} negative</div>", unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-state"><div class="empty-title">No feedback yet</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="section-header">Cache Efficiency</div>', unsafe_allow_html=True)
        if total > 0:
            hit = round(cached / total * 100, 1)
            st.markdown(f"""<div class="metric-card">
              <div class="metric-value">{hit}%</div>
              <div class="metric-label">Cache Hit Rate</div>
              <div class="metric-sub">{cached} of {total} served from cache</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-state"><div class="empty-title">No data yet</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-header">Knowledge Base</div>', unsafe_allow_html=True)
    k1, k2, k3 = st.columns(3)
    k1.metric("Chunks Indexed", rag_chain.doc_count if rag_chain else 0)
    k2.metric("Embedding Model", "MiniLM-L6-v2")
    k3.metric("Language Model", "LLaMA 3.1 · Groq")


# ── EVALUATION ────────────────────────────────────────────────────────────────
def render_eval_page(rag_chain):
    from evaluation import get_eval_history, get_eval_details, run_evaluation
    _brand("Evaluation Centre", "Accuracy · Precision · Recall · F1 · Triage")
    if not kb_ready(rag_chain):
        return

    cb, ci = st.columns([1, 3])
    with cb:
        if st.button("Run Evaluation", type="primary", use_container_width=True):
            with st.spinner("Evaluating 20 test cases..."):
                try:
                    s = run_evaluation(rag_chain, verbose=False)
                    st.success(f"F1: {s.avg_answer_f1*100:.1f}%  Triage: {s.triage_accuracy*100:.1f}%")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")
    with ci:
        st.info("Runs 20 labeled QA pairs without cache. Computes token-level F1, precision, recall, and triage accuracy.")

    history = get_eval_history()
    if not history:
        st.markdown("""<div class="empty-state">
          <div class="empty-title">No evaluation runs yet</div>
          <div class="empty-sub">Click Run Evaluation above to benchmark the system.</div>
        </div>""", unsafe_allow_html=True)
        return

    latest = history[0]
    st.markdown(f'<div class="section-header">Latest Run — {latest["run_id"]}</div>', unsafe_allow_html=True)
    for col, lbl, rv, sub in zip(
        st.columns(5),
        ["Answer F1","Precision","Recall","Triage Accuracy","KB Coverage"],
        [latest["avg_answer_f1"], latest["avg_answer_precision"],
         latest["avg_answer_recall"], latest["triage_accuracy"], latest["coverage_rate"]],
        ["Token-level F1","Answer precision","Answer recall","L1/L2 correct","Relevant docs found"],
    ):
        pct = f"{rv*100:.1f}%"
        c   = "#2d6b47" if rv > 0.7 else "#9c6b52" if rv > 0.4 else "#7a4f3a"
        col.markdown(f"""<div class="metric-card">
          <div style="font-family:'DM Serif Display',serif;font-size:2.1rem;color:{c}">{pct}</div>
          <div class="metric-label">{lbl}</div>
          <div class="metric-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-header">Triage Classification</div>', unsafe_allow_html=True)
    for col, lbl, v in zip(
        st.columns(4),
        ["L1 Precision","L1 Recall","L2 Precision","L2 Recall"],
        [latest["l1_precision"],latest["l1_recall"],latest["l2_precision"],latest["l2_recall"]],
    ):
        col.metric(lbl, f"{v*100:.1f}%")

    st.markdown('<div class="section-header">Per-Question Results</div>', unsafe_allow_html=True)
    details = get_eval_details(latest["run_id"])
    if details:
        import pandas as pd
        rows = [{
            "Question": d["question"][:68]+"…" if len(d["question"])>68 else d["question"],
            "F1":       f"{d.get('answer_f1',0)*100:.0f}%",
            "Precision":f"{d.get('answer_precision',0)*100:.0f}%",
            "Recall":   f"{d.get('answer_recall',0)*100:.0f}%",
            "KB Score": f"{d.get('retrieval_score',0):.2f}",
            "Triage":   f"{'Pass' if d.get('triage_correct') else 'Fail'} · {d.get('predicted_triage','')}",
            "Latency":  f"{d.get('latency_ms',0):.0f} ms",
        } for d in details]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=400)

    if len(history) > 1:
        st.markdown('<div class="section-header">F1 Score Over Time</div>', unsafe_allow_html=True)
        import pandas as pd
        df = pd.DataFrame([{"Run": h["run_id"], "F1": h["avg_answer_f1"],
                            "Triage": h["triage_accuracy"]} for h in reversed(history)]).set_index("Run")
        st.line_chart(df)


# ── ADMIN ─────────────────────────────────────────────────────────────────────
def render_admin_page():
    import sqlite3
    from auth.auth_manager import DB_PATH, register_user
    user = current_user()
    _brand("Admin Panel", "User Management · Organisation Settings")

    st.markdown('<div class="section-header">Create New User</div>', unsafe_allow_html=True)
    with st.form("create_user"):
        c1, c2 = st.columns(2)
        with c1:
            nn = st.text_input("Full name")
            ne = st.text_input("Email address")
        with c2:
            nr = st.selectbox("Role", ["agent","viewer","admin"])
            no = st.text_input("Organisation ID", value=user["org_id"])
        np_ = st.text_input("Temporary password", type="password")
        if st.form_submit_button("Create User", type="primary"):
            if all([nn, ne, nr, no, np_]):
                ok, msg = register_user(ne, nn, np_, nr, no)
                (st.success if ok else st.error)(msg)
            else:
                st.error("Please fill in all fields.")

    st.markdown('<div class="section-header">All Users</div>', unsafe_allow_html=True)
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id,name,email,role,org_id,is_active,created_at,last_login FROM users ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        import pandas as pd
        data = [{"ID":r["id"],"Name":r["name"],"Email":r["email"],"Role":r["role"].upper(),
                 "Org":r["org_id"],"Active":"Yes" if r["is_active"] else "No",
                 "Created":r["created_at"][:10],
                 "Last Login":(r["last_login"] or "Never")[:16].replace("T"," ")} for r in rows]
        st.dataframe(pd.DataFrame(data), use_container_width=True, height=300)
    except Exception as e:
        st.error(f"Could not load users: {e}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    rag_chain, load_error = load_rag()

    if not is_logged_in():
        render_auth_page()
        return

    render_sidebar(rag_chain)

    if load_error:
        st.error(f"RAG engine failed: {load_error}")
        st.info("Check your .env has GROQ_API_KEY and run python ingest.py")
        return

    page = st.session_state.get("current_page", "Chat")
    if   page == "Chat":       render_chat_page(rag_chain)
    elif page == "Dashboard":  render_dashboard_page(rag_chain)
    elif page == "Evaluation": render_eval_page(rag_chain)
    elif page == "Admin":      render_admin_page() if is_admin() else st.error("Access denied.")

if __name__ == "__main__":
    main()
