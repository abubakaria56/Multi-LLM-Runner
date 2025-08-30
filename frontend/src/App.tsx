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

        // process all complete lines; keep the last partial
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
      // leftover line if any
      const leftover = buffer.trim();
      if (leftover) {
        try {
          handleEvent(JSON.parse(leftover));
        } catch {
          /* ignore */
        }
      }
    } catch (err: any) {
      if (controller.signal.aborted) {
        // user cancelled; ignore
      } else {
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
      // initialize empty arrays so tables render immediately
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
        // sort by prompt_index so rows remain ordered as they arrive
        arr.sort((a, b) => a.prompt_index - b.prompt_index);
        return { ...prev, [evt.model]: arr };
      });
      return;
    }
    if (evt.event === "end") {
      // nothing required; streaming=false will flip when the network closes
      return;
    }
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || streaming) return;

    // cancel any prior stream
    abortRef.current?.abort();

    await uploadAndStream(file);
  };

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
          {countPrompts !== null && (
            <div className="summary">
              Planned prompts: <strong>{countPrompts}</strong>
              {models.length > 0 && (
                <>
                  {"  "}• Models: <strong>{models.join(", ")}</strong>
                </>
              )}
            </div>
          )}
        </div>
      </header>

      {/* Results render below; header position never changes */}
      <main className="content container">
        {hasResults &&
          Object.entries(results).map(([modelName, runs]) => (
            <section key={modelName} className="model-block">
              <h2 className="model-name">
                {modelName}{" "}
                <span style={{ fontWeight: 400, fontSize: 14, color: "#aaa" }}>
                  ({runs.length} / {countPrompts ?? "?"})
                </span>
              </h2>

              <div className="table-wrap">
                <table className="results-table">
                  <thead>
                    <tr>
                      <th style={{ width: "35%" }}>Prompt</th>
                      <th>Response</th>
                      <th>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((r, i) => (
                      <tr key={i}>
                        <td className="cell prompt">
                          <pre>{r.prompt}</pre>
                        </td>
                        <td className="cell response">
                          <pre>{r.response}</pre>
                        </td>
                        <td className="cell error-cell">{r.error ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
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
