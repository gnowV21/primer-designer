# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Read [HANDOFF_THESIS_STATUS.md](HANDOFF_THESIS_STATUS.md) first** — current project status, locked decisions, and next steps for the thesis. Keep it updated when a milestone changes.

## Development Commands

### Backend (Terminal 1)
```bash
cd backend
pip install -r requirements.txt
python app.py          # runs on http://localhost:5000
```

### Frontend (Terminal 2)
```bash
cd frontend
npm install
npm run dev            # runs on http://localhost:5173
npm run build          # production build → dist/
npm run preview        # preview production build
```

### Tests
```bash
cd backend && python -m pytest tests visualization -q --ignore=tests/smoke   # unit + route tests
npx playwright test          # e2e (repo root; needs both dev servers running)
```
No linter is configured yet.

## Architecture

This is a **split-stack** web app: a Python/Flask backend and a React/Vite frontend running as two separate processes during development.

### Request flow
Browser → Vite dev server (`:5173`) → `/api/*` proxy → Flask (`:5000`) → miRBase REST API (`https://mirbase.org/api/mirna/`)

In production, `/api/*` must be reverse-proxied to the Flask server separately (Vite proxy is dev-only).

### Backend (`backend/`)
- `app.py` — Flask entry point; registers blueprints; CORS allowed for `localhost:5173` and `localhost:3000`; exposes `GET /api/health`
- `routes/mirbase.py` — `GET /api/mirbase/<mirna_id>`: tries `?accession=<id>` first, then `?name=<id>`, returns `{id, accession, sequence, family, species, length}` or 404
- Stack: **Flask 3 + flask-cors + requests + primer3-py + ViennaRNA + biopython + numpy + flask-limiter + reportlab** (see `requirements.txt`); BLAST+ is a system binary. Do not add dependencies beyond these without a reason recorded in the PR.

### Frontend (`frontend/src/`)
- Fixed stack: **React 18 + Vite 5 + Tailwind 3 + React Router DOM v6 + Axios** — no Redux, no Formik, no UI component libraries
- `constants/defaults.js` — single source of truth for all default slider/input values and their min/max limits
- `hooks/useMiRBase.js` — async miRNA lookup; states: `idle | loading | found | not_found | error`
- `components/ui/` — four low-level primitives: `Tooltip`, `Toggle`, `Slider`, `RangeSlider`
- `pages/SearchPage/` — main feature page; state owned at `index.jsx`, passed down to four sub-groups: `SequenceGroup`, `ThermodynamicGroup`, `PrimerConstraintsGroup`, `QpcrConditionsGroup`

### Tailwind custom colors
Colors are defined under `theme.extend.colors` (not `theme.colors`) to preserve Tailwind's built-in palette:
- `teal-50/200/600/800` — brand greens (`#E1F5EE / #5DCAA5 / #0F6E56 / #085041`)
- `red-50/400/600` — error states

### RangeSlider implementation note
Two `<input type="range">` elements are stacked with `position: absolute`. The filled track between thumbs is a CSS `linear-gradient` computed from `leftPct` and `rightPct` as inline styles. The constraint `minVal ≤ maxVal - step` must be enforced in `onMinChange`/`onMaxChange` handlers.

### Domain context
Stem-loop RT-qPCR (Chen et al. 2005): designs three primers for mature miRNA quantification — a stem-loop RT primer, a forward qPCR primer, and a fixed universal reverse primer (`5'-CCAGTGCAGGGTCCGAGGTA-3'`). The RT 3′ overhang (binding region) is **6 nt by default** (Chen 2005). **5 and 7 nt are supported** (project decision 2026-09-18) and always carry an off-label warning; anything outside 5–7 nt is rejected with HTTP 400. The overhang length is read from the RT primer (`len(S) − 44`) wherever a primer is analysed or visualised — never assumed to be 6.
