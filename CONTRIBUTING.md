# Contributing to NeerDrishti AI — Team Zeniths

**These rules are compulsory. Every contributor, on every change, without exception.**

We are 6 people shipping a finale build against a hard date (**5 Sep 2026**). The rules below
exist for exactly one reason: so that nobody's work silently breaks somebody else's the night
before the demo. They are short. Read them once, properly.

If a rule genuinely blocks you, say so in the group and get it changed. Do **not** quietly skip it.

---

## 0. The five non-negotiables

1. **No direct pushes to `main`.** Ever. `main` is protected. Everything lands through a Pull Request.
2. **Every PR is reviewed and merged by @OfficialAbhinavSingh.** Nobody self-merges. Nobody merges
   somebody else's PR.
3. **Stay in your lane.** You own a folder. Touching another lane's folder requires the owner's
   approval on the PR.
4. **If an AI agent wrote or helped write the change, you must declare it in the PR.** See §7.
   Undeclared agent work is grounds for closing the PR unmerged.
5. **Never commit a secret.** No `.env`, no tokens, no API keys, no service-account JSON. See §9.

---

## 1. Lane ownership

You have write access to the whole repo. That is trust, not permission. Ownership below decides
who must approve a change.

| Lane | Owner(s) | Owns (write freely) |
|---|---|---|
| **R1 · Satellite & Geo** | Abhinav — @OfficialAbhinavSingh | `backend/pipelines/satellite/`, `data/samples/zones*.geojson` |
| **R2 · Data (Billing / NRW)** | Sayali — @sayali-rathod-07 · Saksham — @Kr0issant | `backend/pipelines/billing/`, `data/samples/billing*.csv` |
| **R3 · Backend & Fusion** | Abhinav — @OfficialAbhinavSingh · Krishna — @krishnaasinghal | `backend/app/` |
| **R4 · Frontend & Dashboard** | Abhishek — @Abhi1818Singh | `frontend/` |
| **R5 · Automation (n8n)** | Pranjay — @PranjaySrivastava | `automation/n8n/`, `backend/app/routers/reports.py` |
| **R6 · AI Agent, DevOps & Deploy** | Krishna — @krishnaasinghal | `render.yaml`, `docker-compose.yml`, `.github/` |
| **Pitch & Deck** | Sayali — @sayali-rathod-07 · Pranjay — @PranjaySrivastava | `docs/DEMO.md`, deck assets |

Enforced automatically by [`.github/CODEOWNERS`](.github/CODEOWNERS) — GitHub will request the right
reviewer for you.

**`docs/DATA-CONTRACT.md` is special.** See §8.

---

## 2. Before you write any code

```bash
git checkout main
git pull origin main          # always branch from fresh main
```

Then follow [`docs/SETUP.md`](docs/SETUP.md). If your local env doesn't run, fix that before
opening a PR — "works on my machine" is not reviewable.

---

## 3. Branches

One branch per task. Branch off `main`, never off another feature branch.

```
<type>/<lane>-<short-description>
```

| Part | Allowed values |
|---|---|
| `type` | `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf` |
| `lane` | `r1`, `r2`, `r3`, `r4`, `r5`, `r6` |
| description | lowercase, hyphenated, ≤ 5 words |

Good:

```
feat/r1-ndvi-baseline-composite
fix/r3-fusion-missing-signal-renormalise
docs/r6-demo-script-v2
chore/r4-leaflet-upgrade
```

Bad: `abhinav-work`, `patch-1`, `new`, `test123`, `final-final-v2`.

Keep a branch alive for **at most 2 days**. Long branches are how you get a merge conflict at 2am
on 4 Sep. Split the work instead.

---

## 4. Commits

