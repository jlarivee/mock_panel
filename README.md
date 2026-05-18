# Drew's Mock Panel Interview

A Streamlit web app that runs a realistic 4-person mock panel interview for the **Data Analyst I** role with the Rhode Island DCYF **Residential Monitoring Unit (RMU)**. Built for Drew Larivee to rehearse before his Thursday interview. Four AI panelists each stay in character, rotate questions, probe weak answers, and produce structured feedback at the end. Powered by the **Anthropic Claude API**.

## The panel

- **Maya Reynolds** — RMU Administrator (Hiring Manager). Opens and closes. Warm but evaluating.
- **David Chen** — Senior Data Analyst, Office of Data Analytics. Technical. Short sharp questions.
- **Patricia Velazquez, LCSW** — Clinical Program Manager. Ethics and tone.
- **James Whitfield** — HR Business Partner. Conduct, conflict, public service values.

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

| Command     | What it does                                                   |
| ----------- | -------------------------------------------------------------- |
| `/feedback` | Drop the roleplay and get scores + things to fix right now     |
| `/harder`   | Bump the difficulty one notch (Easy → Medium → Hard)           |
| `/easier`   | Drop the difficulty one notch                                  |
| `/skip`     | Current panelist skips their turn and hands off                |
| `/restart`  | Wipe the conversation and start over                           |

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
