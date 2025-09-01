import { useMemo, useState } from "react";

type RowStatus = "running" | "done";

type Row = {
  prompt_index: number;
  prompt: string;
  response?: string;
  error?: string | null;
  status: RowStatus;
  duration_ms?: number;
};

type ModelRows = Record<number, Row>;
type ResultsMap = Record<string, ModelRows>;

type StartEvent = { event: "start"; count_prompts: number; models: string[] };
type ProgressEvent = {
  event: "progress";
  model: string;
  prompt_index: number;
  prompt: string;
  status: "started";
};
type ResultEvent = {
  event: "result";
  model: string;
  prompt_index: number;
  prompt: string;
  response: string;
  error: string | null;
  duration_ms?: number;
};
type EndEvent = { event: "end" };
type StreamEvent = StartEvent | ProgressEvent | ResultEvent | EndEvent;

const ALL_MODELS = [
  "DeepSeek R1 New",
  "DeepSeek R1",
  "Sonnet 3.7",
  "GPT 4o",
  "Nova Premier",
  "Gemini 2.5 Flash",
  "Gemini 2.5 Pro",
];

export default function App() {
  const [prompt, setPrompt] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [availableModels] = useState<string[]>(ALL_MODELS);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);

  const [models, setModels] = useState<string[]>([]);
  const [results, setResults] = useState<ResultsMap>({});

  const hasResults = useMemo(() => Object.keys(results).length > 0, [results]);

  async function sendPrompt(body: any) {
    setError(null);
    setStreaming(true);

    let res: Response;
    try {
      res = await fetch("http://localhost:8000/api/chat-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch (err: any) {
      setStreaming(false);
      setError(err?.message ?? String(err));
      return;
    }

    if (!res.ok || !res.body) {
      setStreaming(false);
      const msg = await res.text().catch(() => "");
      setError(msg || `Request failed (${res.status})`);
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
        } catch {}
      }
    } catch (err: any) {
      setError(err?.message ?? String(err));
    } finally {
      setStreaming(false);
    }
  }

  function handleEvent(evt: StreamEvent) {
    if (evt.event === "start") {
      setModels(evt.models);
      setResults((prev) => {
        const next = { ...prev };
        evt.models.forEach((m) => (next[m] = next[m] || {}));
        return next;
      });
    }

    if (evt.event === "progress") {
      const { model, prompt_index, prompt } = evt;
      setResults((prev) => {
        const modelMap = { ...(prev[model] || {}) };
        modelMap[prompt_index] = { prompt_index, prompt, status: "running" };
        return { ...prev, [model]: modelMap };
      });
    }

    if (evt.event === "result") {
      const { model, prompt_index, prompt, response, error, duration_ms } = evt;
      setResults((prev) => {
        const modelMap = { ...(prev[model] || {}) };
        modelMap[prompt_index] = {
          prompt_index,
          prompt,
          response,
          error,
          status: "done",
          duration_ms,
        };
        return { ...prev, [model]: modelMap };
      });
    }
  }

  async function resetMemory(modelsToReset?: string[]) {
    try {
      await fetch("http://localhost:8000/api/reset-memory", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ models: modelsToReset ?? null }),
      });
      if (modelsToReset && modelsToReset.length) {
        setResults((prev) => {
          const next = { ...prev };
          modelsToReset.forEach((m) => delete next[m]);
          return next;
        });
        setModels((prev) => prev.filter((m) => !modelsToReset.includes(m)));
        setSelectedModels((prev) =>
          prev.filter((m) => !modelsToReset.includes(m))
        );
      } else {
        setResults({});
        setModels([]);
        setSelectedModels([]);
      }
    } catch {
      // ignore
    }
  }

  async function removeModels(modelsToRemove: string[]) {
    if (!modelsToRemove.length) return;
    try {
      await fetch("http://localhost:8000/api/remove-models", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ models: modelsToRemove }),
      });
    } catch {
      // ignore network error
    }
    setResults((prev) => {
      const next = { ...prev };
      modelsToRemove.forEach((m) => delete next[m]);
      return next;
    });
    setModels((prev) => prev.filter((m) => !modelsToRemove.includes(m)));
    setSelectedModels((prev) =>
      prev.filter((m) => !modelsToRemove.includes(m))
    );
  }

  const onRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || streaming) return;

    // clear immediately
    const currentPrompt = prompt;
    setPrompt("");

    const body = {
      prompt: currentPrompt,
      models: selectedModels.length ? selectedModels : undefined,
    };
    await sendPrompt(body);
  };

  function truncate(s: string, max = 100) {
    if (!s) return "";
    return s.length > max ? s.slice(0, max).trimEnd() + "…" : s;
  }

  function toggleModel(name: string) {
    setSelectedModels((prev) =>
      prev.includes(name) ? prev.filter((m) => m !== name) : [...prev, name]
    );
  }

  function chipClass(name: string) {
    const isSelected = selectedModels.includes(name);
    return isSelected ? "chip chip--selected" : "chip";
  }

  return (
    <div className="app">
      <header className="header">
        <div className="container">
          <h1 className="title">KongLLM Multi-Model Runner</h1>
          <p className="subtitle">
            Choose models per prompt. Selected chips are blue. Removing a model
            clears its memory and turns its chip white.
          </p>

          {/* Model picker */}
          <div className="chip-row">
            {availableModels.map((m) => (
              <button
                key={m}
                type="button"
                className={chipClass(m)}
                onClick={() => toggleModel(m)}
                disabled={streaming}
              >
                {m}
              </button>
            ))}
          </div>

          <form className="run-form" onSubmit={onRun}>
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Ask me anything…"
              disabled={streaming}
            />
            <button className="btn" disabled={!prompt.trim() || streaming}>
              {streaming ? "Running…" : "Run"}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() =>
                resetMemory(selectedModels.length ? selectedModels : undefined)
              }
              disabled={streaming}
            >
              Reset memory
            </button>
          </form>

          {error && <div className="error">Error: {error}</div>}
        </div>
      </header>

      <main className="content container">
        {Object.entries(results).length > 0 &&
          Object.entries(results).map(([modelName, rowsMap]) => {
            const rows = Object.values(rowsMap).sort(
              (a, b) => a.prompt_index - b.prompt_index
            );
            const done = rows.filter((r) => r.status === "done").length;

            return (
              <details key={modelName} className="model-dropdown" open>
                <summary className="model-summary">
                  <span className="caret" aria-hidden>
                    ▸
                  </span>
                  <span className="model-summary-title">{modelName}</span>
                  <span className="model-count">({done} turns)</span>
                  <span style={{ marginLeft: "auto" }}>
                    <button
                      type="button"
                      className="btn btn-danger btn-small"
                      onClick={(e) => {
                        e.preventDefault();
                        removeModels([modelName]);
                      }}
                    >
                      Remove
                    </button>
                  </span>
                </summary>

                <div className="model-body">
                  <div className="table-wrap">
                    <table className="results-table">
                      <tbody>
                        {rows.map((r) => (
                          <tr key={r.prompt_index}>
                            <td className="cell row-dropdown-cell" colSpan={3}>
                              <details
                                className={`row-dropdown ${
                                  r.status === "running" ? "is-running" : ""
                                }`}
                              >
                                <summary>
                                  <span className="caret" aria-hidden>
                                    ▸
                                  </span>
                                  <span className="summary-title">
                                    {truncate(r.prompt, 100)}
                                  </span>
                                  {r.status === "running" ? (
                                    <span className="summary-badge badge-running">
                                      <span className="badge-text">
                                        running
                                      </span>
                                    </span>
                                  ) : r.error ? (
                                    <span className="summary-badge badge-error">
                                      <span className="badge-text">error</span>
                                    </span>
                                  ) : (
                                    <span className="summary-badge badge-ok">
                                      <span className="badge-text">ready</span>
                                    </span>
                                  )}
                                  {r.status === "done" &&
                                    r.duration_ms !== undefined && (
                                      <span className="duration">
                                        {Math.round(r.duration_ms)} ms
                                      </span>
                                    )}
                                </summary>

                                <div className="row-body">
                                  <div className="row-section">
                                    <div className="row-label">Prompt</div>
                                    <pre className="row-pre">{r.prompt}</pre>
                                  </div>

                                  {r.status === "done" && (
                                    <div className="row-section">
                                      <div className="row-label">Response</div>
                                      <pre className="row-pre">
                                        {r.response}
                                      </pre>
                                    </div>
                                  )}

                                  {r.status === "done" && r.error && (
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
            );
          })}

        {!hasResults && !streaming && (
          <p className="empty-note">
            No results yet. Pick models (or leave empty to run all), type a
            prompt, and click Run.
          </p>
        )}
      </main>
    </div>
  );
}
