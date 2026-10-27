# JobPilot — Frontend

The modern web dashboard for JobPilot: an application tracker, job discovery explorer, career assistant, analytics suite, and system status monitor.

Built with React 19, TypeScript, Vite, Tailwind CSS v4, Recharts, and Axios.

---

## 1. Quick Start

Run the backend first (port 8000), then start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000> in your browser.

> The development server runs on **port 3000** and automatically proxies requests starting with `/api` to the FastAPI backend at `http://127.0.0.1:8000`.

### Production Build

```bash
npm run build
npm run preview
```

- `npm run build`: Runs strict TypeScript type-checking (`tsc --noEmit`) and compiles optimized production assets to `dist/`.
- `npm run preview`: Serves the production build locally at <http://127.0.0.1:4173>.

### Scripts

| Script | Purpose |
| --- | --- |
| `npm run dev` | Vite dev server with hot module replacement on port 3000 |
| `npm run build` | Strict typecheck (`tsc --noEmit`) and production bundle build |
| `npm run preview` | Serve the production build locally on port 4173 |
| `npm run typecheck` | Run TypeScript verification without emitting files |

---

## 2. Configuration

Configuration is managed via optional environment variables in `frontend/.env` (see `.env.example`):

| Variable | Default | Description |
| --- | --- | --- |
| `VITE_API_BASE_URL` | *(empty)* | Optional absolute URL of the backend (e.g. `http://127.0.0.1:8000`). Leaving this empty uses relative `/api` paths with the Vite proxy. |

---

## 3. Design System

The interface uses a warm, editorial career-management palette defined in `src/index.css`:

- **Palette:**
  - Background: `#F7F7F4`
  - Main Surfaces: `#FFFFFF`, `#F0F1EC`
  - Text: `#20231F` (primary), `#6F746E` (secondary), `#9B9F99` (tertiary)
  - Brand Accent: `#246B50` (hover `#1D5741`, light `#E6F1E9`)
  - Semantic Colors: Amber (`#C18B45`), Red (`#A33E32`, light `#F7E9E6`)
  - Subtle Borders: `#E7E8E3`
- **Typography:** Manrope (`@fontsource/manrope`) for interface copy and headings.
- **Geometry:** Subtle 6–8px corner rounding with clean spacing.
