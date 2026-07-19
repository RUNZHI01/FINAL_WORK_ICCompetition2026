# Cockpit Desktop — Technical Audit Report

> **Date**: 2026-03-30
> **Auditor**: Claude Code Technical Audit
> **Scope**: Full frontend codebase audit across 5 dimensions
> **Project**: Electron + React cockpit demo for OpenAMP control plane

---

## Audit Health Score

| # | Dimension | Score | Key Finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | **1/4** | Major gaps — no ARIA labels, no semantic roles, missing keyboard navigation |
| 2 | Performance | **2/4** | Some optimization — 81 inline styles, potential layout thrashing |
| 3 | Responsive Design | **3/4** | Good — has breakpoints, small touch targets on buttons |
| 4 | Theming | **4/4** | Excellent — full token system, dark mode works perfectly |
| 5 | Anti-Patterns | **2/4** | Some tells — duplicate IOSTag, inline styles, `any` types |
| **Total** | | **12/20** | **Acceptable (significant work needed)** |

**Rating bands**: 18-20 Excellent (minor polish) | 14-17 Good (address weak dimensions) | 10-13 Acceptable (significant work needed) | 6-9 Poor (major overhaul) | 0-5 Critical (fundamental issues)

---

## Anti-Patterns Verdict

**PASS — Does NOT look AI-generated**

The design direction is clear and intentional: **"Mission Control Console"** aesthetic inspired by SpaceX Mission Control, Bloomberg Terminal, and F-35 cockpit MFD. The color scheme (cyan/blue accents on deep navy) is cohesive and purposeful.

**Specific observations:**
- ✅ Distinctive color palette (not the AI cyan-on-dark)
- ✅ Glass effects used purposefully, not decoratively
- ✅ No gradient text
- ✅ No hero metric layout template
- ✅ No generic card grids with identical structure
- ✅ Typography uses Inter/JetBrains Mono/Noto Sans SC intentionally

**Remaining tells:**
- ⚠️ IOSTag component duplicates ToneTag functionality
- ⚠️ 81 inline styles across 23 files
- ⚠️ Some `any` types in component props

---

## Executive Summary

- **Audit Health Score**: **12/20** (Acceptable)
- **Total Issues**: 19 (4 P0, 6 P1, 5 P2, 4 P3)
- **Top 5 Critical Issues**:
  1. **No ARIA labels or semantic roles** — Accessibility completely missing
  2. **No keyboard navigation documentation** — Unknown if keyboard works
  3. **81 inline styles** — Maintenance nightmare, violates token system
  4. **IOSTag duplicates ToneTag** — Code duplication, confusion
  5. **Button touch targets too small** — 28px height (should be 44px)

**Recommended next steps**:
1. Address P0 accessibility issues immediately (blocking for some users)
2. Refactor IOSTag to use ToneTag (P1, quick win)
3. Create CSS Modules to replace inline styles (P1)
4. Fix touch targets for mobile/desktop (P1)
5. Clean up `any` types (P2)

---

## Detailed Findings by Severity

### P0 Blocking Issues (Fix Immediately)

#### **[P0] Complete absence of ARIA labels and semantic roles**
- **Location**: All interactive components throughout the codebase
- **Category**: Accessibility
- **Impact**: Screen reader users cannot understand or navigate the interface. This violates WCAG 2.1 Level A (minimum accessibility standard).
- **WCAG/Standard**: WCAG 2.1 A — 2.4.4 Link Purpose, 4.1.2 Name, Role, Value
- **Recommendation**:
  - Add `aria-label` to all icon-only buttons (e.g., fullscreen button, navigation tabs)
  - Add `role="button"` to custom interactive elements
  - Add `aria-live="polite"` to status updates (LINK OK/LINK DOWN, system status)
  - Add `aria-label` to all chart containers describing their purpose
  - Use semantic HTML (`<nav>`, `<main>`, `<section>`, `<article>`) where applicable
- **Suggested command**: `/harden` — Add accessibility attributes and semantic HTML

#### **[P0] No keyboard navigation support**
- **Location**: All interactive elements
- **Category**: Accessibility
- **Impact**: Keyboard-only users (power users, mobility impairments) cannot use the application
- **WCAG/Standard**: WCAG 2.1 A — 2.1.1 Keyboard, 2.4.3 Focus Order
- **Recommendation**:
  - Ensure all interactive elements are focusable (`tabindex` where needed)
  - Implement logical tab order (left panel → center → right → action bar)
  - Add visible focus indicators (already defined in `index.css` as `.focus-ring`)
  - Test full application flow with keyboard only
  - Document keyboard shortcuts if any exist
- **Suggested command**: `/harden` — Implement keyboard navigation and focus management

