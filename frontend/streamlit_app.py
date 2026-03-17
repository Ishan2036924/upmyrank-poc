# Run with: streamlit run frontend/streamlit_app.py
# Requires: FastAPI server running on localhost:8000

"""
UpMyRank — AI Tutor Frontend

Two-page Streamlit app:
  Page 1 — AI Tutor   : Socratic chat interface + knowledge genome sidebar
  Page 2 — Mock Test  : Practice problems with verified answer checking
"""
from __future__ import annotations

import re

import httpx
import streamlit as st

# ─── Constants ─────────────────────────────────────────────────────────────────

API_BASE         = "http://localhost:8000"
TEST_STUDENT_ID  = "00e92458-39e8-41c9-beda-789b077dd6a2"
TEST_STUDENT_NAME = "Test Student (JEE 2026)"

TOPIC_OPTIONS = [
    "Any",
    "Cartesian Product of Sets",
    "Definition and Examples of Relations",
    "Reflexive Relations",
    "Symmetric Relations",
    "Transitive Relations",
    "Equivalence Relations",
    "Definition and Types of Functions",
    "One-to-One (Injective) Functions",
    "Onto (Surjective) Functions",
    "Bijective Functions",
    "Composition of Functions",
    "Inverse of a Function",
]

HINT_LABELS = {
    1: ("💡", "Conceptual Nudge"),
    2: ("🔍", "Structural Approach"),
    3: ("📐", "Partial Solution (60–70%)"),
}

# ─── Page configuration ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="UpMyRank — AI Tutor",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Genome progress bars */
.bar-row {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 3px 0;
}
.bar-label {
    width: 170px;
    font-size: 11.5px;
    color: #555;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex-shrink: 0;
}
.bar-bg {
    flex: 1;
    background: #e4e4e4;
    border-radius: 5px;
    height: 7px;
    min-width: 60px;
}
.bar-fill {
    height: 7px;
    border-radius: 5px;
}
.bar-pct {
    width: 30px;
    font-size: 11px;
    font-weight: 700;
    text-align: right;
    flex-shrink: 0;
}

/* Weak concept chips */
.weak-chip {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 8px;
    background: #fff5f5;
    border-left: 3px solid #e74c3c;
    border-radius: 0 5px 5px 0;
    margin: 3px 0;
    font-size: 12px;
}

