---
name: cinematic-experience
description: Design and build cinematic, immersive web experiences that feel like interactive films — framework-agnostic, brand-agnostic. Triggers on cinematic, immersive, 3D, WebGL, Three.js, scroll animation, dark futuristic UI, AI interface, HUD, parallax, motion design.
icon: 🎬
---

# Cinematic Experience Engine — Universal Skill v2.0

---

## How to Read This Skill

```
This skill is not a toolbox.
It is a way of thinking.

A website shows information.
A cinematic experience tells a story through space, motion, and emotion.
Your goal is always the latter — regardless of the request, tools, or client.
```

---

## Operating System — Read First

### The Two Modes

Before anything else, determine the working mode:

```
QUICK MODE  → a single specific effect, under 30 minutes
              assume defaults, state them explicitly, build directly
              apply: §3 partially + §6 + §11 + §12 only

FULL MODE   → a complete experience, a real project
              run the full loop in order:
              DISCOVER → DERIVE → ARCHITECT → BUILD → GATE
```

### The FULL MODE Loop

```
1. DISCOVER    → intent, identity, platform, constraints
2. DERIVE      → visual and motion language derived from the client
3. ARCHITECT   → scene structure, canvas type, layer system
4. BUILD       → assemble layer by layer
5. GATE        → quality gates before delivery
```

> **The Golden Rule:** Never impose a style. Every recommendation is derived
> from the discovery answers, not copied from this document. The code patterns
> are conceptual references — adapt them to the project's stack; never paste blindly.

---

## §1 — Core Philosophy

```
Design scenes, not pages.
Design emotions, not UI.
Every scroll is a camera move.
Every section is a narrative beat with a distinct mood.
```

### The Cinematic Spectrum

Cinematic is not all-or-nothing:

| Level | Definition | When to Choose |
|---|---|---|
| **Full Immersion** | The entire site is a 3D world | Creative portfolios, dramatic showcases |
| **Cinematic Accent** | A functional site with one or two cinematic scenes | Most real products |
| **Cinematic Motion** | Standard content with weighted, intentional motion | Content sites, dashboards |

> **The decision comes from Discovery** — a banking dashboard with a particle
> universe behind every chart is the wrong call, not a cinematic one.

### The Universal Signals of Cinematic Feel

```
Depth     → multiple parallax layers, real or implied
Motion    → weighted and damped, never instant
Contrast  → clear focal hierarchy in every scene
Shifts    → mood changes between sections (light, color, energy)
Intent    → every movement means something; nothing moves without purpose
```

---

## §2 — DISCOVER: What You Must Know Before Building

### When Information Is Missing

```
If any question materially changes the build → ask before you build.
If the request is a quick prototype with no constraints → assume defaults and state them explicitly.
```

**Defaults when unspecified:**
```
Platform      : single HTML file, ES modules, Three.js via importmap
Performance   : 60fps target on mid-range devices
Responsiveness: mobile + desktop
Accessibility : full reduced-motion support
```

### Discovery Questions

| Question | Why It Matters |
|---|---|
| **Emotion** — what should the user feel in the first 3 seconds? | Drives the entire mood, palette, and motion |
| **Narrative** — what story does scrolling tell? | Determines scene count and order |
| **Brand Identity** — logo, colors, tone, values? | Source for the derived visual language |
| **Missing Identity** — three words describing the desired feeling? one example you admire? | Alternative starting point when identity is absent |
| **Stack & Build Tool** — framework, bundler, CMS? | Decides code patterns and dependency format |
| **Output Format** — single HTML, component, full production build? | Decides architecture |
| **Target Devices & Perf Budget** — mobile? low-end? target FPS? | Particle counts, DPR cap, technique choice |
| **Accessibility Context** — motion-sensitive audience? regulatory requirements? | Severity of reduced-motion fallback |
| **Interface Layer?** — HUD, terminal, AI-OS overlay? | Adds the interactive layer (§9.4) |

---

## §3 — DERIVE: From Emotion to Experience

### 3.1 Mood Anchor

Choose one primary mood word:
```
awe · power · intimacy · urgency · serenity · mystery · boldness · refinement
```

Everything — color, motion speed, type weight — is derived from this word.

### 3.2 Energy Curve

A film is never the same energy level throughout:

```
low ──► rise ──► peak (the CTA moment) ──► resolution
```

Use this curve to vary section energy deliberately, not randomly.

### 3.3 Scene Architecture

The canonical narrative structure — use the beats that serve the story, not all of them:

```
1. HOOK         → full-screen, dramatic, attention in < 3 seconds
2. WORLD REVEAL → introduce the universe/brand with motion
3. EXPLORATION  → user discovers depth (scroll-driven)
4. IMMERSION    → pull them inside (interactive)
5. TRUST LAYER  → credibility, kept subtle — not a generic logo wall
6. CTA FINALE   → one powerful call to action (theatrical)
```

**Compression guide:**
```
Full immersion      → all six scenes, each its own scroll act
Cinematic accent    → HOOK + CTA as cinematic scenes; middle content with cinematic motion
Minimal             → HOOK + one revealing scroll
```