Format — [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <imperative summary, lowercase, no trailing period>
```

```bash
git commit -m "feat(satellite): compute 3-year NDVI baseline per zone"
git commit -m "fix(fusion): renormalise weights when a signal row is missing"
git commit -m "docs(contract): add cloud_pct QA field to satellite_signals"
```

Rules:
- `<type>` from the same list as branches. `<scope>` is the lane folder (`satellite`, `billing`,
  `fusion`, `api`, `frontend`, `n8n`, `deploy`, `docs`).
- Summary in the **imperative** — "add", not "added"/"adds".
- One logical change per commit. `wip`, `asdf`, `stuff`, `.` are not commit messages.

**Signing commits is recommended, not required.** If you already have SSH commit signing working,
keep using it. If you don't, do **not** spend finale week setting it up — an unsigned commit is
merged exactly like a signed one, and nothing in CI or branch protection checks for a signature.
Setup, if you want it, is in [`docs/SETUP.md`](docs/SETUP.md). One warning if you try: GitHub keeps
**authentication keys** and **signing keys** in two separate lists, and adding yours to the wrong
one fails silently — the badge just stays grey.

---

## 5. Opening the Pull Request

```bash
git push -u origin feat/r1-ndvi-baseline-composite
gh pr create --title "feat(satellite): compute 3-year NDVI baseline per zone" --body-file <your body>
```

Or use the GitHub UI — the PR template loads automatically. **Fill in every section.**

### 5.1 PR title — same format as a commit

```
<type>(<scope>): <imperative summary>
```

The title is checked by CI. A PR titled `updates` will fail before a human even looks at it.

### 5.2 PR body — the required format

The template in [`.github/pull_request_template.md`](.github/pull_request_template.md) is loaded
for you. Every section is mandatory. Delete nothing. If a section doesn't apply, write
`N/A — <one line why>`.

````markdown
## Lane
R1 · Satellite & Geo

## What this changes
<2–4 sentences, plain English. What did you actually do.>

## Why
<Which MVP milestone (M1–M8) or Phase-2 item (P1–P5) from docs/SCOPE.md does this serve?
 Link the issue: Closes #12>

## How to verify
<Exact commands or click-path a reviewer runs to see it work. Not "it works".>
```bash
python -m app.init_db && python seed.py
curl localhost:8000/api/scores | head
```

## Data contract impact
- [ ] No change to `docs/DATA-CONTRACT.md`
- [ ] Changes the contract — **announced in the group first** (§8), and DATA-CONTRACT.md updated in this PR

## Blast radius
<Which other lanes could this break? Tag them: @handle>

## Evidence
<Screenshot / GIF for anything visual. API response paste for anything backend.
 A frontend PR without a screenshot will be sent back.>

## AI agent disclosure  — REQUIRED, see CONTRIBUTING §7
- [ ] Written entirely by hand, no AI assistance
- [ ] AI-assisted (autocomplete / suggestions I reviewed line by line)
- [ ] **Substantially agent-generated** — agent: `<name+model>`, scope: `<what it wrote>`

I confirm I have read and understood every line of this diff: **yes / no**

## Checklist
- [ ] Branched from fresh `main`, follows the naming rules (§3)
- [ ] Commits follow the conventional format (§4)
- [ ] CI green (backend tests + frontend build)
- [ ] No secrets, no `.env`, no keys, no tokens in the diff
- [ ] Stayed in my lane, or tagged the owner of any lane I touched
- [ ] Self-reviewed my own diff on the "Files changed" tab before requesting review
````

### 5.3 Size

Aim for **under 400 changed lines**. A 2000-line PR the night before the freeze will not get a
real review, and that is when bugs ship. Split it.

Open it as a **Draft** the moment you start pushing — it lets everyone see what's in flight and
prevents two people building the same thing.

---

## 6. Review and merge

| Step | Who | Rule |
|---|---|---|
| 1 · Self-review | Author | Read your own diff on "Files changed" **before** requesting review |
| 2 · CI | Automated | Must be green. A red PR is not reviewed. |
| 3 · Lane review | CODEOWNER of any lane touched | Approve or request changes |
| 4 · Final review | @OfficialAbhinavSingh | Every PR, no exceptions |
| 5 · **Merge** | @OfficialAbhinavSingh **only** | **Nobody else clicks Merge. Nobody self-merges.** |

- Turnaround target: a review within **12 hours**. If it's blocking you, ping the group — don't wait silently.
- Reviewer leaves **specific** comments. "looks good" on a 300-line diff is not a review.
- Author **resolves every conversation** before merge. Unresolved threads block the merge.
- Merge strategy: **Squash and merge**. The squash commit message uses the PR title, so §5.1 matters.
- Delete your branch after merge.

### Emergency / hotfix (only 3–5 Sep, only if the demo is broken)

Same PR flow, but: branch `fix/hotfix-<thing>`, label `priority:demo-blocker`, ping the group
directly, review target 30 minutes. Still a PR. Still merged by @OfficialAbhinavSingh.
**Even a demo-blocker does not get pushed straight to `main`.**

---

## 7. AI agent disclosure — compulsory

We use AI agents (Claude Code, Cursor, Copilot, Gemini, Lyzr, and others) and that is completely
fine — it is how we ship this in two weeks. What is **not** fine is a reviewer not knowing which
parts of a diff a human actually understands.

**Rule: if an AI agent wrote or materially helped write the change, you declare it in the PR body.**

Pick exactly one box in the *AI agent disclosure* section:

| Box | Use when |
|---|---|
| **Written entirely by hand** | No AI touched this beyond ordinary editor autocomplete |
| **AI-assisted** | You drove; AI suggested lines/blocks that you read and edited |
| **Substantially agent-generated** | An agent produced whole files, functions, or the bulk of the diff |

If you pick *substantially agent-generated*, you must also fill in:

- **agent** — the tool and model, e.g. `Claude Code (Opus 5)`, `Cursor (Sonnet 5)`, `Copilot`
- **scope** — what it produced, e.g. `pipelines/satellite/ndvi.py end-to-end + its tests`

Additionally:

1. **If the PR itself was opened by an agent**, prefix the PR title with `[agent]` and say so in the
   first line of the body. Example: `[agent] feat(billing): generate synthetic NRW dataset`.
2. **Add the `ai-assisted` label** to the PR.
3. **You are still the author.** Answer this honestly: *"I confirm I have read and understood every
   line of this diff: yes / no"*. If the answer is **no**, do not open the PR — go read it first.
   A judge at the finale will ask you how your own code works.
4. Agent-generated **tests** get extra scrutiny. A test that asserts the bug is still a green test.

**Why we enforce this:** a reviewer reads an agent-generated diff differently from a hand-written
one — more slowly, and checking the things agents get wrong (invented APIs, silently dropped edge
cases, tests that assert nothing). Hiding it wastes their time and ours.

---

## 8. Changing the data contract

[`docs/DATA-CONTRACT.md`](docs/DATA-CONTRACT.md) is the one file all six lanes depend on. Every
other lane is written against it.

**Protocol — in this order:**

1. **Post in the team group first.** State the change and what breaks. Wait for R3 (@OfficialAbhinavSingh
   / @krishnaasinghal) to ack.
2. Open a PR that changes `docs/DATA-CONTRACT.md` **and** `backend/app/models.py` / `schemas.py`
   **and** `backend/seed.py` together. A contract change that leaves seed data stale breaks
   everyone the next morning.
3. Title it `docs(contract): ...` and tag **every** lane owner as reviewer.
4. Announce the merge in the group. Everyone rebases.

After **3 Sep (feature freeze)** the contract is closed. Bugfixes only.

---

## 9. Secrets — hard rule

Nothing secret goes in the repo. Not in code, not in a config file, not in a commit message, not
"temporarily", not in a comment.

- Local config lives in `backend/.env`, which is **gitignored**. `backend/.env.example` holds the
  *keys only*, with empty or dummy values.
- Deployed config lives in Render environment variables.
- GEE service-account JSON, WhatsApp/Meta tokens, `INGEST_TOKEN`, DB URLs — env vars, always.
- n8n workflow exports **must be scrubbed** before committing to `automation/n8n/`. n8n embeds
  credential references and sometimes webhook URLs. Open the JSON and check it by eye.

**If you commit a secret:** do not just delete it in a follow-up commit — it stays in the history.
Tell @OfficialAbhinavSingh immediately and **rotate the credential**. Rotating is the fix; deleting
is not.

See [`SECURITY.md`](SECURITY.md).

---

## 10. Definition of done

A change is done when **all** of these are true. Not when it runs on your laptop.

- [ ] Merged to `main` through a reviewed PR
- [ ] CI green on `main` after the merge
- [ ] Works against the deployed Render URL, not only locally
- [ ] The relevant doc is updated (contract, SETUP, ROLES, or your lane's README)
- [ ] `python backend/seed.py` still produces a working demo — **this is the offline fallback for
      the finale and it must never be broken**
- [ ] You can explain it out loud in 30 seconds to a judge

---

## 11. Daily rhythm

- **Async standup, 15 min, in the group:** finished / doing / blocked. Nothing else.
- **Blocked > 2 hours? Say it.** Two weeks is short. Silent blockers are the single most expensive
  thing that can happen to this project.
- Check open PRs once a day. A PR waiting on your review is a teammate who cannot start their next task.

---

## Quick reference

```bash
# start
git checkout main && git pull origin main
git checkout -b feat/r1-ndvi-baseline-composite

# work, then
git add -p
git commit -m "feat(satellite): compute 3-year NDVI baseline per zone"
git push -u origin feat/r1-ndvi-baseline-composite

# open PR — template loads automatically, fill EVERY section
gh pr create --web

# after Abhinav merges
git checkout main && git pull origin main
git branch -d feat/r1-ndvi-baseline-composite
```

Questions about these rules → ask in the group, or open a `docs:` PR proposing the change.
