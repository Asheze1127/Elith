# web/ — Elith frontend

Next.js (App Router, TypeScript) frontend for Elith RAG. See `../docs/details/directory.md`
§2 for the full layer layout (`app/` routing-only, `components/presentational`
vs `components/container`, `hooks/`, `lib/api/` as the sole fetch boundary,
`context/`, `types/`).

## Getting started

```bash
npm install
npm run dev
```

Open http://localhost:3000. The API base URL is read from
`NEXT_PUBLIC_API_BASE_URL` (see `.env.example`); it defaults to
`http://localhost:8000` for local dev against the FastAPI backend.

## Scripts

```bash
npm run dev     # start the dev server
npm run build   # production build
npm run lint    # ESLint
npm run test    # Vitest (unit tests, e.g. lib/api/client.ts)
```

## Status

The frontend currently includes the chat screen, mode toggle, citation/status/
warning display, feedback submission, `/documents`, and `/review`. The root
`../README.md` has the full local setup and sample-data flow.