> **Rule:** every scene must feel like a cut in a film — distinct mood, purpose, energy.
> Three strong scenes beat six weak ones every time.

---

## §4 — ARCHITECT: Structure and Layers

### 4.1 Choose the Canvas Type

| Need | Canvas |
|---|---|
| Full 3D world, particles, camera rigs | WebGL canvas, fixed, full viewport |
| Scroll narrative, no 3D | Stacked DOM sections + CSS/JS motion |
| Hybrid: 3D world + content overlay | Fixed WebGL canvas + DOM content layer + optional HUD |
| Lightweight, no WebGL | DOM + CSS transforms + IntersectionObserver |

### 4.2 The Layer System (Universal, Stack-Independent)

Build bottom-up so each layer can be swapped or degraded independently:

```
Layer 4 (top)    HUD / terminal / AI-OS interface    (optional, interactive)
Layer 3          Scene content sections              (HTML, the story)
Layer 2          Visual overlays                    (vignette, grain, grid)
Layer 1 (base)   The world                          (WebGL canvas or CSS scene)
```

### 4.3 Output Format Decision

```
Single HTML file        → ES modules + importmap + inline CSS/JS
Component in an app     → framework-specific renderer + framework motion library
Full production build   → code-splitting + lazy-loading + SSR-safe mount
```

---

## §5 — The Derived Visual Language

> This section replaces any hard-coded palette. You derive a system — you do not impose one.

### 5.1 Palette Derivation

**If brand identity exists:**
```
1. Start from the real colors (logo, brand guidelines)
2. Identify the base color (primary surface — usually very dark or very light)
3. Identify the accent color (the color that lights up key moments)
4. Build a three-tier text scale (primary / dim / ghost)
5. Validate contrast: body text ≥ 4.5:1, large text ≥ 3:1 (WCAG AA)
```

**If brand identity is absent:**
```
1. Ask for three words describing the desired feeling
2. Ask for one example the client admires (does not need to be a competitor)
3. Build a textual mood board before writing any code
4. Use the mood → color table as a starting point
```

**Mood → Color Table (a guide, not a rule):**

| Mood | Base | Accent |
|---|---|---|
| Wonder / discovery | deep indigo | cyan / teal |
| Future-tech / power | near-black | electric blue or violet |
| Warmth / human | charcoal | amber / coral |
| Premium / luxury | black | gold / champagne |
| Mystery / noir | black | one restrained accent |
| Bold / energetic | dark base | saturated magenta or orange |
| Calm / ethereal | soft deep blue-grey | pale glow |

> **Note:** cinematic depth comes from high contrast, not only from darkness.
> A bright, high-key scene with strong contrast is equally cinematic.

### 5.2 Typography

```
Display  → headline face, must have visible character — never the OS default
Body     → optimized for readability
Mono     → only when a HUD, terminal, or data layer exists; skip otherwise

Always: full fallback stack ('DisplayFont', system-ui, sans-serif)
```

**Fluid scale:**
```css
:root {
  --step-1: clamp(0.9rem,  0.85rem + 0.2vw, 1rem);
  --step-2: clamp(1.1rem,  1rem + 0.5vw, 1.25rem);
  --step-3: clamp(1.6rem,  1.2rem + 1.8vw, 2.25rem);
  --display: clamp(2.5rem, 1rem + 7vw, 7rem);
}
```

### 5.3 Texture and Material Language

Choose 1–3 only, based on mood. Stacking all of them means none of them:

| Texture | Effect | Rule |
|---|---|---|
| **Glow** | neon accent on specific elements | use sparingly — glow everywhere = glow nowhere |
| **Grain** | subtle film grain overlay | adds organic, non-digital quality |
| **Glass** | frosted/blurred panels | for content over busy backgrounds |
| **Grid / Scanlines** | faint structural lines | for depth or a system-interface feel |
| **Vignette** | darkened edges | focuses attention on center |

---

## §6 — Motion Language (The Heart of Cinematic Feel)

Cinematic feel lives in **how** things move, not in **what** moves.
These rules are fully stack-independent.

### 6.1 Easing Curves

Never use linear. Choose by intent:

```css
:root {
  --ease-cinematic: cubic-bezier(0.16, 1, 0.3, 1);     /* weighted enter, slow out  */
  --ease-dramatic:  cubic-bezier(0.7, 0, 0.84, 0);     /* dramatic exit, fast out   */
  --ease-natural:   cubic-bezier(0.22, 1, 0.36, 1);    /* general purpose           */
  --ease-impact:    cubic-bezier(0.34, 1.56, 0.64, 1); /* overshoot / snap          */
}
```

### 6.2 Timing Scale

```
instant ~100ms · quick ~200ms · standard ~400ms · theatrical ~700ms · reveal 1000ms+
```

Be explicit about what moves — **never** use `transition: all`.

### 6.3 Weighted, Damped Motion — The Most Important Rule

