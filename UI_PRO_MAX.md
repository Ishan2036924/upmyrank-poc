# UI/UX Pro Max Skill - (Light Glassmorphic Edition)
*This file contains advanced frontend execution rules. Apply these ONLY when building or refactoring UI components.*

## Core Aesthetics
- **Theme:** Strictly Light Glassmorphic. No dark mode.
- **Surfaces:** Use `bg-white/80` or `bg-white/90` with `backdrop-blur-md` for floating elements. Use `border-white/50` for subtle definition.
- **Shadows:** Avoid harsh black shadows. Use soft, colored shadows or large, diffused drop shadows (`shadow-[0_8px_30px_rgb(0,0,0,0.04)]`).

## Component Execution (Pro Max Rules)
- **Micro-interactions:** Every clickable element must have a satisfying, smooth transition (`transition-all duration-300 ease-out`). Include active states (`active:scale-95`).
- **Typography:** Create strict visual hierarchy. Muted labels (`text-slate-500 text-sm font-medium`) above high-contrast values (`text-slate-900 text-2xl font-bold`).
- **Empty States & Placeholders:** Never use default boring text. Make inputs and empty states conversational and beautifully padded.
- **Spacing:** Elements must breathe. Use ample padding (`p-6` or `p-8` for cards) and distinct gap spacing (`gap-4`) in flex/grid layouts.
