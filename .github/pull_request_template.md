<!--
  Title must be:  <type>(<scope>): <imperative summary>
  e.g.            feat(satellite): compute 3-year NDVI baseline per zone
  If an AGENT opened this PR, prefix the title with [agent].

  Fill in EVERY section. Do not delete sections.
  If one does not apply, write: N/A — <one line why>
  Rules: CONTRIBUTING.md
-->

## Lane
<!-- One of: R1 Satellite & Geo | R2 Data | R3 Backend & Fusion | R4 Frontend | R5 Automation | R6 AI Agent/DevOps | Pitch -->


## What this changes
<!-- 2–4 sentences, plain English. What you actually did. -->


## Why
<!-- Which MVP milestone (M1–M8) or Phase-2 item (P1–P5) from docs/SCOPE.md does this serve?
     Link the issue: Closes #___ -->


## How to verify
<!-- Exact commands or click-path the reviewer runs. Not "it works". -->

```bash

```

## Data contract impact
- [ ] No change to `docs/DATA-CONTRACT.md`
- [ ] Changes the contract — announced in the group first (CONTRIBUTING §8), and `DATA-CONTRACT.md`
      + `models.py` + `schemas.py` + `seed.py` are all updated in this PR

## Blast radius
<!-- Which other lanes could this break? Tag them: @handle. Write "none" only if you are sure. -->


## Evidence
<!-- Screenshot or GIF for anything visual. API response paste for anything backend.
     A frontend PR without a screenshot will be sent back. -->


## AI agent disclosure — REQUIRED (CONTRIBUTING §7)
<!-- Tick exactly ONE. Undeclared agent work gets the PR closed unmerged. -->
- [ ] Written entirely by hand, no AI assistance
- [ ] AI-assisted (autocomplete / suggestions I reviewed line by line)
- [ ] **Substantially agent-generated**
  - agent: <!-- e.g. Claude Code (Opus 5), Cursor (Sonnet 5), Copilot, Gemini, Lyzr -->
  - scope: <!-- what it produced, e.g. pipelines/satellite/ndvi.py end-to-end + its tests -->

**I confirm I have read and understood every line of this diff:** <!-- yes / no -->
<!-- If "no": close this PR, go read the diff, reopen. A judge will ask you how it works. -->

## Checklist
- [ ] Branched from fresh `main`; branch name follows CONTRIBUTING §3
- [ ] Commits follow the conventional format (§4) — signing is optional
- [ ] CI green — backend tests + frontend build
- [ ] No secrets, no `.env`, no keys, no tokens in the diff
- [ ] Stayed in my lane, or tagged the owner of every lane I touched
- [ ] Self-reviewed my own diff on the **Files changed** tab before requesting review
- [ ] `python backend/seed.py` still produces a working demo (offline fallback must never break)

---
**Reviewer:** @OfficialAbhinavSingh — only he merges. Do not self-merge. Do not merge someone else's PR.