Cameras and parallax layers must **lag and settle**, never snap.
Damp the scroll/cursor value toward its target each frame:

```js
// current eases toward target — lower factor = heavier = more cinematic
current += (target - current) * 0.06;  // cinematic sweet spot: 0.05–0.1
```

Apply to: camera position, look-at target, parallax layers, cursor-driven elements.

### 6.4 Choreography

```
Stagger        → delay sequential elements 60–120ms rather than firing all at once
Follow-through → let secondary elements drift after the primary lands
Rule           → one focal motion per scene — competing motion reads as chaos
```

### 6.5 Scroll = Camera

Treat scroll progress (0→1) as a camera timeline value, then **damp it** (§6.3)
before applying it. This is what makes scrolling feel like flying, not browsing.

---

## §7 — Spatial and Composition Principles

```
Three depth planes:
  Background  (the world)     → slowest movement
  Midground   (the content)   → medium
  Foreground  (HUD/overlays)  → fastest or fixed

Focal hierarchy: one hero element per scene; everything else supports it.
Negative space: composition, not emptiness — give the focal room to breathe.
Camera framing: lead the eye; use motion to reveal, not to decorate.
```

---

## §8 — Technology Decision Matrix (Framework-Agnostic)

| Goal | Technique | Stack Notes |
|---|---|---|
| Particle fields, 3D geometry, camera rigs | **Three.js** (ES modules) | R3F / TresJS / Threlte |
| Scroll-driven timelines, cinematic cuts | **GSAP + ScrollTrigger** | or lightweight IO + rAF |
| Declarative 3D scene graphs | framework 3D renderer | R3F / TresJS / Threlte |
| Component motion / page transitions | framework motion library | Framer Motion / Motion One / Svelte |
| Custom visual effects, post-processing | **WebGL/GLSL shaders** | drei `<EffectComposer>` |
| Pure CSS immersive effects | CSS transforms + variables | works everywhere, lowest cost |

**Dependency hygiene:**
```
✓ Use modern Three.js via ES modules + importmap
✓ Pin versions in production
✓ No unversioned CDN URLs
✓ Lazy-load the 3D layer so it never blocks first paint
```

---

## §9 — Universal Code Patterns

> ⚠️ **REFERENCE PATTERNS — NOT FOR DIRECT COPY-PASTE**
> Run Discovery first, derive your tokens, then adapt these patterns to your project's stack.
> For framework stacks, see §9.6 for how each concept translates.

### 9.0 Base Shell — Modern Single HTML File

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EXPERIENCE_NAME</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <!-- Fonts: derived from §5.2 — always include a fallback stack -->

  <script type="importmap">
  {
    "imports": {
      "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
      "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
    }
  }
  </script>

  <style>
    /* ⚠️ Derive these values from §5.1 — do not use these placeholders as-is */
    :root {
      --bg: #050508;
      --surface: #0a0a12;
      --border: #1a1a2e;
      --accent: #00d4ff;
      --accent-2: #7c3aed;
      --text: #e8e8f0;
      --text-dim: #4a4a6a;
      --text-ghost: #2a2a3a;
      --ease-cinematic: cubic-bezier(0.16, 1, 0.3, 1);
      --ease-dramatic:  cubic-bezier(0.7, 0, 0.84, 0);
      --ease-natural:   cubic-bezier(0.22, 1, 0.36, 1);
      --ease-impact:    cubic-bezier(0.34, 1.56, 0.64, 1);
      --step-1: clamp(0.9rem,  0.85rem + 0.2vw, 1rem);
      --step-2: clamp(1.1rem,  1rem + 0.5vw, 1.25rem);
      --step-3: clamp(1.6rem,  1.2rem + 1.8vw, 2.25rem);
      --display: clamp(2.5rem, 1rem + 7vw, 7rem);
    }

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    /* Reduced-motion: motion stops, content always remains visible */
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: 0.001ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.001ms !important;
        scroll-behavior: auto !important;
      }
    }

    html, body {
      background: var(--bg);
      color: var(--text);
      overflow-x: hidden;
      font-family: 'BodyFont', system-ui, sans-serif; /* derived from §5.2 */
    }

    /* Layer system — §4.2 */
    #universe {
      position: fixed;
      inset: 0;
      z-index: 0;
    }

    .content {
      position: relative;
      z-index: 1;
    }

    .overlay {
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 2;
    }

    .hud {
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 3;
    }

    /* Static poster fallback when WebGL is unavailable */
    #fallback {
      display: none;
      position: fixed;
      inset: 0;
      z-index: 0;
      /* CSS background matching the project's mood */
    }
  </style>
</head>
<body>

  <!-- Layer 1: The World -->
  <canvas id="universe" aria-hidden="true"></canvas>
  <div id="fallback" aria-hidden="true"></div>

  <!-- Layer 2: Visual Overlays -->
  <div class="overlay" aria-hidden="true"></div>

  <!-- Layer 3: Content — the real story -->
  <main class="content">
    <!-- scenes derived from §3.3 -->
  </main>

  <!-- Layer 4: HUD — optional only -->
  <div class="hud" role="presentation" aria-hidden="true"></div>

  <script type="module">
    import * as THREE from 'three';
    /* patterns below — §9.1 through §9.5 */
  </script>

