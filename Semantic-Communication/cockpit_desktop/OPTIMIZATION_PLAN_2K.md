# Cockpit Desktop - High-Resolution Optimization Plan

> **Date**: 2026-03-30
> **Resolution**: 2560×1440 (2K QHD)
> **Design Direction**: Mission Control Console

---

## Current State Analysis

### ✅ Strengths (Keep)
- **Layout**: Three-column grid (260px | 1fr | 300px) - excellent
- **Theme**: Dark navy (#050b14) with cyan/blue accents - distinctive
- **Typography**: Inter + JetBrains Mono - professional
- **Cards**: Gradient backgrounds, glass effects, highlight variants
- **Components**: Loading skeletons, error boundaries, proper types
- **Accessibility**: ARIA labels, semantic HTML, keyboard nav ready

### ⚠️ Optimization Opportunities for 2K Resolution

With 2560×1440, we have **2.7x more pixels** than 1280×800:
- Current spacing (12px gaps) may feel too sparse
- Content could use more breathing room
- Can add more visual hierarchy and detail
- Opportunity to enhance visual impact

---

## Optimization Plan

### 1. Increase Spacing for Large Screen

**Problem**: 12px gaps designed for 1280px feel too loose at 2560px

**Solution**: Scale up spacing proportionally
```css
/* DashboardPage.module.css */
.dashboard {
  gap: 16px;  /* from 12px */
  padding: 16px; /* from 12px */
}

.leftPanel, .rightPanel {
  padding-left: 4px;  /* from 2px */
  padding-right: 4px; /* from 2px */
}

.centerBottom {
  gap: 16px;  /* from 12px */
}
```

### 2. Enhance Card Visual Hierarchy

**Problem**: All cards have same visual weight

**Solution**: Add size variants to PanelCard
```typescript
// PanelCard already has variant, add size prop
size?: 'compact' | 'normal' | 'spacious'
```

### 3. Add Subtle Background Details

**Problem**: Deep navy background feels flat at large scale

**Solution**: Add technical grid pattern
```css
.animated-bg::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(56, 139, 200, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(56, 139, 200, 0.03) 1px, transparent 1px);
  background-size: 40px 40px;
  opacity: 0.5;
  pointer-events: none;
}
```

### 4. Improve Header Visual Impact

**Problem**: Header is simple at 2560px width

**Solution**: Add navigation tabs and logo (already in MissionShell.tsx)

### 5. Add Data Density Indicators

**Problem**: Large screen can show more information

**Solution**: Add subtle data density toggles or expandable sections

---

## Priority Fixes

### P1 - Scale spacing for 2K (Do Now)
- Increase gaps from 12px → 16px
- Increase padding from 12px → 16px
- Scale card font sizes slightly

### P2 - Visual Polish (Nice to Have)
- Add technical grid background
- Enhance card shadows
- Add subtle animations
- Improve chart visualizations

---

## Implementation

Let me implement the P1 spacing optimizations now.
