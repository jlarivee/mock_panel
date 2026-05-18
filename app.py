"""Drew's Mock Panel Interview — Streamlit app.

Run locally:
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=sk-ant-...
    streamlit run app.py

On Replit: set ANTHROPIC_API_KEY as a Secret, then press Run.
"""

from __future__ import annotations

import datetime as dt
import os

import anthropic
import streamlit as st
from dotenv import load_dotenv
from streamlit_mic_recorder import speech_to_text

from panelists import PANELISTS, find_panelist_by_message
from system_prompt import AGENCY_CONTEXT, build_system_prompt

load_dotenv()

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7")
MAX_TOKENS = 1024  # plenty for one panelist turn (~3-4 sentences + question)

# News briefing always uses Sonnet 4.6 regardless of main model — cheaper and
# well-supported for web_search. Briefing is a one-time call, not per-turn.
NEWS_BRIEFING_MODEL = "claude-sonnet-4-6"

NEWS_BRIEFING_SYSTEM = """\
You are briefing a job candidate (Drew Larivee) for a Data Analyst I interview
at the Rhode Island Department of Children, Youth, and Families (DCYF)
Residential Monitoring Unit. The interview is Thursday, May 21, 2026 at 12:00 PM
at 101 Friendship Street, Providence.

The panel:
- Jason Lyon, LICSW — Administrator, RI Executive Office of Health and Human Services / DCYF (likely the RMU Administrator / hiring manager)
- Kyeonghee Kim — Data Analyst, DCYF Office of Data Analytics, Evaluation, and CQI
- Heather Warner — Chief of Children's Mental Health, DCYF (Community Services & Behavioral Health)

Use the web_search tool to find news from the LAST 30 DAYS (and the past few
months if the last 30 days are thin) about:
- DCYF Rhode Island and the Residential Monitoring Unit
- The federal consent decree (United States v. Rhode Island, 1:24-cv-00531)
  and the federal court-appointed monitor's reports
- St. Mary's Home for Children investigation aftermath
- Bradley Hospital litigation aftermath and ADA compliance
- RMU staffing, policy changes, leadership changes
- Ashley Deckert (DCYF Director) — public statements, hearings, testimony
- Office of the Child Advocate (RI) reports
- RICHIST → CCWIS modernization progress
- Any recent public mentions of Jason Lyon, Kyeonghee Kim, or Heather Warner
  in their DCYF/EOHHS capacities (testimony, reports, press releases)

Return a tight briefing in markdown:

## Recent headlines (past ~30 days)
- 5-8 bullet points, each with a date and source domain in brackets like [providencejournal.com]

## Persistent context worth knowing
- 3-4 bullets on the bigger-picture story Drew should already understand
  (the consent decree, the two scandals, the current oversight structure)

## What this means for the interview
- 2-3 sentences on how Drew could subtly reference current events to demonstrate
  awareness without overplaying it. Be specific — name a panelist if a recent
  public statement of theirs would be useful to acknowledge.

If you find no relevant news in the past 30 days, say so explicitly at the top,
then expand the persistent-context section.
"""


def fetch_news_briefing() -> str:
    """Call Claude with the web_search tool and return the briefing text.

    Uses Sonnet 4.6 + web_search_20260209 (dynamic filtering on by default).
    Returns a markdown string ready to render.
    """
    client = get_client()
    try:
        response = client.messages.create(
            model=NEWS_BRIEFING_MODEL,
            max_tokens=2048,
            system=NEWS_BRIEFING_SYSTEM,
            messages=[
                {"role": "user", "content": "Brief me on the latest DCYF news."}
            ],
            tools=[{"type": "web_search_20260209", "name": "web_search"}],
        )
        text_parts = [b.text for b in response.content if b.type == "text"]
        return "\n\n".join(text_parts).strip() or "(No briefing returned)"
    except anthropic.APIError as e:
        return (
            "**Couldn't fetch briefing.** "
            f"`{type(e).__name__}: {getattr(e, 'message', str(e))}`\n\n"
            "Try again, or proceed with the interview without it."
        )