</body>
</html>
```

### 9.1 Renderer Setup — Robust and Leak-Safe

```js
// ⚠️ Reference pattern — for frameworks see §9.6
import * as THREE from 'three';

/* --- Preference and Capability Detection --- */
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function webglAvailable() {
  try {
    const c = document.createElement('canvas');
    return !!(
      window.WebGLRenderingContext &&
      (c.getContext('webgl') || c.getContext('experimental-webgl'))
    );
  } catch (e) { return false; }
}

function getDeviceTier() {
  const cores = navigator.hardwareConcurrency ?? 2;
  const mem   = navigator.deviceMemory ?? 2;
  if (cores >= 8 && mem >= 8) return 'high';
  if (cores >= 4 && mem >= 4) return 'mid';
  return 'low';
}

/* --- Fallback when WebGL is unavailable --- */
function showFallback() {
  document.getElementById('universe').style.display = 'none';
  document.getElementById('fallback').style.display = 'block';
  // fallback carries a static poster or CSS scene — content remains readable
}

/* --- Entry Point --- */
if (!webglAvailable() || reduceMotion) {
  showFallback();
  if (!reduceMotion) console.info('WebGL unavailable — static experience active');
} else {
  initExperience();
}

function initExperience() {
  const canvas = document.getElementById('universe');
  const tier   = getDeviceTier();

  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: tier !== 'low',
    alpha: true,
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); // always cap DPR
  renderer.setSize(innerWidth, innerHeight);

  const scene  = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.1, 200);
  camera.position.set(0, 0, 30);

  /* --- Context Loss Handling --- */
  canvas.addEventListener('webglcontextlost', (e) => {
    e.preventDefault();
    showFallback();
  }, false);

  canvas.addEventListener('webglcontextrestored', () => {
    document.getElementById('fallback').style.display = 'none';
    canvas.style.display = 'block';
    initExperience();
  }, false);

  /* --- Resize --- */
  window.addEventListener('resize', () => {
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
  }, { passive: true });

  /* --- Pause when offscreen to save power --- */
  let visible = true;
  new IntersectionObserver(([e]) => visible = e.isIntersecting).observe(canvas);
  document.addEventListener('visibilitychange', () => visible = !document.hidden);

  return { renderer, scene, camera, tier, isVisible: () => visible };
}
```

### 9.2 Particle Field — Performance-Aware

```js
// ⚠️ Reference pattern
// accents: array of [r, g, b] values 0..1 — derived from §5.1, never hardcoded here

function createParticleField(scene, { accents, tier, reduceMotion }) {
  // particle count scales with device capability
  const baseCount = { high: 3000, mid: 1800, low: 800 };
  let count = baseCount[tier];
  if (reduceMotion) count = Math.floor(count * 0.2); // minimal when motion is reduced

  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array(count * 3);
  const col = new Float32Array(count * 3);

  for (let i = 0; i < count; i++) {
    pos[i * 3]     = (Math.random() - 0.5) * 100;
    pos[i * 3 + 1] = (Math.random() - 0.5) * 100;
    pos[i * 3 + 2] = (Math.random() - 0.5) * 100;
    // distribute color between two accent tones (60/40)
    const c = accents[Math.random() < 0.6 ? 0 : 1];
    col[i * 3] = c[0]; col[i * 3 + 1] = c[1]; col[i * 3 + 2] = c[2];
  }

  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color',    new THREE.BufferAttribute(col, 3));

  const mat = new THREE.PointsMaterial({
    size: tier === 'low' ? 0.2 : 0.15,
    vertexColors: true,
    transparent: true,
    opacity: 0.85,
    sizeAttenuation: true,
    depthWrite: false,
  });

  const points = new THREE.Points(geo, mat);
  scene.add(points);

  // clean up on teardown
  function dispose() {
    geo.dispose();
    mat.dispose();
    scene.remove(points);
  }

  return { points, dispose };
}
```

### 9.3 Scroll-Driven Camera with Damping

```js
// ⚠️ Reference pattern — this is the core of the cinematic feel

