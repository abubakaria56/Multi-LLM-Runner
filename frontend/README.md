# Multi-LLM Runner frontend

React and TypeScript (Vite) interface for Multi-LLM Runner. It lets you pick models, sends a prompt to the backend, and renders each model's streamed answer in its own column with Markdown, syntax highlighting and KaTeX maths.

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # type-check and production build
```

The backend address defaults to `http://localhost:8000`; set `VITE_API_BASE_URL` in `.env` to change it (see `.env.example`).

See the [project README](../README.md) for the full setup.
