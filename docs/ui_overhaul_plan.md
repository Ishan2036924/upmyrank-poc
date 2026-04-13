# UI Overhaul Plan — Topic Tree + Quick Doubt + Mobile Responsive

> **Status:** ✅ COMPLETE — all 9 implementation steps done  
> **Last updated:** 2026-04-13  
> **When starting:** Read `UI_PRO_MAX.md` fully before touching any frontend file.

---

## Overview

Replacing the current global sidebar + chat UI with a topic-tree navigation model.
Everything is organized by Subject → Chapter → Topic with per-topic actions.
A floating Quick Doubt FAB acts as a shortcut for unscoped questions.

**Primary device:** Mobile (Android, 360–390px). Design mobile-first.

---

## Execution Order (confirm after each step before proceeding)

| Step | Task | Status |
|------|------|--------|
| 1 | Read all frontend files + UI_PRO_MAX.md → write full change plan | ✅ |
| 2 | Build static syllabus constant (Subject → Chapter → Topic, full JEE) | ✅ `lib/syllabus.ts` |
| 3 | Build sidebar topic tree component (desktop + mobile drawer) | ✅ `components/TopicTree.tsx`, `components/Sidebar.tsx` |
| 4 | Build floating Quick Doubt FAB + bottom sheet | ✅ `components/QuickDoubtFAB.tsx` |
| 5 | Update doubt chat to accept topic/chapter from navigation | ✅ `app/doubt/page.tsx` — subjectParam, chapterParam, topicLock, quickDoubtQ |
| 6 | Add subject short-circuit in engine.py (skip `_classify_subject` if subject provided) | ✅ `app/services/doubt/engine.py` — both `start_session` and `start_session_stream` |
| 7 | Restructure main layout (sidebar + content area + mobile header) | ✅ `layout.tsx` — QuickDoubtFAB global; `Sidebar.tsx` — mobile header + drawer |
| 8 | Apply mobile responsive fixes to all existing components | ✅ `globals.css` (dvh utils), `ChatInput.tsx` (fontSize 16), practice/mock/progress pages |
| 9 | Update dashboard screen | ✅ `app/page.tsx` — subject mastery cards, exam countdown, resume session button |
| 10 | Test at 360px, 390px, 768px, 1280px — fix overflow/layout issues | ⬜ Manual testing needed |

---

## Part 1: Topic Tree Sidebar

Replaces current sidebar. Fixed 220px on desktop. Full-height drawer on mobile.

### Tree structure
```
[Physics] [Chemistry] [Maths]   ← subject tabs, one active at a time

Chapter: Rotational Dynamics     ← expandable, shows mastery %
  mastery bar (color coded)
  Topic: Moment of Inertia       ← 3 icons: Doubt | Practice | Mock
  Topic: Torque & Angular Momentum
  Topic: Rolling Motion

Chapter: Electrostatics          ← collapsed by default
...
```

### Mastery color coding
- 0–50% → red
- 51–75% → amber
- 76–100% → green

### Data sources
- **Syllabus structure**: try `/api/taxonomy` or `/api/concepts` first. If neither returns full hierarchy, build a static `SYLLABUS` constant in frontend (Subject → Chapter → Topic). Acceptable for POC.
- **Mastery per topic**: from student genome API — check which endpoint returns `concept_mastery`. If none, render with 0% placeholder and add TODO comment.

### Interactions
- Click subject tab → filter tree to that subject
- Click chapter → expand/collapse topic list
- Click **Doubt** icon on topic → open topic-scoped doubt chat
- Click **Practice** icon → "Coming soon" placeholder
- Click **Mock** icon → "Coming soon" placeholder

### Mobile behavior
- Hidden by default on mobile
- Hamburger (top-left header) → opens as full-height left drawer
- Backdrop tap or swipe left → closes drawer
- Drawer overlays content (does NOT push it)

---

## Part 2: Topic-Scoped Doubt Chat

Opened when student taps Doubt icon on a topic.

### Header
- Back arrow → returns to topic tree
- Chapter + Topic name (e.g. "Rotational Dynamics · Moment of Inertia")
- Subject badge (Physics / Chemistry / Maths)

### Backend changes
1. `POST /api/doubt/session/start` — check if schema accepts `topic`, `chapter`, `subject` fields. If not, add as optional fields. Store on `doubt_session` record.
2. **Subject short-circuit in `engine.py`**: if `subject` is provided in request, skip `_classify_subject()` GPT-4o-mini call entirely. Use provided subject directly. Saves one API call per session start.

### Chat history per topic (STRETCH GOAL)
- Show small count of past doubts below topic in sidebar (e.g. "3 past doubts")
- Tap to see previous sessions for that topic
- Only implement if existing session history endpoint supports filtering by topic. Otherwise TODO.

---

## Part 3: Floating Quick Doubt FAB

Always visible except when doubt chat is open.

### Appearance
- Fixed position, bottom-right, 56px circle
- Dark background (`#1a1a2e` or brand color)
- Chat bubble icon in white
- "Quick Doubt" pill label to the left — visible on first load, fades after 3 seconds

### Behavior
- Tap → opens bottom sheet (not a new page) with large text input
- Student types doubt → Send
- System calls `_classify_subject()` to auto-detect subject + topic
- Opens doubt chat with detected subject/topic pre-filled in header
- If classification fails → default to Physics, show subject selector

### Mobile
- Thumb-reachable (bottom right)
- Bottom sheet rises above keyboard on input focus
- Input `font-size: 16px` (prevents iOS zoom)

---

## Part 4: Main Layout Restructure

### Desktop
```
[Sidebar 220px fixed] | [Main content — flex 1]
```

### Mobile
```
[Full-width main content]
[Drawer overlay when hamburger tapped]
[FAB bottom-right always]
```

### Header bar (mobile)
- Left: hamburger → opens drawer
- Center: UpMyRank logo or current page name
- Right: student avatar or initials

---

## Part 5: Mobile Responsive Fixes (apply to all existing components)

| Issue | Fix |
|-------|-----|
| LaTeX overflow | Wrap display math blocks in `overflow-x: auto` |
| Viewport height | Use `100dvh` instead of `100vh` for chat container |
| Input zoom on iOS | All inputs/textareas: `font-size: 16px` minimum |
| Touch targets | All buttons/chips/tabs/icons: minimum 44×44px tap area (padding, not font size) |
| Horizontal scroll | Page must never scroll horizontally at 360px. Math blocks may scroll inside their own container. |
| iOS smooth scroll | Add `-webkit-overflow-scrolling: touch` on scrollable containers |

---

## Part 6: Dashboard Updates

### Content
- Student name + JEE exam countdown (days remaining)
- Subject mastery: 3 cards (Physics / Chemistry / Maths), each with overall mastery % progress bar
- "Continue where you left off" — last topic studied + Resume button
- Quick action buttons: [Study Now] [Quick Doubt] [Mock Test]

### Mobile
- Everything stacks vertically
- Cards are full width
- Buttons are large (min 48px height)

---

## Rules (do not violate)

- Mobile-first: design at 360px, enhance upward with `sm:` `md:` `lg:` prefixes
- Do NOT create separate mobile components — use Tailwind responsive prefixes only
- Do NOT change backend RAG, genome, or session logic except the subject short-circuit in Step 6
- Do NOT change database schema
- Do NOT add new npm packages without checking if an existing one covers the need
- Do NOT git commit or push
- LaTeX rendering library stays the same — only wrap/style the output
- Final test: open sidebar → expand chapter → tap topic Doubt icon → send message → use FAB quick doubt → confirm all work end-to-end