st.set_page_config(
    page_title="Drew's Mock Panel Interview",
    page_icon="🎙️",
    layout="centered",
)


# ---------- Session state initialization ----------

def init_state() -> None:
    st.session_state.setdefault("started", False)
    st.session_state.setdefault("messages", [])  # list of {role, content}
    st.session_state.setdefault("difficulty", "Medium")
    st.session_state.setdefault("transcript_started_at", None)
    st.session_state.setdefault("news_briefing", None)


def reset_interview() -> None:
    st.session_state.started = False
    st.session_state.messages = []
    st.session_state.transcript_started_at = None


# ---------- Anthropic client ----------

@st.cache_resource(show_spinner=False)
def get_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        st.error(
            "ANTHROPIC_API_KEY is not set. Add it to a `.env` file locally or "
            "to Replit Secrets, then restart the app."
        )
        st.stop()
    return anthropic.Anthropic(api_key=api_key)


def call_model(history: list[dict], difficulty: str) -> str:
    """Send the full history to Claude and return the assistant's reply.

    The system prompt is marked with cache_control so it can be served from
    cache on subsequent turns. Above the minimum cacheable prefix it pays
    for itself within two turns; below it (e.g. on Opus 4.7's 4096-token
    floor) it's a silent no-op — harmless.
    """
    client = get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": build_system_prompt(difficulty),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=history,
    )
    # response.content is a list of blocks; pick the first text block.
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


# ---------- Slash command handling ----------

SLASH_HELP = (
    "Commands: `/feedback` get scored feedback · `/coach` see a model answer "
    "for the current question · `/harder` raise difficulty · `/easier` lower "
    "difficulty · `/skip` skip current panelist · `/restart` reset."
)


def handle_slash_command(text: str) -> tuple[bool, str | None]:
    """Return (handled, injected_user_message).

    If the command is fully local (like /restart), handled=True and
    injected_user_message=None. If the command should be passed to the model
    as a user message (like /feedback or /skip), handled=True and the
    injected_user_message is the literal text to send.
    """
    cmd = text.strip().lower()
    if cmd == "/restart":
        reset_interview()
        st.rerun()
        return True, None
    if cmd == "/harder":
        order = ["Easy", "Medium", "Hard"]
        idx = order.index(st.session_state.difficulty)
        st.session_state.difficulty = order[min(idx + 1, 2)]
        st.toast(f"Difficulty: {st.session_state.difficulty}")
        return True, f"[system note: difficulty raised to {st.session_state.difficulty.upper()}. Continue the interview with the next panelist at the new difficulty.]"
    if cmd == "/easier":
        order = ["Easy", "Medium", "Hard"]
        idx = order.index(st.session_state.difficulty)
        st.session_state.difficulty = order[max(idx - 1, 0)]
        st.toast(f"Difficulty: {st.session_state.difficulty}")
        return True, f"[system note: difficulty lowered to {st.session_state.difficulty.upper()}. Continue the interview with the next panelist at the new difficulty.]"
    if cmd == "/skip":
        return True, "[system note: the candidate used /skip. The current panelist skips their turn and hands off to a different panelist with a fresh question.]"
    if cmd == "/feedback":
        return True, "[system note: the candidate typed /feedback. Drop the roleplay now and provide structured feedback using the feedback format from the system prompt. Then offer to resume the interview.]"
    if cmd == "/coach":
        return True, (
            "[system note: /coach. Pause the roleplay temporarily. Look at the most "
            "recent question asked by a panelist in this conversation, then output:\n\n"
            "**🎯 What [panelist name] is really testing:** 1-2 sentences on the underlying competency.\n\n"
            "**📝 Stronger answer (model framework):** A model answer in STAR format "
            "(Situation, Task, Action, Result) or another appropriate framework for "
            "the question type. Use Drew's actual background — URI criminology grad, "
            "AG Cold Case Unit intern, SQL/Python basics, Tableau/Power BI — make it "
            "realistic for him, not aspirational.\n\n"
            "**🔧 Two specific tactics:** Two concrete in-the-moment tweaks Drew could "
            "use (e.g., 'lead with the specific case file, not the methodology').\n\n"
            "End with: '**Ready to try again?** Type anything and we'll re-ask the "
            "same question so you can deliver the stronger answer.'\n\n"
            "On Drew's next message, return fully to the interview at the same point "
            "and re-ask the same question (or a close variant) so he can actually "
            "practice the better answer.]"
        )
    return False, None


