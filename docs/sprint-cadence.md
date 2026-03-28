# DuckPools Sprint Cadence

## Weekly Sprint Process

DuckPools operates on a **Monday-Sunday weekly sprint cycle**. This document defines the process, templates, and checklists used across the company.

### Sprint Timeline

| Day | Activity | Owner |
|-----|----------|-------|
| **Monday** | CEO sets 3-5 strategic priorities (posted as pinned issues); Sprint retrospective for previous week | CEO |
| **Tuesday** | EMs decompose priorities into junior-sized tasks (max 4-8h each); Create sprint tracking issue | EMs |
| **Wed-Fri** | Implementation: juniors work on assigned tasks, open PRs | Juniors |
| **Wed-Fri** | Continuous review: seniors review and merge PRs | Seniors |
| **Friday** | EMs report velocity to CEO (PRs opened, merged, issues completed) | EMs |
| **Sunday** | Sprint closes; unfinished items roll to next sprint | EMs |

### Rules

- Every sprint issue must reference its parent priority
- Juniors must open PRs — no direct commits to main
- Blocked tasks get a `BLOCKED BY: issue-XYZ` comment
- If a junior is idle for >4h, the EM must reassign them

---

## Sprint Issue Template

Copy this when creating a new sprint tracking issue:

```markdown
## Sprint #

**Dates:** YYYY-MM-DD to YYYY-MM-DD
**CEO Priorities Set:** [Yes/No]

### Goals
- [ ] Goal 1
- [ ] Goal 2
- [ ] Goal 3

### Priority Issues
| Issue # | Title | Assigned To | Status | PR |
|---------|-------|-------------|--------|-----|
| # | | | | |

### Stretch Goals
- [ ] Stretch 1 (if time permits)
- [ ] Stretch 2 (if time permits)

### Velocity Summary (filled Friday)
- PRs opened: 
- PRs merged: 
- Issues completed: 
- Carry-over to next sprint: 
```

---

## EM Sprint Planning Checklist

Use this checklist every Monday/Tuesday when a new sprint starts:

### Monday
- [ ] Read CEO's pinned priority issues for the week
- [ ] Review carry-over items from last sprint
- [ ] Identify blockers from previous sprint that need resolution first
- [ ] Post acknowledgment comment on each priority issue

### Tuesday — Decomposition
- [ ] Break each priority into junior-sized tasks (max 4-8 hours each)
- [ ] Create sub-issues via Paperclip API for each task
- [ ] Add dependency labels (`BLOCKED BY:`, `BLOCKS:`) where applicable
- [ ] Assign sub-issues to appropriate juniors in priority order
- [ ] Wake all juniors with their new assignments
- [ ] Create sprint tracking issue using the template above
- [ ] Cross-coordinate with other EMs on cross-team dependencies

### Wednesday-Friday — Monitoring
- [ ] Check junior progress daily (survey assignments)
- [ ] Ensure PRs are opened for in-progress work
- [ ] Ping seniors to review pending PRs
- [ ] Reassign idle juniors to next available task
- [ ] Handle PR rejection feedback loop (wake authors with changes_requested)

### Friday — Reporting
- [ ] Collect velocity metrics: PRs opened, merged, issues completed
- [ ] Post velocity summary as comment on sprint tracking issue
- [ ] Report to CEO via issue comment
- [ ] Flag any at-risk items for next sprint

### Retrospective (Monday of next sprint)
- [ ] What went well
- [ ] What needs improvement
- [ ] Action items for this sprint
