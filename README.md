# GitHub Streak Backup Agent

Ever forgot to push code one day and lost your GitHub streak? This project fixes that.

It runs automatically every night at **11:30 PM Pakistan time**. If you already pushed something to this repo today, it does nothing. If you forgot, it writes one honest sentence about the project into this README and commits it — so your green square stays green.

> It only touches `README.md`. It never touches your actual code.

---

## What it does, step by step

```
Every night at 11:30 PM (Pakistan time)
        ↓
Did you push anything to this repo today?
        ↓ Yes → Stop. Nothing needed.
        ↓ No
Read the README + your recent commits
        ↓
Ask Groq AI to write one honest sentence about the project
        ↓
Add that sentence to the log section in README.md
        ↓
Commit and push README.md only
```

That's it. One sentence. One commit. No code touched.

---

## Before you start — what you need

- A GitHub account
- Python 3.11 or newer installed on your computer
- Git installed on your computer
- A **Groq API key** (free — takes 2 minutes to get)
- You need to own or have write access to the GitHub repo where you install this

---

## Step 1 — Get a free Groq API key

1. Go to [https://console.groq.com/keys](https://console.groq.com/keys)
2. Sign up for free (or log in)
3. Click **Create API key**
4. Copy the key — it starts with `gsk_...`
5. Save it somewhere safe (like Notepad) — you'll need it in the next steps

---

## Step 2 — Copy this project into your GitHub repo

Copy all the files from this project into the **root** of your GitHub repository.

The most important file that must be in the right place is:
```
.github/workflows/streak-backup.yml
```

If that file is in the wrong folder, the automation won't run.

---

## Step 3 — Set up on your computer (for local testing)

Open a terminal (Command Prompt, PowerShell, or bash) and run these commands one by one.

### Clone your repo and go into it
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
```

### Create a virtual environment (an isolated Python box)

**Windows CMD:**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Windows PowerShell:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You'll know it worked when you see `(venv)` at the start of your terminal line.

### Install the required packages
```bash
pip install -r requirements.txt
```

### Create your `.env` file

**Windows:**
```cmd
copy .env.example .env
```

**Linux / macOS:**
```bash
cp .env.example .env
```

Now open `.env` in any text editor (Notepad, VS Code, etc.) and fill in your real values:

```env
GROQ_API_KEY=gsk_your_actual_key_here
GIT_AUTHOR_NAME=Your Name
GIT_AUTHOR_EMAIL=your_github_email@example.com
DRY_RUN=true
```

> **What email to use?**
> Use the email address that's connected to your GitHub account.
> If you want GitHub to count the commit as yours, the email must match.
>
> Don't know which email GitHub uses for you?
> Go to **GitHub → Settings → Emails**.
> If you have "Keep my email address private" turned on, use the weird-looking
> no-reply email it shows you — something like `123456789+username@users.noreply.github.com`.

---

## Step 4 — Test it safely (dry run)

A "dry run" means: *pretend to run, but don't actually change anything*.

```bash
python run_agent.py --dry-run
```

You'll see something like:

```
✓  Dry-run complete. No files modified.
```

Or if you already committed today:

```
✓  Genuine commit already exists for 2026-07-15 — nothing to do.
```

Both are good. The script is working.

---

## Step 5 — Set up GitHub Actions (the automated part)

This is where the magic happens. GitHub will run the script for you every night automatically.

### 5a — Allow GitHub Actions to write to your repo

1. Open your repository on GitHub
2. Click **Settings** (top of the page)
3. Click **Actions** in the left sidebar
4. Click **General**
5. Scroll down to **Workflow permissions**
6. Select **Read and write permissions**
7. Click **Save**

### 5b — Add your Groq API key as a Secret

1. Go to **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Name: `GROQ_API_KEY`
4. Value: paste your Groq key (`gsk_...`)
5. Click **Add secret**

### 5c — Add your name and email as Variables (optional but recommended)

1. Go to **Settings → Secrets and variables → Actions → Variables**
2. Click **New repository variable**

Add these three (one at a time):

| Name | What to put |
|---|---|
| `GIT_AUTHOR_NAME` | Your name (e.g. `Mirza Haseeb`) |
| `GIT_AUTHOR_EMAIL` | Your GitHub email |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` |

---

## Step 6 — Push the project files to GitHub

```bash
git add .
git commit -m "feat: add streak backup agent"
git push
```

The workflow file must be on your **default branch** (usually `main`) for the scheduled run to work.

---

## Step 7 — Test the workflow manually (first run)

1. Open your repo on GitHub
2. Click **Actions** tab at the top
3. Click **GitHub Streak Backup Agent** in the left list
4. Click the **Run workflow** button (top right)
5. Click **Run workflow** in the popup

Wait 30–60 seconds. Click the running job to watch the logs.

If everything worked, you'll see green checkmarks. Check your repo — you should see a new commit with the message:
```
docs(streak-agent): update development log for YYYY-MM-DD
```

And `README.md` will have a new line in the log section at the bottom.

Run it a second time — it should say "No update needed" because a commit already exists for today. That proves it won't create duplicate entries.

---

## Running locally

```bash
# Preview what would happen (doesn't write anything)
python run_agent.py --dry-run

# Actually update README.md (then commit manually)
python run_agent.py

# Force it to run even if you already committed today (for testing)
python run_agent.py --force --dry-run

# See detailed logs
python run_agent.py --verbose
```

After a normal run (no `--dry-run`), README.md is updated on your machine. Push it yourself:

```bash
git add README.md
git commit -m "docs: update development log"
git push
```

---

## Changing the schedule

The workflow runs at **11:30 PM Pakistan time** by default. To change it, edit `.github/workflows/streak-backup.yml`:

```yaml
- cron: "30 18 * * *"  # 23:30 Asia/Karachi (UTC+5)
```

The number `18` is the hour in UTC. Pakistan is UTC+5, so `18:30 UTC = 23:30 PKT`.

Use [crontab.guru](https://crontab.guru) to build a new schedule.

---

## Changing settings

| Setting | File | Default |
|---|---|---|
| Timezone | `.env` or GitHub Variable | `Asia/Karachi` |
| Max words per entry | `.env` or GitHub Variable | `18` |
| Groq model | `.env` or GitHub Variable | `llama-3.3-70b-versatile` |
| Max log entries kept | `src/streak_agent/readme_service.py` | `30` |

---

## Troubleshooting

### "GROQ_API_KEY is missing"
- Locally: make sure `.env` exists and has `GROQ_API_KEY=gsk_...`
- GitHub Actions: make sure you added it as a **Secret** (not a Variable)

### Workflow ran but nothing was committed
One of these is happening:
- You already committed today (good — that's correct behavior)
- An agent commit already exists today (also correct)
- The generated sentence failed validation
- `DRY_RUN` is still set to `true` somewhere

### Commits don't show on my contribution graph
The author email in `GIT_AUTHOR_EMAIL` must exactly match a verified email on your GitHub account. Double-check it in **Settings → Emails**.

### "Workflow runs but can't push"
Go to **Settings → Actions → General → Workflow permissions** and make sure **Read and write permissions** is selected.

### Workflow doesn't run at exactly 11:30 PM
GitHub shared runners are sometimes busy. The workflow may start a few minutes late. This is normal — that's why it runs at 11:30 instead of 11:59.

---

## What makes an entry honest

The AI is told to only write things it can see evidence for in your README and commit history. It's not allowed to say "fixed bugs", "deployed", "shipped features", or anything specific unless your commits prove it.

If the AI fails or gets too creative, the script falls back to a generic sentence like:

> *Reviewed repository documentation and organized the next development steps.*

It won't write anything that could embarrass you or make false claims.

---

## Files in this project

| File | What it does |
|---|---|
| `run_agent.py` | The command you run locally |
| `src/streak_agent/config.py` | Reads your settings from environment variables |
| `src/streak_agent/git_service.py` | Checks your Git history |
| `src/streak_agent/llm_service.py` | Talks to Groq, handles fallbacks |
| `src/streak_agent/readme_service.py` | Reads and updates README.md safely |
| `src/streak_agent/validator.py` | Makes sure the AI output isn't garbage |
| `src/streak_agent/main.py` | Ties everything together |
| `.github/workflows/streak-backup.yml` | The GitHub Actions schedule |
| `.env.example` | Template for your local `.env` file |

---

## Automated Development Log

<!-- STREAK_AGENT_LOG_START -->

_No automated development entries yet._

<!-- STREAK_AGENT_LOG_END -->