# ---------- Rendering ----------

def render_welcome() -> None:
    st.title("🎙️ Drew's Mock Panel Interview")
    st.caption(
        "DCYF Residential Monitoring Unit · Data Analyst I · "
        "Thursday May 21, 2026 · 12:00 PM · 101 Friendship Street, Providence"
    )
    st.write("")
    st.subheader("Your panel")

    cols = st.columns(len(PANELISTS))
    for col, p in zip(cols, PANELISTS):
        with col:
            with st.container(border=True):
                st.markdown(f"### {p['avatar']} **{p['name']}**")
                st.markdown(f"*{p['role']}*")
                st.write(p["tagline"])

    st.caption(
        "⚠️ Roleplay only. Names and titles are from public DCYF / EOHHS "
        "records; voices are role-typical inferences for practice, not literal "
        "impersonations. Linda Lora (HR coordinator who sent the invite) is "
        "not on the panel."
    )

    st.write("")
    st.subheader("Get current on DCYF")
    st.caption(
        "Optional: pull the past ~30 days of DCYF / consent decree / monitor "
        "news before you start. Adds realism and gives you talking points. "
        "Costs about a nickel via Claude's web search."
    )
    if st.session_state.news_briefing is None:
        if st.button(
            "🗞️ Brief me on recent DCYF news",
            use_container_width=True,
        ):
            with st.spinner("Searching the web for recent DCYF news..."):
                st.session_state.news_briefing = fetch_news_briefing()
            st.rerun()
    else:
        with st.expander("🗞️ Recent DCYF news — read this first", expanded=True):
            st.markdown(st.session_state.news_briefing)
        if st.button("🔄 Refresh briefing", use_container_width=False):
            st.session_state.news_briefing = None
            st.rerun()

    st.write("")
    st.info(SLASH_HELP)
    st.write("")
    if st.button(
        "▶ Start Interview", type="primary", use_container_width=True
    ):
        st.session_state.started = True
        st.session_state.transcript_started_at = dt.datetime.now().isoformat(
            timespec="seconds"
        )
        # Seed with an empty user turn so the model produces the opening.
        with st.spinner("Jason is opening the panel..."):
            opening = call_model(
                [{"role": "user", "content": "Begin the interview."}],
                st.session_state.difficulty,
            )
        st.session_state.messages.append(
            {"role": "assistant", "content": opening}
        )
        st.rerun()


def render_message(msg: dict) -> None:
    role = msg["role"]
    content = msg["content"]
    if role == "user":
        with st.chat_message("user"):
            st.markdown(content)
        return

    panelist = find_panelist_by_message(content)
    if panelist is not None:
        with st.chat_message("assistant", avatar=panelist["avatar"]):
            st.caption(f"{panelist['name']} — {panelist['role']}")
            st.markdown(content)
    else:
        # Fallback for feedback mode or unrecognized messages
        with st.chat_message("assistant", avatar="📋"):
            st.markdown(content)