function createScrollCamera({ camera, scene, renderer, reduceMotion, isVisible }) {
  let target  = 0;
  let current = 0;

  window.addEventListener('scroll', () => {
    const max = document.documentElement.scrollHeight - innerHeight;
    target = max > 0 ? scrollY / max : 0;
  }, { passive: true });

  // ⚠️ Design your own camera keyframes here based on §3.3 — this is an example only
  function applyCamera(progress) {
    camera.position.z = 30 - progress * 25;
    camera.position.x = Math.sin(progress * Math.PI) * 12;
    camera.position.y = progress * 4;
    camera.lookAt(0, 0, 0);
  }

  const { points, dispose: disposeParticles } = createParticleField(scene, {
    accents: ACCENTS, // ← derived from §5.1
    tier: getDeviceTier(),
    reduceMotion,
  });

  function tick() {
    requestAnimationFrame(tick);

    if (!isVisible()) return; // no rendering when offscreen

    // snap immediately when motion is reduced, damp otherwise
    const dampFactor = reduceMotion ? 1 : 0.06;
    current += (target - current) * dampFactor;

    if (!reduceMotion) {
      points.rotation.y += 0.0004;
      points.rotation.x += 0.0001;
    }

    applyCamera(current);
    renderer.render(scene, camera);
  }

  tick();

  // clean up memory on unmount or route change
  function dispose() {
    disposeParticles();
    renderer.dispose();
  }

  return { dispose };
}
```

### 9.4 HUD / Terminal / AI-OS Interface Layer (Optional Only)

> Use **only** when the experience is a genuine system/OS-style interface.
> Never ship a terminal input that does nothing — either wire it to real behavior
> or make it display-only. A non-functional input is broken UI.

```css
/* ⚠️ Reference pattern — only when a real HUD layer is needed */
.hud {
  position: fixed;
  inset: 0;
  pointer-events: none;
  font-family: var(--mono, 'JetBrains Mono', monospace);
  font-size: 10px;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  opacity: 0.7;
}

.hud__corner {
  position: absolute;
  width: 18px;
  height: 18px;
  border-color: var(--accent);
}

.hud__corner.tl { top: 18px;    left: 18px;  border-top: 1px solid; border-left: 1px solid; }
.hud__corner.tr { top: 18px;    right: 18px; border-top: 1px solid; border-right: 1px solid; }
.hud__corner.bl { bottom: 18px; left: 18px;  border-bottom: 1px solid; border-left: 1px solid; }
.hud__corner.br { bottom: 18px; right: 18px; border-bottom: 1px solid; border-right: 1px solid; }

.glow {
  color: var(--accent);
  text-shadow: 0 0 8px color-mix(in srgb, var(--accent) 60%, transparent);
}
```

```html
<!-- aria-hidden: HUD is decorative, real content lives in <main> -->
<div class="hud" aria-hidden="true">
  <span class="hud__corner tl"></span>
  <span class="hud__corner tr"></span>
  <span class="hud__corner bl"></span>
  <span class="hud__corner br"></span>
</div>
```

### 9.5 Scene Text Transitions (Theatrical and Accessible)

```js
// ⚠️ Reference pattern
// Use IntersectionObserver, not raw scroll, so it fires only on enter

function createSceneObserver(onEnter) {
  return new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) onEnter(entry.target);
    });
  }, { threshold: 0.3 });
}

function revealScene(el, reduceMotion) {
  if (reduceMotion) {
    // content immediately visible with no motion
    el.style.opacity = '1';
    el.style.transform = 'none';
    return;
  }

  // stagger inner elements
  const children = el.querySelectorAll('[data-reveal]');
  children.forEach((child, i) => {
    child.style.transitionDelay = `${i * 80}ms`;
    child.style.transition = `
      opacity 0.7s var(--ease-cinematic),
      transform 0.7s var(--ease-cinematic)
    `;
  });

  // one frame to ensure initial state is applied
  requestAnimationFrame(() => {
    el.style.opacity = '1';
    children.forEach((child) => {
      child.style.opacity = '1';
      child.style.transform = 'translateY(0)';
    });
  });
}

/*
Companion CSS:
[data-scene]  { opacity: 0; }
[data-reveal] { opacity: 0; transform: translateY(20px); }
*/
```

### 9.6 Stack Adapters

> **Principle:** keep state and intent in framework-agnostic values.
> Only the binding differs. This keeps cinematic logic portable across any stack.

| Concept | Vanilla | React | Vue 3 | Svelte |
|---|---|---|---|---|
| rAF render loop | `requestAnimationFrame` | R3F `useFrame` | TresJS `useRenderLoop` | Threlte `useTask` |
| Scroll progress + damping | scroll listener + lerp | `@react-three/drei useScroll` | composable | `svelte/action` |
| Component motion | CSS transitions / GSAP | Framer Motion / Motion One | `@vueuse/motion` | `transition:` / `animate:` |
| Scroll timelines | GSAP ScrollTrigger | GSAP in `useLayoutEffect` | GSAP in `onMounted` | GSAP in `onMount` |
| Reduced motion | `matchMedia` | `useReducedMotion()` | `usePreferredReducedMotion` | media query store |
| SSR Safety | N/A | `dynamic` with `ssr: false` | `client:only` or guard | `onMount` guard |

---

## §10 — Performance Engineering

> A slow cinematic experience is not an experience — it is a slideshow.

```
Particle counts   → scale by device tier (§9.1), never a fixed number
DPR               → always capped at 2
Geometry          → instance repeated shapes, merge static geometry,
                    no separate Mesh per particle
Loading           → lazy-load the 3D layer; never block first paint
Pausing           → pause when offscreen or tab is hidden (§9.1)
Measurement       → target ≥ 55fps on the reference device;
                    watch LCP/TBT, not only visual polish