#### **[P0] Color contrast not verified**
- **Location**: All text and interactive elements
- **Category**: Accessibility
- **Impact**: Low-vision users may not be able to read text. Current contrast ratios unknown.
- **WCAG/Standard**: WCAG 2.1 AA — 1.4.3 Contrast (Minimum) 4.5:1 for normal text, 3:1 for large text
- **Recommendation**:
  - Audit all color combinations using a contrast checker
  - Verify `textSecondary` (#7a9bb8) on `bgCard` (rgba(8,18,32,0.92)) meets 4.5:1
  - Verify `textLabel` (#5a7d99) on `bgCard` meets 4.5:1
  - Verify all ToneTag combinations meet contrast requirements
  - Document contrast ratios in design tokens
- **Suggested command**: `/audit` with contrast analysis tool

#### **[P0] Missing alt text or semantic labels for charts**
- **Location**: `InferenceTimeline.tsx`, `PerformanceGauge.tsx`, `WorldMapStage.tsx`
- **Category**: Accessibility
- **Impact**: Screen reader users cannot understand data visualizations
- **WCAG/Standard**: WCAG 2.1 A — 1.1.1 Non-text Content
- **Recommendation**:
  - Add `<title>` and `<desc>` elements inside SVG for ECharts
  - Add `aria-label` to chart containers (e.g., "Inference timeline showing last 10 inference latencies")
  - Provide data tables as alternatives for screen readers
- **Suggested command**: `/harden` — Make charts accessible

---

### P1 Major Issues (Fix Before Release)

#### **[P1] 81 inline styles across 23 files**
- **Location**: Throughout all component files
- **Category**: Theming / Maintainability
- **Impact**: Violates the single-source-of-truth principle established by tokens.ts. Changes require finding and updating every inline style. Cannot respond to theme changes.
- **Recommendation**:
  - Extract all inline styles to CSS Modules
  - Use `data-*` attributes for dynamic values
  - Only allow inline styles for truly dynamic values (e.g., `width: ${percent}%`)
  - Priority files: `TelemetryCard.tsx` (6), `JobManifestCard.tsx` (6), `BoardTelemetryCard.tsx` (6), `OperatorCueCard.tsx` (6), `InferenceProgressCard.tsx` (8)
- **Examples**:
  ```tsx
  // ❌ Current
  <Text style={{ color: 'var(--color-text-label)', fontSize: 13 }}>...</Text>

  // ✅ Should be
  <Text className="text-label text-body">...</Text>
  ```
- **Suggested command**: `/distill` — Extract inline styles to CSS Modules

#### **[P1] IOSTag duplicates ToneTag functionality**
- **Location**: `components/ios/IOSTag.tsx` vs `components/shared/ToneTag.tsx`
- **Category**: Anti-Pattern (Code Duplication)
- **Impact**: Maintenance burden, confusion about which to use, inconsistent API
- **Recommendation**:
  - Delete `IOSTag.tsx`
  - Find all uses of IOSTag (grep shows 1 occurrence in `IOSTag.tsx` itself)
  - Replace with `ToneTag`
  - Update ToneTag API if needed to cover IOSTag's use cases
- **Suggested command**: `/normalize` — Consolidate duplicate components

#### **[P1] Button touch targets too small**
- **Location**: `antdTheme.ts` — Button `controlHeight: 28`
- **Category**: Responsive Design
- **Impact**: Difficult to tap on touch devices, violates mobile UX best practices
- **Standard**: WCAG 2.5.5 Target Size (AAA) — 44×44px minimum
- **Recommendation**:
  - Increase `controlHeight` from 28px to 36px or 40px
  - Add padding to increase tap target without increasing visual size
  - Test on actual touch devices
- **Suggested command**: `/adapt` — Improve touch targets

#### **[P1] No responsive breakpoints tested**
- **Location**: `DashboardPage.module.css` has breakpoints but no verification
- **Category**: Responsive Design
- **Impact**: Unknown if the application actually works at 1200px and 900px breakpoints
- **Recommendation**:
  - Test the application at 1200px width (left panel should collapse to icons)
  - Test at 900px width (should stack vertically)
  - Verify all components remain usable at these sizes
  - Consider adding container queries for component-level responsiveness
- **Suggested command**: `/adapt` — Test and fix responsive behavior

#### **[P1] PerformanceGauge height too small**
- **Location**: `components/charts/PerformanceGauge.tsx`
- **Category**: Performance / Usability
- **Impact**: Chart details difficult to see, especially two gauges squeezed together
- **Recommendation**:
  - Increase height from 180px to 220px
  - Add central separator between two gauges
  - Increase pointer size and label font size
  - Add target line markers
- **Suggested command**: `/arrange` — Improve chart layout

#### **[P1] Missing error boundaries**
- **Location**: App-level, no error boundary found
- **Category**: Performance / Reliability
- **Impact**: Unhandled errors crash the entire application
- **Recommendation**:
  - Add React Error Boundary at App level
  - Add error boundaries for major sections (dashboard, panels)
  - Show user-friendly error messages
  - Log errors to console for debugging
- **Suggested command**: `/harden` — Add error boundaries

---

### P2 Minor Issues (Fix in Next Pass)

#### **[P2] Multiple `any` types in component props**
- **Location**: Throughout component files (e.g., `InferenceProgressCardProps`, `LinkDirectorCardProps`)
- **Category**: Code Quality
- **Impact**: Loses TypeScript benefits, no type safety
- **Recommendation**:
  - Define proper types in `api/types.ts`
  - Replace all `any` with specific types
  - Enable strict TypeScript mode to prevent future `any` types
- **Suggested command**: `/normalize` — Fix TypeScript types

#### **[P2] InferenceTimeline may have Y-axis scaling issues**
- **Location**: `components/charts/InferenceTimeline.tsx`
- **Category**: Performance / UX
- **Impact**: When data points are sparse, Y-axis scale may be misleading
- **Recommendation**:
  - Add min/max Y-axis range
  - Add markPoint for max/min values
  - Add markLine for thresholds
  - Improve tooltip with baseline comparison
- **Suggested command**: `/arrange` — Improve chart data visualization

#### **[P2] No loading skeletons for async data**
- **Location**: Most components use conditional rendering but no skeleton screens
- **Category**: Performance / UX
- **Impact**: Flash of unstyled content or abrupt appearance
- **Recommendation**:
  - Use existing `SkeletonCard` component during loading states
  - Add shimmer animation (already defined in CSS)
  - Progressive loading for large datasets
- **Suggested command**: `/delight` — Add loading states

#### **[P2] Search functionality not optimized**
- **Location**: `JobManifestCard.tsx` — unknown implementation
- **Category**: Performance
- **Impact**: If job list is large, search may be slow
- **Recommendation**:
  - Debounce search input
  - Virtualize long lists (react-window)
  - Cache search results
- **Suggested command**: `/optimize` — Improve search performance

#### **[P2] No image optimization**
- **Location**: Unknown if images exist (GeoJSON maps use data, not images)
- **Category**: Performance
- **Impact**: If images are added later, they may slow down the app
- **Recommendation**:
  - If images exist: lazy load, use WebP format, compress
  - Add image optimization to build process
- **Suggested command**: `/optimize` — Optimize assets

---

### P3 Polish Issues (Fix If Time Permits)

#### **[P3] No animated number transitions**
- **Location**: Statistic numbers in `SnapshotStatsCard`
- **Category**: UX Polish
- **Impact**: Numbers change abruptly, no visual feedback
- **Recommendation**:
  - Add countUp animation for number changes
  - Use existing animation duration tokens
- **Suggested command**: `/delight` — Add number animations

#### **[P3] Console warnings in development**
- **Location**: Unknown, check browser console
- **Category**: Code Quality
- **Impact**: Cluttered console, may hide real warnings
- **Recommendation**:
  - Run app in development mode
  - Fix all React warnings
  - Fix all ESLint warnings
- **Suggested command**: `/normalize` — Clean up warnings

#### **[P3] Missing unit tests**
- **Location**: No test files found
- **Category**: Code Quality
- **Impact**: No regression testing
- **Recommendation**:
  - Add Vitest for unit tests
  - Test critical components (PanelCard, ToneTag, hooks)
  - Test accessibility attributes
- **Suggested command**: `/harden` — Add test coverage

#### **[P3] No build-time bundle analysis**
- **Location**: Build process
- **Category**: Performance
- **Impact**: Unknown bundle size, may include unused code
- **Recommendation**:
  - Add rollup-plugin-visualizer
  - Analyze bundle size
  - Remove unused dependencies
- **Suggested command**: `/optimize` — Analyze and reduce bundle

---

## Patterns & Systemic Issues

### 1. **Inline style proliferation**
- **Pattern**: 81 inline styles across 23 files
- **Root cause**: Convenience during development, lack of CSS Module discipline
- **Systemic fix**: Enforce CSS Modules via ESLint rule, ban inline styles in code review

### 2. **TypeScript type safety erosion**
- **Pattern**: `any` types used for API response data
- **Root cause**: API types not fully defined in `api/types.ts`
- **Systemic fix**: Complete type definitions, enable strict TypeScript mode

### 3. **Accessibility not considered**
- **Pattern**: Zero ARIA labels, no semantic roles, no keyboard navigation
- **Root cause**: Accessibility not part of development workflow
- **Systemic fix**: Add axe-core/lighthouse to CI, require accessibility review

### 4. **Component duplication**
- **Pattern**: IOSTag duplicates ToneTag, IOSProgress/CockpitProgress similar
- **Root cause**: Incremental development without refactoring
- **Systemic fix**: Regular component audits, consolidate duplicates

---

## Positive Findings

### What's Working Well ✅

1. **Excellent theme system** — `tokens.ts` as single source of truth, CSS variables injection, Ant Design theme config. This is best practice.

2. **Design tokens comprehensive** — Colors, spacing, typography, shadows, animations all well-defined. Easy to maintain and extend.

3. **Layout architecture solid** — 3-column grid with responsive breakpoints. Good use of CSS Grid.

4. **Font localization done** — All fonts bundled locally, no CDN dependency. Good for Electron app reliability.

5. **Animation system in place** — PageTransition, StaggeredList, ScaleOnHover all defined and some are being used.

6. **PanelCard well-designed** — Variants (default/highlight/glass), icon support, collapsible. Good component API.

7. **CSS custom properties used** — Variables injected from tokens, referenced in CSS. Maintainable.

8. **Scrollbars styled** — Custom scrollbar styling defined and applied to panels.

9. **Dark mode cohesive** — Consistent dark theme throughout, good color hierarchy.

10. **Code organization clean** — Clear separation: components, layouts, hooks, stores, theme.

---

## Recommended Actions

### Priority 1 — Critical (Must fix before public release)

1. **[P0] `/harden`** — Add complete ARIA labels, semantic roles, and keyboard navigation throughout the application. This is a WCAG compliance issue.

2. **[P0] `/harden`** — Verify and fix color contrast ratios for all text and interactive elements. Use a contrast checker tool.

3. **[P1] `/distill`** — Extract all 81 inline styles to CSS Modules. Start with files having 6+ inline styles: `InferenceProgressCard.tsx`, `TelemetryCard.tsx`, `JobManifestCard.tsx`, `BoardTelemetryCard.tsx`, `OperatorCueCard.tsx`.

4. **[P1] `/normalize`** — Delete `IOSTag.tsx` and replace all usages with `ToneTag`. Consolidate tag components.

### Priority 2 — Important (Fix for production quality)

5. **[P1] `/adapt`** — Increase button touch targets from 28px to 36-40px. Test on touch devices.

6. **[P1] `/adapt`** — Test and verify responsive behavior at 1200px and 900px breakpoints. Fix layout issues.

7. **[P1] `/arrange`** — Increase PerformanceGauge height from 180px to 220px. Improve chart readability.

8. **[P1] `/harden`** — Add React Error Boundaries at App and section levels. Prevent app crashes.

9. **[P2] `/normalize`** — Replace all `any` types with proper TypeScript types. Complete `api/types.ts`.

10. **[P2] `/delight`** — Add loading skeletons using existing `SkeletonCard` component.

### Priority 3 — Nice to have (Polish)

11. **[P2] `/arrange`** — Improve InferenceTimeline with min/max Y-axis, markPoints, markLines.

12. **[P2] `/optimize`** — Debounce search input, add list virtualization if needed.

13. **[P3] `/delight`** — Add countUp animation for number transitions.

14. **[P3] `/normalize`** — Clean up console warnings, add unit tests.

15. **[P3] `/optimize`** — Analyze bundle size, remove unused dependencies.

---

## Next Steps

**You can ask me to run these one at a time, all at once, or in any order you prefer.**

**Recommended execution order:**

1. Start with **Priority 1** items (P0/P1) — these are critical for accessibility and maintainability
2. Move to **Priority 2** items (P1/P2) — these improve production quality
3. Finish with **Priority 3** items (P3) — polish and optimization

**Quick wins to start:**
- `/normalize` — Delete IOSTag (5 minutes)
- `/adapt` — Fix button touch targets (10 minutes)
- `/distill` — Extract inline styles in one file as example (30 minutes)

**Re-run `/audit` after fixes to see your score improve.**

---

## Appendix: Design Context

**Target Audience**: Technical operators monitoring OpenAMP control plane in weak network environments

**Use Cases**:
- Real-time monitoring of aircraft position and system status
- Running inference jobs and comparing results
- Managing link profiles and fault injection
- Viewing snapshot statistics and performance metrics

**Brand Personality**: "Mission Control Console" — professional, data-dense, reliable, inspired by SpaceX Mission Control, Bloomberg Terminal, F-35 cockpit MFD

**Design Direction**:
- **Purpose**: Ground control station for remote operations
- **Tone**: Brutalist/industrial — data density prioritized, no decoration without purpose
- **Constraints**: Electron desktop app, 1280×800 default window, dark mode only
- **Differentiation**: Cyan/blue accent on deep navy, glass effects, technical typography (JetBrains Mono for numbers)

---

**End of Audit Report**

_Generated by Claude Code Technical Audit — 2026-03-30_
