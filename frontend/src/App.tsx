import { useMemo, useRef, useState } from "react";

type ModelRun = {
  prompt: string;
  response: string;
  error: string | null;
  prompt_index: number;
};
type ResultsMap = Record<string, ModelRun[]>; // model -> runs[]

type StartEvent = { event: "start"; count_prompts: number; models: string[] };
type ResultEvent = {
  event: "result";
  model: string;
  prompt_index: number;
  prompt: string;
  response: string;
  error: string | null;
};
type EndEvent = { event: "end" };
type StreamEvent = StartEvent | ResultEvent | EndEvent;

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [countPrompts, setCountPrompts] = useState<number | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [results, setResults] = useState<ResultsMap>({});

  // refs to each model <details> container (so we can expand/collapse all rows inside)
  const modelRefs = useRef<Record<string, HTMLDetailsElement | null>>({});
  const abortRef = useRef<AbortController | null>(null);

  const hasResults = useMemo(() => Object.keys(results).length > 0, [results]);

  async function uploadAndStream(f: File) {
    const controller = new AbortController();
    abortRef.current = controller;

    setError(null);
    setStreaming(true);
    setResults({});
    setCountPrompts(null);
    setModels([]);

    const form = new FormData();
    form.append("file", f);

    let res: Response;

    try {
      res = await fetch("http://localhost:8000/api/upload-stream", {
        method: "POST",
        body: form,
        signal: controller.signal,
      });
    } catch (err: any) {
      setStreaming(false);
      setError(err?.message ?? String(err));
      return;
    }

    if (!res.ok || !res.body) {
      setStreaming(false);
      const msg = await res.text().catch(() => "");
      setError(msg || `Upload failed (${res.status})`);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          let evt: StreamEvent;
          try {
            evt = JSON.parse(trimmed);
          } catch {
            continue;
          }
          handleEvent(evt);
        }
      }
      const leftover = buffer.trim();
      if (leftover) {
        try {
          handleEvent(JSON.parse(leftover));
        } catch {
          /* ignore */
        }
      }
    } catch (err: any) {
      if (!controller.signal.aborted) {
        setError(err?.message ?? String(err));
      }
    } finally {
      setStreaming(false);
    }
  }

  function handleEvent(evt: StreamEvent) {
    if (evt.event === "start") {
      setCountPrompts(evt.count_prompts);
      setModels(evt.models);
      setResults(Object.fromEntries(evt.models.map((m) => [m, []])));
      return;
    }
    if (evt.event === "result") {
      setResults((prev) => {
        const arr = prev[evt.model] ? [...prev[evt.model]] : [];
        arr.push({
          prompt: evt.prompt,
          response: evt.response,
          error: evt.error,
          prompt_index: evt.prompt_index,
        });
        arr.sort((a, b) => a.prompt_index - b.prompt_index);
        return { ...prev, [evt.model]: arr };
      });
      return;
    }
    // evt.event === "end" -> nothing needed
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || streaming) return;
    abortRef.current?.abort(); // cancel any prior run
    await uploadAndStream(file);
  };

  function truncate(s: string, max = 120) {
    if (!s) return "";
    return s.length > max ? s.slice(0, max).trimEnd() + "…" : s;
  }

  function expandCollapseAllRows(modelName: string, open: boolean) {
    const details = modelRefs.current[modelName];
    if (!details) return;
    const rowDropdowns = details.querySelectorAll("details.row-dropdown");
    rowDropdowns.forEach((d) => {
      if (open) (d as HTMLDetailsElement).setAttribute("open", "");
      else (d as HTMLDetailsElement).removeAttribute("open");
    });
  }

  function expandCollapseAllModels(open: boolean) {
    models.forEach((m) => {
      const ref = modelRefs.current[m];
      if (!ref) return;
      if (open) ref.setAttribute("open", "");
      else ref.removeAttribute("open");
    });
  }

  return (
    <div className="app">
      {/* Header stays at top-left */}
      <header className="header">
        <div className="container">
          <h1 className="title">KongLLM Multi-Model Runner</h1>
          <p className="subtitle">
            Upload a <code>.jsonl</code> (one JSON object per line).
          </p>

          <form className="upload-form" onSubmit={onSubmit}>
            <input
              type="file"
              accept=".jsonl"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              disabled={streaming}
            />
            <button className="btn" disabled={!file || streaming}>
              {streaming ? "Running…" : "Upload & Run"}
            </button>
            {streaming && (
              <button
                type="button"
                className="btn"
                onClick={() => abortRef.current?.abort()}
                style={{ marginLeft: 8 }}
              >
                Cancel
              </button>
            )}
          </form>

          {error && <div className="error">Error: {error}</div>}

          {/* Global info + optional model expand/collapse controls */}
          <div className="summary">
            {countPrompts !== null && (
              <>
                Planned prompts: <strong>{countPrompts}</strong>
                {models.length > 0 && (
                  <>
                    {"  "}• Models: <strong>{models.join(", ")}</strong>
                  </>
                )}
              </>
            )}
          </div>

          {models.length > 0 && (
            <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
              <button
                type="button"
                className="btn btn-small"
                onClick={() => expandCollapseAllModels(true)}
                title="Expand all models"
              >
                Expand all models
              </button>
              <button
                type="button"
                className="btn btn-small"
                onClick={() => expandCollapseAllModels(false)}
                title="Collapse all models"
              >
                Collapse all models
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Results render below; header position never changes */}
      <main className="content container">
        {hasResults &&
          Object.entries(results).map(([modelName, runs]) => (
            <details
              key={modelName}
              className="model-dropdown"
              open
              ref={(el) => (modelRefs.current[modelName] = el)}
            >
              <summary className="model-summary">
                <span className="caret" aria-hidden>
                  ▸
                </span>
                <span className="model-summary-title">{modelName}</span>
                <span className="model-count">
                  ({runs.length} / {countPrompts ?? "?"})
                </span>
              </summary>

              <div className="model-body">
                <div className="model-actions">
                  <button
                    className="btn btn-small"
                    onClick={() => expandCollapseAllRows(modelName, true)}
                    title="Expand all rows"
                  >
                    Expand all rows
                  </button>
                  <button
                    className="btn btn-small"
                    onClick={() => expandCollapseAllRows(modelName, false)}
                    title="Collapse all rows"
                  >
                    Collapse all rows
                  </button>
                </div>

                <div className="table-wrap">
                  <table className="results-table">
                    <thead>
                      <tr>
                        <th>Prompt • Response (click row to expand)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runs.map((r, i) => (
                        <tr key={i}>
                          <td className="cell row-dropdown-cell" colSpan={3}>
                            <details className="row-dropdown">
                              <summary>
                                <span className="caret" aria-hidden>
                                  ▸
                                </span>
                                <span className="summary-title">
                                  {truncate(r.prompt, 100)}
                                </span>
                                {r.error ? (
                                  <span className="summary-badge badge-error">
                                    error
                                  </span>
                                ) : (
                                  <span className="summary-badge badge-ok">
                                    ready
                                  </span>
                                )}
                              </summary>

                              <div className="row-body">
                                <div className="row-section">
                                  <div className="row-label">Prompt</div>
                                  <pre className="row-pre">{r.prompt}</pre>
                                </div>

                                <div className="row-section">
                                  <div className="row-label">Response</div>
                                  <pre className="row-pre">{r.response}</pre>
                                </div>

                                {r.error && (
                                  <div className="row-section">
                                    <div className="row-label">Error</div>
                                    <pre className="row-pre row-pre-error">
                                      {r.error}
                                    </pre>
                                  </div>
                                )}
                              </div>
                            </details>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </details>
          ))}

        {!hasResults && !streaming && (
          <p style={{ color: "#bdbdbd", marginTop: 12 }}>
            No results yet. Upload a file to begin.
          </p>
        )}
      </main>
    </div>
  );
}