Events            → read scroll/cursor in event listeners,
                    do heavy work in the rAF loop
```

```js
// pause rendering when offscreen — saves battery and frames
let visible = true;
new IntersectionObserver(([e]) => visible = e.isIntersecting).observe(canvas);
document.addEventListener('visibilitychange', () => visible = !document.hidden);

function tick() {
  requestAnimationFrame(tick);
  if (!visible) return; // no work when hidden
  // ... rest of render loop
}
```

---

## §11 — Accessibility and Reduced Motion (Non-Negotiable)

```css
/* CSS: motion stops, content always remains readable */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
    scroll-behavior: auto !important;
  }
}
```

```js
// JS: snap instead of damp, no drifting particles, no camera fly-throughs
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
```

**Complete accessibility checklist:**

```
✓ prefers-reduced-motion: detected and applied in both CSS and JS
✓ Essential content never hidden behind scroll or motion alone
✓ Contrast: body text ≥ 4.5:1, large text ≥ 3:1 (validated in §5.1)
✓ Keyboard: all interactive elements reachable, focus styles visible,
            logical focus order maintained
✓ Canvas is decorative: aria-hidden="true"; real content lives in the DOM
✓ Static poster provided when motion is reduced or WebGL is unavailable (§12)
✓ Auto-playing infinite motion can be paused by the user
✓ Overlays and traps manage focus correctly
```

---

## §12 — Robustness and Fallbacks (Progressive Enhancement)

> The experience must degrade gracefully — never show a black screen.

```js
// ⚠️ Reference pattern
function webglAvailable() {
  try {
    const c = document.createElement('canvas');
    return !!(
      window.WebGLRenderingContext &&
      (c.getContext('webgl') || c.getContext('experimental-webgl'))
    );
  } catch (e) { return false; }
}

