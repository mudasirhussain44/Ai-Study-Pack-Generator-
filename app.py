import os
import re
from typing import Any, Dict

import streamlit as st

from workflow import WorkflowError, run_study_workflow


st.set_page_config(
    page_title="AI Study Pack Generator",
    page_icon="📚",
    layout="wide",
)


def get_api_key() -> str:
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
        if key:
            return str(key)
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY", "")


def safe_filename(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", text).strip("_")
    return value or "study_pack"


def render_markdown(pack: Dict[str, Any]) -> str:
    lines = [f"# 📚 {pack.get('title', 'AI Study Pack')}", ""]

    if pack.get("quick_summary"):
        lines += ["## 1. Quick Summary", str(pack["quick_summary"]), ""]

    concepts = pack.get("key_concepts", [])
    if concepts:
        lines.append("## 2. Key Concepts")
        for item in concepts:
            lines += [
                f"### {item.get('concept', 'Concept')}",
                str(item.get("explanation", "")),
            ]
            if item.get("example"):
                lines.append(f"**Example:** {item['example']}")
            lines.append("")

    definitions = pack.get("important_definitions", [])
    if definitions:
        lines.append("## 3. Important Definitions")
        for item in definitions:
            lines.append(
                f"- **{item.get('term', 'Term')}:** "
                f"{item.get('definition', '')}"
            )
        lines.append("")

    examples = pack.get("worked_examples", [])
    if examples:
        lines.append("## 4. Worked Examples")
        for i, item in enumerate(examples, 1):
            lines += [
                f"### Example {i}",
                f"**Question:** {item.get('question', '')}",
                f"**Solution:** {item.get('solution', '')}",
                "",
            ]

    questions = pack.get("practice_questions", [])
    if questions:
        lines.append("## 5. Practice Questions")
        for item in questions:
            lines += [
                f"### Question {item.get('number', '')} — "
                f"{item.get('type', '')} — {item.get('difficulty', '')}",
                str(item.get("question", "")),
            ]
            for option in item.get("options", []):
                lines.append(f"- {option}")
            lines += [
                "",
                f"**Answer:** {item.get('answer', '')}",
                f"**Explanation:** {item.get('explanation', '')}",
                "",
            ]

    tips = pack.get("exam_tips", [])
    if tips:
        lines += ["## 6. Exam Tips"]
        lines.extend(f"- {tip}" for tip in tips)
        lines.append("")

    mistakes = pack.get("common_mistakes", [])
    if mistakes:
        lines += ["## 7. Common Mistakes"]
        lines.extend(f"- {mistake}" for mistake in mistakes)
        lines.append("")

    notes = pack.get("final_quality_notes", [])
    if notes:
        lines += ["## 8. Final Quality Notes"]
        lines.extend(f"- {note}" for note in notes)
        lines.append("")

    lines += [
        "---",
        "*AI-assisted educational material. Verify important academic "
        "information with your course resources.*",
    ]
    return "\n".join(lines)


st.sidebar.title("⚙️ Settings")

api_key = st.sidebar.text_input(
    "Gemini API Key",
    value=get_api_key(),
    type="password",
)

model = st.sidebar.text_input(
    "Gemini Model",
    value="gemini-2.5-flash",
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
### 🔄 AI Workflow

1. 🧠 Planning
2. ✍️ Content Generation
3. 🔍 Assignment Review
4. ✨ Refinement
"""
)
st.sidebar.caption("Context is passed between every stage.")

st.title("📚 AI Study Pack Generator")
st.write(
    "Create personalized study material using a four-stage AI workflow."
)

st.markdown("---")
st.subheader("🎯 Study Pack Settings")

with st.form("study_pack_form"):
    col1, col2 = st.columns(2)

    with col1:
        subject = st.text_input(
            "📖 Subject",
            placeholder="e.g. Statistics",
        )
        topic = st.text_input(
            "🎯 Topic",
            placeholder="e.g. Hypothesis Testing",
        )
        level = st.selectbox(
            "🎓 Student Level",
            ["Beginner", "High School", "College / University", "Professional"],
        )
        language = st.selectbox(
            "🌐 Language",
            ["English", "Simple English", "Roman Urdu", "Urdu"],
        )

    with col2:
        pack_type = st.selectbox(
            "📝 Study Pack Type",
            [
                "Complete Study Pack",
                "Exam Preparation Pack",
                "Quick Revision Pack",
                "Practice Questions Pack",
                "Concept Explanation Pack",
            ],
        )
        difficulty = st.select_slider(
            "📊 Difficulty",
            ["Easy", "Medium", "Hard", "Mixed"],
            value="Mixed",
        )
        question_count = st.slider(
            "❓ Practice Questions",
            5, 30, 10, 5
        )
        learning_goal = st.text_area(
            "🎯 Learning Goal",
            placeholder="e.g. Prepare for my university exam.",
        )

    submitted = st.form_submit_button(
        "🚀 Generate Study Pack",
        type="primary",
        use_container_width=True,
    )

if submitted:
    if not api_key:
        st.error(
            "Gemini API key is missing. Add it in the sidebar or "
            "configure GEMINI_API_KEY in Streamlit Secrets."
        )
        st.stop()

    if not subject.strip() or not topic.strip():
        st.warning("Please enter both subject and topic.")
        st.stop()

    user_context = {
        "subject": subject.strip(),
        "topic": topic.strip(),
        "level": level,
        "language": language,
        "pack_type": pack_type,
        "difficulty": difficulty,
        "question_count": question_count,
        "learning_goal": learning_goal.strip()
        or "Understand the topic and prepare for assessment.",
    }

    progress = st.progress(0)
    status = st.empty()

    def on_stage(stage: str, value: int):
        progress.progress(value)
        messages = {
            "Planning": "🧠 Stage 1/4 — Planning...",
            "Content Generation": "✍️ Stage 2/4 — Generating content...",
            "Assignment Review": "🔍 Stage 3/4 — Reviewing content...",
            "Refinement": "✨ Stage 4/4 — Refining final pack...",
            "Complete": "✅ All stages completed!",
        }
        status.info(messages.get(stage, stage))

    try:
        result = run_study_workflow(
            api_key=api_key.strip(),
            model=model.strip(),
            user_context=user_context,
            on_stage=on_stage,
        )
        st.session_state["workflow_result"] = result
        st.session_state["user_context"] = user_context
        status.success("🎉 Study pack generated successfully!")

    except WorkflowError as exc:
        status.error("❌ Workflow stopped.")
        st.error(str(exc))
        st.info("Check your API key, model, connection, and try again.")

    except Exception as exc:
        status.error("❌ Unexpected application error.")
        st.error(f"Please try again. Details: {exc}")


result = st.session_state.get("workflow_result")

if result:
    st.markdown("---")
    st.subheader("📊 Workflow Results")

    review = result.get("review") or {}
    score = review.get("overall_score", 0)

    c1, c2 = st.columns(2)
    with c1:
        st.metric("AI Review Score", f"{score}/100")
    with c2:
        if review.get("status") == "PASS":
            st.success("Review Status: PASS")
        else:
            st.warning("Review Status: NEEDS REFINEMENT")

    tabs = st.tabs(
        ["✨ Final Study Pack", "🧠 Planning", "✍️ Draft", "🔍 Review"]
    )

    with tabs[0]:
        final_pack = result.get("final")
        if final_pack:
            markdown = render_markdown(final_pack)
            st.markdown(markdown)

            filename = (
                f"{safe_filename(st.session_state['user_context']['topic'])}"
                "_study_pack.md"
            )

            st.download_button(
                "⬇️ Download Study Pack",
                data=markdown,
                file_name=filename,
                mime="text/markdown",
                use_container_width=True,
            )

    with tabs[1]:
        st.json(result.get("plan", {}))

    with tabs[2]:
        st.json(result.get("draft", {}))

    with tabs[3]:
        st.json(result.get("review", {}))

st.markdown("---")
st.caption(
    "AI Study Pack Generator • Planning → Generation → Review → Refinement"
)