def render_sidebar() -> None:
    with st.sidebar:
        st.title("Drew's Panel Interview")
        st.caption("Mock interview for DCYF RMU Data Analyst I")

        st.session_state.difficulty = st.select_slider(
            "Difficulty",
            options=["Easy", "Medium", "Hard"],
            value=st.session_state.difficulty,
            help=(
                "Easy = no follow-up probing. Medium = one probe per weak "
                "answer. Hard = panelists press and call out bluffs."
            ),
        )

        st.write("")
        if st.button("🔄 Restart Interview", use_container_width=True):
            reset_interview()
            st.rerun()

        transcript_md = build_transcript_markdown()
        st.download_button(
            "💾 Save Transcript",
            data=transcript_md,
            file_name=transcript_filename(),
            mime="text/markdown",
            use_container_width=True,
            disabled=not st.session_state.messages,
        )

        st.write("")
        with st.expander("📚 Show Prep Notes (agency context)"):
            st.markdown("```\n" + AGENCY_CONTEXT + "\n```")

        if st.session_state.news_briefing:
            with st.expander("🗞️ Recent DCYF news"):
                st.markdown(st.session_state.news_briefing)

        st.write("")
        st.caption(SLASH_HELP)
        st.caption(f"Model: `{MODEL}`")


# ---------- Transcript export ----------

def transcript_filename() -> str:
    stamp = (
        st.session_state.transcript_started_at
        or dt.datetime.now().isoformat(timespec="seconds")
    )
    safe = stamp.replace(":", "-")
    return f"drew-mock-panel-{safe}.md"


def build_transcript_markdown() -> str:
    lines: list[str] = []
    started = (
        st.session_state.transcript_started_at
        or dt.datetime.now().isoformat(timespec="seconds")
    )
    lines.append("# Drew's Mock Panel Interview — Transcript")
    lines.append("")
    lines.append(f"- Started: {started}")
    lines.append(f"- Exported: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- Difficulty: {st.session_state.difficulty}")
    lines.append(f"- Model: {MODEL}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for msg in st.session_state.messages:
        if msg["role"] == "user":
            lines.append("**Drew:**")
            lines.append("")
            lines.append(msg["content"])
        else:
            lines.append(msg["content"])
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


# ---------- Main ----------

def main() -> None:
    init_state()
    render_sidebar()

    if not st.session_state.started:
        render_welcome()
        return

    st.title("🎙️ Drew's Mock Panel Interview")
    st.caption(
        f"Difficulty: **{st.session_state.difficulty}** · "
        "Type `/feedback` anytime for interim feedback."
    )

    for msg in st.session_state.messages:
        render_message(msg)

    # Voice input: browser-native Web Speech API via streamlit-mic-recorder.
    # Returns the transcript once per click (just_once=True), then None on
    # subsequent reruns until the mic is clicked again.
    voice_text = speech_to_text(
        language="en",
        start_prompt="🎤 Speak your answer",
        stop_prompt="⏹️ Stop recording",
        just_once=True,
        use_container_width=True,
        key="mic_input",
    )

    typed_text = st.chat_input("Your answer (or hit the mic above)...")
    user_text = voice_text or typed_text
    if not user_text:
        return

    # Slash command? Decide whether it is purely local or should be injected
    # into the conversation as a hidden system note.
    injected: str | None = None
    if user_text.strip().startswith("/"):
        handled, injected = handle_slash_command(user_text)
        if handled and injected is None:
            # Local command already handled (e.g., /restart triggered a rerun)
            return
        if handled and injected is not None:
            # Show the slash command in the transcript as Drew's message,
            # but send the injected note to the model.
            st.session_state.messages.append(
                {"role": "user", "content": user_text}
            )
            with st.chat_message("user"):
                st.markdown(user_text)
            with st.spinner("Panel is responding..."):
                reply = call_model(
                    st.session_state.messages[:-1]
                    + [{"role": "user", "content": injected}],
                    st.session_state.difficulty,
                )
            st.session_state.messages.append(
                {"role": "assistant", "content": reply}
            )
            st.rerun()
            return

    # Normal candidate answer
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)
    with st.spinner("Panel is responding..."):
        reply = call_model(st.session_state.messages, st.session_state.difficulty)
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()


if __name__ == "__main__":
    main()
