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
    "Commands: `/feedback` get interim feedback · `/harder` raise difficulty · "
    "`/easier` lower difficulty · `/skip` skip current panelist · `/restart` "
    "reset the interview."
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
    return False, None


# ---------- Rendering ----------

def render_welcome() -> None:
    st.title("🎙️ Drew's Mock Panel Interview")
    st.caption(
        "DCYF Residential Monitoring Unit · Data Analyst I · "
        "4-person panel simulation"
    )
    st.write("")
    st.subheader("Today's panel")

    cols = st.columns(2)
    for i, p in enumerate(PANELISTS):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"### {p['avatar']} **{p['name']}**")
                st.markdown(f"*{p['role']}*")
                st.write(p["tagline"])

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
        with st.spinner("Maya is opening the panel..."):
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