// the fallback is real content — not a white or black screen
// it must tell the same story without motion
if (!webglAvailable() || reduceMotion) {
  showFallback();
} else {
  initExperience();
}
```

**Complete robustness checklist:**

```
✓ WebGL check before initialization
✓ webglcontextlost: preventDefault + immediate fallback
✓ webglcontextrestored: re-initialize
✓ Teardown: dispose() geometry/material/renderer on unmount
✓ SSR safety: 3D code guarded by client-only check
✓ Fallback carries real content — tells the story without motion
✓ Tier scaling: particle counts and effects scale with device capability
```

---

## §13 — Complete Example: Minimal Cinematic Landing Page

> This example assembles every section into one complete scenario.
> **Scenario:** tech company, mood = "future-power", stack = vanilla HTML, no existing brand.

### Discovery → Derived Tokens

```
Emotion      → power + awe in the first 3 seconds
Narrative    → we are building the future (hook → product reveal → credibility → CTA)
Identity     → none (three words: power, precision, future)
Stack        → single HTML file, vanilla JS
Devices      → desktop first, mobile second
```

```css
/* Derived tokens from §5.1 — mood: "future-power" */
:root {
  --bg: #04040a;
  --surface: #080814;
  --border: #151528;
  --accent: #3b82f6;   /* electric blue — derived from mood */
  --accent-2: #8b5cf6; /* secondary violet */
  --text: #e2e8f0;
  --text-dim: #475569;
  --text-ghost: #1e293b;
}
```

### Complete File

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NEXUS — Build The Future</title>

  <script type="importmap">
  {
    "imports": {
      "three": "https://unpkg.com/three@0.160.0/build/three.module.js"
    }
  }
  </script>

  <style>
    :root {
      --bg: #04040a; --surface: #080814; --border: #151528;
      --accent: #3b82f6; --accent-2: #8b5cf6;
      --text: #e2e8f0; --text-dim: #475569; --text-ghost: #1e293b;
      --ease-cinematic: cubic-bezier(0.16, 1, 0.3, 1);
      --display: clamp(2.5rem, 1rem + 7vw, 7rem);
      --step-3: clamp(1.6rem, 1.2rem + 1.8vw, 2.25rem);
      --step-2: clamp(1.1rem, 1rem + 0.5vw, 1.25rem);
    }

    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: 0.001ms !important;
        transition-duration: 0.001ms !important;
      }
    }

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    html { scroll-behavior: smooth; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', system-ui, sans-serif;
      overflow-x: hidden;
    }

    /* Layers */
    #universe { position: fixed; inset: 0; z-index: 0; }

    #fallback {
      display: none;
      position: fixed;
      inset: 0;
      z-index: 0;
      background: radial-gradient(ellipse at 50% 50%, #0f1729 0%, #04040a 70%);
    }

    .content { position: relative; z-index: 1; }

    /* Scenes */
    .scene {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 4rem 2rem;
    }

    /* HOOK */
    .scene--hook {
      text-align: center;
      flex-direction: column;
      gap: 1.5rem;
    }

    .hook__eyebrow {
      font-size: var(--step-2);
      color: var(--accent);
      letter-spacing: 0.3em;
      text-transform: uppercase;
      opacity: 0;
      transform: translateY(20px);
      transition:
        opacity 1s var(--ease-cinematic),
        transform 1s var(--ease-cinematic);
    }

    .hook__title {
      font-size: var(--display);
      font-weight: 800;
      line-height: 0.95;
      letter-spacing: -0.02em;
      opacity: 0;
      transform: translateY(30px);
      transition:
        opacity 1s var(--ease-cinematic) 0.15s,
        transform 1s var(--ease-cinematic) 0.15s;
    }

    .hook__sub {
      font-size: var(--step-3);
      color: var(--text-dim);
      max-width: 40ch;
      line-height: 1.5;
      opacity: 0;
      transform: translateY(20px);
      transition:
        opacity 1s var(--ease-cinematic) 0.3s,
        transform 1s var(--ease-cinematic) 0.3s;
    }

    .hook__cta {
      display: inline-block;
      padding: 0.9em 2.5em;
      background: var(--accent);
      color: #fff;
      font-weight: 600;
      font-size: var(--step-2);
      border-radius: 4px;
      text-decoration: none;
      letter-spacing: 0.02em;
      opacity: 0;
      transform: translateY(20px);
      transition:
        opacity 1s var(--ease-cinematic) 0.45s,
        transform 1s var(--ease-cinematic) 0.45s,
        background 0.2s;
    }

    .hook__cta:hover { background: #2563eb; }
    .hook__cta:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 4px;
    }

    /* Visible state */
    .scene--hook.is-visible .hook__eyebrow,
    .scene--hook.is-visible .hook__title,
    .scene--hook.is-visible .hook__sub,
    .scene--hook.is-visible .hook__cta {
      opacity: 1;
      transform: translateY(0);
    }

    /* WORLD REVEAL */
    .scene--world {
      flex-direction: column;
      gap: 1rem;
      text-align: center;
      border-top: 1px solid var(--border);
    }

    /* HUD corners */
    .hud { position: fixed; inset: 0; pointer-events: none; z-index: 3; }
    .hud__corner {
      position: absolute;
      width: 20px;
      height: 20px;
      border-color: var(--accent);
      opacity: 0.4;
    }
    .hud__corner.tl { top: 20px;    left: 20px;  border-top: 1px solid; border-left: 1px solid; }
    .hud__corner.tr { top: 20px;    right: 20px; border-top: 1px solid; border-right: 1px solid; }
    .hud__corner.bl { bottom: 20px; left: 20px;  border-bottom: 1px solid; border-left: 1px solid; }
    .hud__corner.br { bottom: 20px; right: 20px; border-bottom: 1px solid; border-right: 1px solid; }
  </style>
</head>
<body>

  <canvas id="universe" aria-hidden="true"></canvas>
  <div id="fallback" aria-hidden="true"></div>

  <main class="content">

    <!-- HOOK -->
    <section class="scene scene--hook" data-scene="hook">
      <p class="hook__eyebrow">NEXUS PLATFORM</p>
      <h1 class="hook__title">Build<br>The Future.</h1>
      <p class="hook__sub">
        Infrastructure for teams who refuse to compromise
        on speed, scale, or precision.
      </p>
      <a href="#world" class="hook__cta">Start Building</a>
    </section>

    <!-- WORLD REVEAL -->
    <section class="scene scene--world" id="world" data-scene="world">
      <p style="color:var(--accent);letter-spacing:.3em;
                text-transform:uppercase;font-size:var(--step-2)">
        The Platform
      </p>
      <h2 style="font-size:var(--step-3);font-weight:700;
                 max-width:30ch;text-align:center">
        Every tool your team needs, in one unified environment.
      </h2>
    </section>

    <!-- CTA FINALE -->
    <section class="scene" style="flex-direction:column;gap:2rem;
                                  text-align:center;border-top:1px solid var(--border)">
      <h2 style="font-size:var(--display);font-weight:800;line-height:0.95">
        Ready?
      </h2>
      <a href="#" class="hook__cta" style="opacity:1;transform:none">
        Get Early Access
      </a>
    </section>

  </main>

  <!-- HUD — decorative only -->
  <div class="hud" aria-hidden="true">
    <span class="hud__corner tl"></span>
    <span class="hud__corner tr"></span>
    <span class="hud__corner bl"></span>
    <span class="hud__corner br"></span>
  </div>

  <script type="module">
    import * as THREE from 'three';

    const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

    /* --- WebGL Check --- */
    function webglAvailable() {
      try {
        const c = document.createElement('canvas');
        return !!(window.WebGLRenderingContext &&
          (c.getContext('webgl') || c.getContext('experimental-webgl')));
      } catch (e) { return false; }
    }

    function showFallback() {
      document.getElementById('universe').style.display = 'none';
      document.getElementById('fallback').style.display = 'block';
    }

    /* --- Palette: derived from §5.1 for mood "future-power" --- */
    const ACCENTS = [
      [0.23, 0.51, 0.96], // #3b82f6 — electric blue
      [0.55, 0.36, 0.96], // #8b5cf6 — violet
    ];

    /* --- Entry --- */
    if (!webglAvailable()) {
      showFallback();
    } else {
      initExperience();
    }

    function initExperience() {
      const canvas   = document.getElementById('universe');
      const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
      renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
      renderer.setSize(innerWidth, innerHeight);

      const scene  = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.1, 200);
      camera.position.set(0, 0, 30);

      /* Context loss */
      canvas.addEventListener('webglcontextlost', (e) => {
        e.preventDefault();
        showFallback();
      });

      /* Resize */
      window.addEventListener('resize', () => {
        camera.aspect = innerWidth / innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(innerWidth, innerHeight);
      }, { passive: true });

      /* Particles */
      const count = reduceMotion ? 300 : 2200;
      const geo   = new THREE.BufferGeometry();
      const pos   = new Float32Array(count * 3);
      const col   = new Float32Array(count * 3);

      for (let i = 0; i < count; i++) {
        pos[i * 3]     = (Math.random() - 0.5) * 100;
        pos[i * 3 + 1] = (Math.random() - 0.5) * 100;
        pos[i * 3 + 2] = (Math.random() - 0.5) * 100;
        const c = ACCENTS[Math.random() < 0.6 ? 0 : 1];
        col[i * 3] = c[0]; col[i * 3 + 1] = c[1]; col[i * 3 + 2] = c[2];
      }

      geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      geo.setAttribute('color',    new THREE.BufferAttribute(col, 3));

      const mat = new THREE.PointsMaterial({
        size: 0.15, vertexColors: true, transparent: true,
        opacity: 0.8, sizeAttenuation: true, depthWrite: false,
      });

      const points = new THREE.Points(geo, mat);
      scene.add(points);

      /* Scroll camera */
      let target = 0, current = 0;
      window.addEventListener('scroll', () => {
        const max = document.documentElement.scrollHeight - innerHeight;
        target = max > 0 ? scrollY / max : 0;
      }, { passive: true });

      /* Visibility */
      let visible = true;
      new IntersectionObserver(([e]) => visible = e.isIntersecting).observe(canvas);
      document.addEventListener('visibilitychange', () => visible = !document.hidden);

      /* Render loop */
      function tick() {
        requestAnimationFrame(tick);
        if (!visible) return;

        current += (target - current) * (reduceMotion ? 1 : 0.06);

        if (!reduceMotion) {
          points.rotation.y += 0.0004;
          points.rotation.x += 0.0001;
        }

        camera.position.z = 30 - current * 20;
        camera.position.x = Math.sin(current * Math.PI) * 8;
        camera.lookAt(0, 0, 0);
        renderer.render(scene, camera);
      }

      tick();
    }

    /* --- Scene Reveals --- */
    const hookScene = document.querySelector('[data-scene="hook"]');

    new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) entry.target.classList.add('is-visible');
      });
    }, { threshold: 0.2 }).observe(
      ...document.querySelectorAll('[data-scene]')
    );

    // HOOK reveals immediately on load
    requestAnimationFrame(() => hookScene.classList.add('is-visible'));
  </script>
</body>
</html>
```