/* Hint / analysis badges */
.badge {
    display: inline-block;
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 11px;
    margin-bottom: 6px;
}
.badge-hint  { background: #e8f4ff; color: #1a5fa8; }
.badge-full  { background: #e8ffe8; color: #1a7a1a; }
.badge-info  { background: #f0f0f0; color: #555; }

/* Verification strip */
.verify-strip {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 12px;
    margin-top: 6px;
}
.verify-ok   { background: #f0fff0; border: 1px solid #27ae60; }
.verify-warn { background: #fffbea; border: 1px solid #f39c12; }
</style>
""", unsafe_allow_html=True)


# ─── LaTeX post-processor ──────────────────────────────────────────────────────

def fix_latex(text: str) -> str:
    """Convert LLM math notation variants to Streamlit-compatible $…$."""
    # \( ... \) → $...$
    text = re.sub(r'\\\(\s*', '$', text)
    text = re.sub(r'\s*\\\)', '$', text)
    # \[ ... \] → $$...$$
    text = re.sub(r'\\\[\s*', '$$', text)
    text = re.sub(r'\s*\\\]', '$$', text)
    # ( \command... ) → $\command...$
    text = re.sub(
        r'\(\s*((?:[^()]*\\[a-zA-Z]+[^()]*)+)\s*\)',
        r'$\1$', text
    )
    # [ expression with backslash ] → $$...$$
    text = re.sub(
        r'\[\s*((?:[^\[\]]*\\[a-zA-Z]+[^\[\]]*)+)\s*\]',
        r'$$\1$$', text
    )
    text = re.sub(r'\$\$\s*\$\$', '$$', text)
    return text


# ─── API helpers ───────────────────────────────────────────────────────────────

def _api_get(path: str) -> dict | None:
    """GET request; returns parsed JSON or None on any error."""
    try:
        r = httpx.get(f"{API_BASE}{path}", timeout=30.0)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        st.error("❌ Cannot reach FastAPI server on localhost:8000. "
                 "Start it with: `poetry run uvicorn app.main:app --reload --port 8000`")
        return None
    except httpx.HTTPStatusError as exc:
        st.error(f"❌ API {exc.response.status_code}: {exc.response.text[:250]}")
        return None
    except Exception as exc:
        st.error(f"❌ Unexpected error: {exc}")
        return None


def _api_post(path: str, payload: dict) -> dict | None:
    """POST request; returns parsed JSON or None on any error."""
    try:
        r = httpx.post(f"{API_BASE}{path}", json=payload, timeout=90.0)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        st.error("❌ Cannot reach FastAPI server on localhost:8000.")
        return None
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300]
        st.error(f"❌ API {exc.response.status_code}: {detail}")
        return None
    except Exception as exc:
        st.error(f"❌ Unexpected error: {exc}")
        return None


# ─── Genome helpers ────────────────────────────────────────────────────────────

def _score_color(score: float) -> str:
    if score < 0.4:
        return "#e74c3c"
    if score < 0.7:
        return "#f39c12"
    return "#27ae60"


def _render_bar(label: str, score: float, label_width: int = 170):
    color = _score_color(score)
    pct   = int(score * 100)
    st.markdown(f"""
<div class="bar-row">
  <span class="bar-label" style="width:{label_width}px;" title="{label}">{label}</span>
  <div class="bar-bg">
    <div class="bar-fill" style="width:{pct}%;background:{color};"></div>
  </div>
  <span class="bar-pct" style="color:{color};">{pct}%</span>
</div>""", unsafe_allow_html=True)


def _load_student() -> dict | None:
    """Fetch fresh student genome and cache it in session_state."""
    data = _api_get(f"/student/{TEST_STUDENT_ID}")
    if data:
        st.session_state.student_data = data
    return data


# ─── Sidebar ───────────────────────────────────────────────────────────────────

def _render_sidebar(active_page: str):
    """Render the full sidebar: branding, genome, weak concepts, stats."""
    with st.sidebar:
        st.markdown("## 🎯 UpMyRank")
        st.caption("AI-Powered JEE/NEET Tutor · POC")
        st.divider()

        # Student picker (hardcoded for POC, easily extendable)
        st.selectbox(
            "Student",
            [TEST_STUDENT_NAME],
            label_visibility="collapsed",
        )

        col_r, col_h = st.columns([4, 1])
        with col_h:
            refresh = st.button("🔄", help="Refresh genome", key="sb_refresh")

        if refresh or st.session_state.get("student_data") is None:
            with st.spinner("Loading…"):
                _load_student()

        data = st.session_state.get("student_data")
        if not data:
            st.warning("Could not load student genome.")
            return

        # ── Overall mastery ───────────────────────────────────────────────────
        overall = data.get("overall_mastery", 0.0)
        oc      = _score_color(overall)
        pct_o   = int(overall * 100)
        st.markdown(f"**Overall Mastery &nbsp; "
                    f"<span style='color:{oc};font-size:15px;'>{pct_o}%</span>**",
                    unsafe_allow_html=True)
        st.progress(overall)
        st.markdown("")

        # ── Per-topic breakdown ───────────────────────────────────────────────
        for topic, info in data.get("topic_mastery", {}).items():
            avg      = info.get("average", 0.0)
            concepts = info.get("concepts", [])
            with st.expander(
                f"**{topic}** — {int(avg * 100)}%",
                expanded=True,
            ):
                for c in concepts:
                    sub = c.get("subtopic", c["concept_id"])
                    # Trim label to fit sidebar width
                    lbl = sub.split("(")[0].strip()
                    if len(lbl) > 26:
                        lbl = lbl[:24] + "…"
                    _render_bar(lbl, c["mastery"])

        st.divider()

        # ── Weakest concepts — sorted lowest first ────────────────────────────
        weakest = sorted(
            data.get("weakest_concepts", []),
            key=lambda x: x["mastery"],
        )
        if weakest:
            st.markdown("**⚠️ Needs Review**")
            for c in weakest:
                sc  = c["mastery"]
                col = _score_color(sc)
                lbl = c.get("subtopic", c["concept_id"]).split("(")[0].strip()
                st.markdown(f"""
<div class="weak-chip">
  <span>{lbl}</span>
  <span style="color:{col};font-weight:bold;">{int(sc*100)}%</span>
</div>""", unsafe_allow_html=True)
            st.markdown("")

        # ── Session stats ─────────────────────────────────────────────────────
        total    = data.get("total_sessions", 0)
        resolved = data.get("resolved_sessions", 0)
        st.caption(f"📊 Sessions: {total} total · {resolved} resolved")


# ─── Session-state initialisation ──────────────────────────────────────────────

def _init_tutor_state():
    defaults = {
        "messages":          [],       # list of {role, content, meta}
        "session_id":        None,     # active doubt session UUID
        "hint_level":        0,        # how many hints given so far
        "concepts":          [],       # concept IDs involved in session
        "session_resolved":  False,
        "student_data":      None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset_session():
    st.session_state.messages         = []
    st.session_state.session_id       = None
    st.session_state.hint_level       = 0
    st.session_state.concepts         = []
    st.session_state.session_resolved = False


# ─── Chat message rendering ────────────────────────────────────────────────────

def _render_messages():
    for msg in st.session_state.messages:
        role    = msg["role"]      # "student" | "tutor"
        content = msg["content"]
        meta    = msg.get("meta", {})

        with st.chat_message("user" if role == "student" else "assistant"):

            # Analysis expander (first tutor turn in a session)
            if role == "tutor" and meta.get("analysis"):
                ana   = meta["analysis"]
                topic = ana.get("topic", "—")
                diff  = ana.get("difficulty", "—")
                ptype = ana.get("problem_type", "—")
                with st.expander(
                    f"📊 Analysis · **{topic}** · Difficulty {diff}/10 · {ptype}"
                ):
                    st.json(ana)

            # Hint / full-solution badge
            hl  = meta.get("hint_level")
            ifs = meta.get("is_full_solution", False)
            if hl:
                if ifs:
                    st.markdown(
                        '<span class="badge badge-full">🔓 Full Solution</span>',
                        unsafe_allow_html=True,
                    )
                else:
                    icon, label = HINT_LABELS.get(hl, ("💡", f"Hint {hl}"))
                    st.markdown(
                        f'<span class="badge badge-hint">{icon} Hint {hl} — {label}</span>',
                        unsafe_allow_html=True,
                    )

            # Main content — apply LaTeX fix then render
            if meta.get("out_of_scope"):
                st.warning(fix_latex(content))
            else:
                st.markdown(fix_latex(content))

            # Verification strip (full solutions only)
            vr = meta.get("verification")
            if vr:
                flagged    = vr.get("flagged_for_review", False)
                conf       = vr.get("confidence", 0.0)
                method     = vr.get("method", "llm").upper()
                errors     = vr.get("errors", [])

                if flagged:
                    warn_text = (
                        f"⚠️ Flagged for review · "
                        f"Confidence: {conf:.0%} · Method: {method}"
                    )
                    if errors:
                        error_list = "\n".join(f"- {e}" for e in errors)
                        warn_text += f"\n\n**Issues found:**\n{error_list}"
                    st.warning(warn_text)
                else:
                    st.success(
                        f"✅ Verified · Confidence: {conf:.0%} · Method: {method}"
                    )


# ─── AI TUTOR PAGE ──────────────────────────────────────────────────────────────

def page_ai_tutor():
    _init_tutor_state()
    _render_sidebar("tutor")

    st.title("🤖 AI Tutor")
    st.caption(
        "Socratic mode · NCERT Class 12 Math — Relations & Functions · "
        "The tutor guides you step-by-step rather than giving direct answers."
    )

    # ── Render conversation history ────────────────────────────────────────────
    _render_messages()

    # ── Active session action bar ──────────────────────────────────────────────
    session_id = st.session_state.session_id
    resolved   = st.session_state.session_resolved
    hl         = st.session_state.hint_level

    if session_id and not resolved:
        st.divider()

        # Progress indicator
        hints_left  = max(0, 3 - hl)
        prog_label  = f"Hint {hl}/3 used" if hl > 0 else "No hints used yet"
        st.caption(f"🎯 Session active · {prog_label} · {hints_left} hint(s) remaining")

        # Four action buttons
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            hint_label = (
                f"💡 Get Hint ({hl}/3)"  if hl < 3
                else "🔓 Show Full Solution"
            )
            btn_hint = st.button(hint_label, key="btn_hint", use_container_width=True)

        with c2:
            btn_solved = st.button(
                "✅ I Solved It!", key="btn_solved", use_container_width=True
            )

        with c3:
            btn_full = st.button(
                "📖 Full Solution", key="btn_full", use_container_width=True
            )

        with c4:
            btn_new = st.button("🔁 New", key="btn_new", use_container_width=True)

        # ── Get Hint ──────────────────────────────────────────────────────────
        if btn_hint:
            with st.spinner("Thinking…"):
                res = _api_post("/doubt/hint", {"session_id": session_id})
            if res:
                new_hl    = res.get("hint_level", hl + 1)
                is_full   = res.get("is_full_solution", False)
                resolved_ = res.get("resolved", False)
                st.session_state.hint_level       = new_hl
                st.session_state.session_resolved = resolved_
                st.session_state.messages.append({
                    "role":    "tutor",
                    "content": res.get("response", ""),
                    "meta": {
                        "hint_level":      new_hl,
                        "is_full_solution": is_full,
                        "verification":    res.get("verification"),
                    },
                })
                if resolved_:
                    _load_student()  # refresh genome
                st.rerun()

        # ── Show Full Solution (jump straight there) ───────────────────────────
        if btn_full:
            with st.spinner("Generating full solution…"):
                last = None
                for _ in range(6):   # safety cap
                    res = _api_post("/doubt/hint", {"session_id": session_id})
                    if not res:
                        break
                    last = res
                    st.session_state.hint_level = res.get("hint_level", 0)
                    if res.get("resolved") or res.get("is_full_solution"):
                        break
            if last:
                st.session_state.session_resolved = last.get("resolved", True)
                st.session_state.messages.append({
                    "role":    "tutor",
                    "content": last.get("response", ""),
                    "meta": {
                        "hint_level":      last.get("hint_level"),
                        "is_full_solution": True,
                        "verification":    last.get("verification"),
                    },
                })
                _load_student()
                st.rerun()

        # ── I Solved It! ──────────────────────────────────────────────────────
        if btn_solved:
            concepts = st.session_state.concepts
            with st.spinner("Updating mastery…"):
                for cid in concepts:
                    _api_post(
                        f"/student/{TEST_STUDENT_ID}/update-mastery",
                        {"concept_id": cid, "performance_score": 1.0},
                    )
            st.session_state.session_resolved = True
            st.session_state.messages.append({
                "role":    "tutor",
                "content": (
                    "🎉 **Excellent work!** Your mastery scores have been updated "
                    "to reflect that you solved this independently. "
                    "Check the sidebar to see your updated knowledge genome!"
                ),
                "meta": {},
            })
            _load_student()
            st.rerun()

        # ── New Question ──────────────────────────────────────────────────────
        if btn_new:
            _reset_session()
            st.rerun()

    elif resolved:
        # Completion banner
        col_msg, col_btn = st.columns([4, 1])
        with col_msg:
            st.success(
                "✅ Session complete! Start a new question below or "
                "check your updated knowledge genome in the sidebar."
            )
        with col_btn:
            if st.button("🔁 New Question", key="btn_new_resolved"):
                _reset_session()
                st.rerun()

    # ── Chat input (shown only when no active unresolved session) ─────────────
    if not session_id or resolved:
        question = st.chat_input(
            "Ask a question about Relations & Functions…",
        )
        if question:
            # Append student message immediately
            st.session_state.messages.append({
                "role": "student", "content": question, "meta": {}
            })

            with st.spinner("Analyzing your question…"):
                res = _api_post("/doubt/ask", {
                    "question":   question,
                    "student_id": TEST_STUDENT_ID,
                    "subject":    "Mathematics",
                })

            if res:
                st.session_state.session_id       = res.get("session_id")
                st.session_state.concepts         = res.get("concepts_involved", [])
                st.session_state.hint_level       = 0
                st.session_state.session_resolved = False
                st.session_state.messages.append({
                    "role":    "tutor",
                    "content": res.get("response", ""),
                    "meta":    {
                        "analysis":    res.get("analysis"),
                        "out_of_scope": res.get("out_of_scope", False),
                    },
                })
            st.rerun()


# ─── MOCK TEST PAGE ─────────────────────────────────────────────────────────────

def _init_mock_state():
    defaults = {
        "mock_problem":        None,
        "mock_result":         None,
        "student_data":        None,
        "questions_attempted": 0,
        "questions_correct":   0,
        "current_streak":      0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def page_mock_test():
    _init_mock_state()
    _render_sidebar("mock")

    st.title("📝 Mock Test")
    st.caption(
        "Practice problems from the NCERT Relations & Functions chapter. "
        "Your answers are verified by a two-layer pipeline (SymPy + GPT-4o-mini)."
    )

    # ── Score counter ──────────────────────────────────────────────────────────
    attempted = st.session_state.get("questions_attempted", 0)
    correct   = st.session_state.get("questions_correct", 0)
    streak    = st.session_state.get("current_streak", 0)
    st.markdown(f"📊 **Score: {correct}/{attempted}** · Streak: {streak} 🔥")
    st.markdown("")

    # ── Problem configuration ──────────────────────────────────────────────────
    cfg_col1, cfg_col2, cfg_col3, cfg_col4 = st.columns([2, 3, 2, 2])

    with cfg_col1:
        subject = st.selectbox("Subject", ["Mathematics"], key="mt_subject")

    with cfg_col2:
        topic_choice = st.selectbox("Topic", TOPIC_OPTIONS, key="mt_topic")

    with cfg_col3:
        difficulty = st.slider(
            "Difficulty", 0.1, 1.0, 0.5, 0.1, format="%.1f", key="mt_diff"
        )

    with cfg_col4:
        st.markdown("")  # spacer
        st.markdown("")  # spacer
        gen_btn = st.button(
            "🎲 Generate Question", key="mt_gen", use_container_width=True
        )

    if gen_btn:
        payload: dict = {"subject": subject, "difficulty": difficulty}
        if topic_choice != "Any":
            payload["topic"] = topic_choice
        with st.spinner("Fetching a problem…"):
            res = _api_post("/mock/generate", payload)
        if res:
            st.session_state.mock_problem = res
            st.session_state.mock_result  = None
            st.rerun()

    st.divider()

    # ── Display problem ────────────────────────────────────────────────────────
    problem = st.session_state.mock_problem
    if not problem:
        st.info(
            "👆 Choose a topic and difficulty, then click **Generate Question** to begin."
        )
        return

    diff_val = problem.get("difficulty", 0.5)
    # Difficulty display: 100% = hardest, colour inverted (hard=red, easy=green)
    diff_color = _score_color(1.0 - diff_val)
    diff_pct   = int(diff_val * 100)

    sub_label = problem.get("subtopic") or ""
    topic_label = problem.get("topic", "—")
    full_topic = f"{topic_label} · {sub_label}" if sub_label else topic_label

    st.markdown(
        f"**Topic:** {full_topic} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"**Difficulty:** <span style='color:{diff_color};font-weight:700;'>"
        f"{diff_pct}%</span>",
        unsafe_allow_html=True,
    )
    st.markdown("")

    # Question in a highlighted block
    with st.container(border=True):
        st.markdown("**❓ Question**")
        st.markdown(fix_latex(problem.get("question_text", "")))

    st.markdown("")

    # ── Answer input ───────────────────────────────────────────────────────────
    st.markdown("**✏️ Your Answer**")
    st.caption(
        "Tip: use `$x^2$` for inline LaTeX or `$$\\frac{a}{b}$$` for display math."
    )
    answer = st.text_area(
        "answer",
        key="mt_answer",
        height=130,
        label_visibility="collapsed",
        placeholder="Type your complete answer here…",
    )

    sub_col, new_col, _ = st.columns([2, 2, 4])
    with sub_col:
        submit_btn = st.button(
            "📤 Submit Answer",
            key="mt_submit",
            disabled=not answer.strip(),
            use_container_width=True,
        )
    with new_col:
        new_btn = st.button(
            "🔁 New Question",
            key="mt_new",
            use_container_width=True,
        )

    if new_btn:
        st.session_state.mock_problem = None
        st.session_state.mock_result  = None
        st.rerun()

    if submit_btn and answer.strip():
        with st.spinner("Verifying your answer…"):
            res = _api_post("/mock/submit", {
                "problem_id": problem["problem_id"],
                "answer":     answer.strip(),
                "student_id": TEST_STUDENT_ID,
            })
        if res:
            st.session_state.mock_result = res
            # Update score counters
            st.session_state.questions_attempted += 1
            if res.get("correct", False):
                st.session_state.questions_correct += 1
                st.session_state.current_streak   += 1
            else:
                st.session_state.current_streak = 0
            _load_student()   # refresh genome after mastery update
            st.rerun()

    # ── Result display ─────────────────────────────────────────────────────────
    result = st.session_state.mock_result
    if not result:
        return

    st.divider()
    st.markdown("### 📊 Result")

    correct_ans = result.get("correct", False)
    confidence  = result.get("confidence", 0.0)
    method      = result.get("verification_method", "llm").upper()
    flagged     = result.get("flagged_for_review", False)

    # Verdict banner
    if correct_ans:
        st.success(
            f"✅ **Correct!** &nbsp; Confidence: {confidence:.0%} · Method: {method}"
        )
    else:
        st.error(
            f"❌ **Incorrect.** &nbsp; Confidence: {confidence:.0%} · Method: {method}"
        )

    if flagged:
        st.warning(
            "⚠️ The verifier flagged this result for human review — "
            "please check the explanation carefully."
        )

    # Explanation
    explanation = result.get("explanation", "")
    if explanation:
        with st.expander("📋 Explanation", expanded=True):
            st.markdown(fix_latex(explanation))

    # Verified answer
    verified_ans = result.get("verified_answer", "")
    if verified_ans and verified_ans != "See solution steps.":
        with st.expander("✅ Verified Answer", expanded=not correct_ans):
            st.markdown(fix_latex(verified_ans))

    # Concepts tested — colored badge pills
    concepts = result.get("concepts_tested", [])
    if concepts:
        badge_colors = ["#e8f4ff", "#e8ffe8", "#fff5e8", "#f5e8ff"]
        text_colors  = ["#1a5fa8", "#1a7a1a", "#a86a1a", "#6a1a7a"]
        badges_html  = ""
        for i, c in enumerate(concepts):
            bg  = badge_colors[i % len(badge_colors)]
            col = text_colors[i % len(text_colors)]
            badges_html += (
                f'<span style="display:inline-block;background:{bg};color:{col};'
                f'border-radius:12px;padding:2px 10px;font-size:11px;'
                f'margin:2px 3px;">{c}</span>'
            )
        st.markdown(f"**Concepts tested:** {badges_html}", unsafe_allow_html=True)

    # Mastery updates
    updates = result.get("mastery_updates", [])
    if updates:
        with st.expander("📈 Mastery Updates", expanded=True):
            for u in updates:
                delta = round(u["new_mastery"] - u["old_mastery"], 4)
                arrow = "▲" if delta >= 0 else "▼"
                color = "#27ae60" if delta >= 0 else "#e74c3c"
                cid   = u["concept_id"]
                st.markdown(
                    f"**`{cid}`** &nbsp; "
                    f"{u['old_mastery']:.3f} → **{u['new_mastery']:.3f}** &nbsp; "
                    f"<span style='color:{color};font-weight:700;'>{arrow} {abs(delta):.3f}</span> "
                    f"· Next review in {u['interval_days']} day(s)",
                    unsafe_allow_html=True,
                )


# ─── Sidebar navigation + routing ─────────────────────────────────────────────

# Top-level nav must be declared before page functions consume sidebar space
_NAV_OPTIONS = ["🤖 AI Tutor", "📝 Mock Test"]
with st.sidebar:
    selected = st.radio(
        "Navigate",
        _NAV_OPTIONS,
        label_visibility="collapsed",
        key="nav_radio",
    )
    st.divider()

if selected == "🤖 AI Tutor":
    page_ai_tutor()
else:
    page_mock_test()

# ─── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("UpMyRank POC · Built with FastAPI + pgvector + GPT-4o-mini · NCERT Class 12 Relations & Functions")
