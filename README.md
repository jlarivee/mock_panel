# Drew's Mock Panel Interview

A Streamlit web app that runs a realistic 3-person mock panel interview for the **Data Analyst I** role with the Rhode Island DCYF **Residential Monitoring Unit (RMU)**. Built for Drew Larivee to rehearse before his **Thursday, May 21 2026, 12:00 PM** interview at 101 Friendship Street, Providence. Three AI panelists each stay in character, rotate questions, probe weak answers, and produce structured feedback at the end. Powered by the **Anthropic Claude API**.

## The panel

These are Drew's **real** panelists, pulled from the interview invitation and matched to public DCYF / EOHHS records:

- **Jason Lyon, LICSW** — Administrator, RI Executive Office of Health and Human Services / DCYF. Almost certainly the hiring manager for this role. Opens and closes; asks the broadest mix (mission, behavioral, conflict, public-service values).
- **Kyeonghee Kim** — Data Analyst, DCYF Office of Data Analytics, Evaluation, and CQI. The technical peer Drew would work alongside. SQL, statistics, data quality, methodology with messy administrative data.
- **Heather Warner** — Chief of Children's Mental Health, DCYF (Community Services & Behavioral Health). Ethics, confidentiality, trauma-informed framing, communicating technical work to clinical staff.

> **Roleplay only.** Names and titles come from public records (DCYF contact directory, the 2021 DCYF org chart, LinkedIn, the 2014 DCYF Adoption Surveillance Report). Voices are role-typical inferences for practice — not literal impersonations. The panel does not include Linda Lora, who is the State of RI HR Analyst II that scheduled the interview; HR-style behavioral questions are absorbed into Jason's mix.

## Run locally

```bash
cd mock-panel
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your Anthropic key (sk-ant-…)
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Deploy to Replit

1. Create a new Repl → **Import from upload** (or push this `mock-panel/` folder via GitHub).
2. In the Repl, open **Tools → Secrets** and add:
   - `ANTHROPIC_API_KEY` = your Claude API key (sk-ant-…)
   - *(optional)* `ANTHROPIC_MODEL` = `claude-sonnet-4-6` to save money during practice runs
3. Press **Run**. Replit will install the dependencies and start Streamlit on port 8080.
4. The first time Replit prompts about the webview, allow it. The chat UI loads in the right pane.

The included `.replit` file already wires up the run command and Cloud Run deployment target.

## How Drew uses it

1. Click **Start Interview**. Maya opens and asks the first question.
2. Answer by typing **or** by clicking the 🎤 **Speak your answer** button and talking — closer to a real Zoom/phone interview. Click again to stop, and the transcript is sent automatically.
3. Panelists rotate, each asks 3–4 questions over 12–15 total.
4. After James says "we have time for your questions for us," ask the panel anything you want them to answer in character.
5. Maya closes the interview. Type **/feedback** (or just keep typing) to get scored feedback.

### Voice input

Uses the browser's built-in **Web Speech API** — no extra API key, no audio uploaded anywhere. Browser support:

- ✅ Chrome, Edge, Safari (desktop and iOS), Brave, Arc
- ❌ Firefox (no Web Speech API) — falls back to typing

The first time you click the mic, the browser will ask for microphone permission. Allow it.

### Slash commands

| Command     | What it does                                                         |
| ----------- | -------------------------------------------------------------------- |
| `/feedback` | Drop the roleplay and get scores + things to fix + topics to study   |
| `/coach`    | Pause and see a model STAR-format answer for the question just asked, then re-ask it so Drew can deliver the stronger version |
| `/harder`   | Bump the difficulty one notch (Easy → Medium → Hard)                 |
| `/easier`   | Drop the difficulty one notch                                        |
| `/skip`     | Current panelist skips their turn and hands off                      |
| `/restart`  | Wipe the conversation and start over                                 |

### Pre-interview news briefing

On the welcome screen there's a **🗞️ Brief me on recent DCYF news** button. It uses Claude's built-in web search to pull the past ~30 days of headlines about DCYF, the consent decree, the federal monitor, St. Mary's, and Bradley Hospital. The briefing also includes "what this means for your interview" — how Drew could subtly reference current events without overplaying it.

Cost: roughly $0.05 per briefing (web search + Sonnet processing). Available again in the sidebar mid-interview if you want to re-read.

### Scored, actionable feedback

The end-of-interview feedback (or `/feedback` mid-run) is structured for action, not just description. Every section is mandatory:

- **Overall score** out of 5, plus per-panelist 1–5 scores with one-line reasons
- **Three things that worked** — each with *why it landed* (the specific move Drew made)
- **Three things to fix — with concrete swaps** — each one says *Instead of:* "[quote]" → *Try saying:* "[deliverable replacement]" using Drew's real background. Not "be more specific" but a sentence he could actually deliver in the room.
- **Turning-point questions** — the 3–5 questions that most moved the needle, each scored 1–5 with a sharper answer
- **Strongest and weakest answer** — quoted with reasoning
- **Topics to study before Thursday** — concrete topics tied to actual weak spots, e.g. *"review SQL window functions — Kyeonghee's running-median question caught you flat-footed"* not "study SQL"
- **Would they hire?** — yes / no / lean from each of the three panelists

### Sidebar

- **Difficulty slider** — Easy / Medium (default) / Hard. Hard makes panelists press, follow up, and call out bluffs.
- **Restart Interview** — same as `/restart`.
- **Save Transcript** — downloads the full session as a markdown file.
- **Show Prep Notes** — the agency context block, so Drew can re-read mid-interview.

## Model choice and cost per run

The app reads `ANTHROPIC_MODEL` from your env (defaults to `claude-opus-4-7`). Rough estimates for a full ~15-question interview:

| Model              | Cost per interview | Notes                                                   |
| ------------------ | ------------------ | ------------------------------------------------------- |
| `claude-opus-4-7`  | ~$0.50             | Most realistic panel feel — use for dress rehearsal.    |
| `claude-sonnet-4-6`| ~$0.05             | Prompt caching kicks in (cached prefix ~$0.30/M tokens). Great for early practice. |
| `claude-haiku-4-5` | ~$0.02             | Cheapest. Less nuanced but still usable.                |

Switch models by editing `ANTHROPIC_MODEL` in `.env` (or in Replit Secrets) and restarting. Note: prompt caching only activates above the model's minimum cacheable prefix (~2k tokens on Sonnet/Haiku, ~4k on Opus 4.7) — the system prompt is right at the boundary, so caching helps most on Sonnet.

## File map

```
mock-panel/
├── app.py              # Streamlit UI + Anthropic API calls + slash commands
├── panelists.py        # The four panelist personas + avatar mapping
├── system_prompt.py    # Master system prompt (agency context + rules)
├── requirements.txt    # streamlit, anthropic, python-dotenv, streamlit-mic-recorder
├── .env.example        # Template for local ANTHROPIC_API_KEY
├── .replit             # Replit run + deploy config
├── replit.nix          # Replit Python 3.11 environment
└── README.md           # This file
```