---

## §14 — Anti-Patterns: What to Escape

### On Judging Tools

```
Tools are neutral.
Tailwind, white backgrounds, and stock UI components are not forbidden.
They are only wrong as the unconsidered default.
Judge the result and the intent — not the library.
```

### Defaults to Escape

```
❌ 16px system sans on a white page with a #007bff button
❌ "fade-in boxes on scroll" as the only motion — that is not cinematic
❌ Full card grid layout with no spatial intent
❌ Stock photos with no treatment; unmodified starter components
❌ transition: all; instant camera snaps; linear easing
❌ glow/grain/scanlines on everything (they only work as accents)
❌ Essential content hidden behind motion or 3D with no fallback
❌ A terminal input field that does nothing — that is broken UI
```

---

## §15 — Quality Gates: Definition of Done

Do not deliver until every item is true:

```
First Impression
  ✓ Dramatic within 3 seconds

Performance
  ✓ ≥ 55fps on the target device
  ✓ 3D layer never blocks first paint

Accessibility
  ✓ prefers-reduced-motion applied and tested in both CSS and JS
  ✓ WebGL-unavailable path shows a fallback that tells the same story
  ✓ All text passes WCAG AA contrast minimums
  ✓ canvas is aria-hidden="true"; real content lives in the DOM
  ✓ All interactive elements are keyboard accessible with visible focus

Robustness
  ✓ Context loss is handled
  ✓ Resources are disposed on teardown
  ✓ Fully responsive: mobile / tablet / desktop
  ✓ SSR-safe if the project uses server rendering

Design
  ✓ Every scene has a distinct mood — no two adjacent sections feel identical
  ✓ No inert interactive elements
  ✓ Energy curve is clear: rise → peak → resolution

Code
  ✓ No console errors
  ✓ Dependencies are pinned
  ✓ No deprecated global THREE build
```

---

```
This skill ends here.
What does not end is the question you begin with every time:

What does the user feel in the first 3 seconds?

When your answer is clear and intentional —
everything else is execution.
```