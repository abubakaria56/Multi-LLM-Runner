import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import katex from "katex";
import "katex/dist/katex.min.css";

/* ---------------- Types ---------------- */

type RowStatus = "running" | "done";

type Row = {
  prompt_index: number; // client-side turn id
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

/* ---------------- Constants ---------------- */

const ALL_MODELS = [
  "DeepSeek R1 New",
  "DeepSeek R1",
  "Sonnet 3.7",
  "GPT 4o",
  "Nova Premier",
  "Gemini 2.5 Flash",
  "Gemini 2.5 Pro",
];

/* ---------------- Math/Markdown sanitization ---------------- */

function seemsMathy(s: string) {
  return /\\(sum|frac|vec|boldsymbol|mathbf|mathrm|alpha|beta|gamma|theta|phi|Phi|nabla|int|cdot|times|le|ge|approx|Rightarrow|Leftarrow|to|pm|sqrt|over|hat|bar|dot|ddot|partial|boxed|text|displaystyle|prod)/i.test(
    s
  );
}

function transformOutsideCode(text: string, fn: (t: string) => string) {
  const re = /```[\s\S]*?```/g;
  let out = "";
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    out += fn(text.slice(last, m.index));
    out += m[0];
    last = m.index + m[0].length;
  }
  out += fn(text.slice(last));
  return out;
}

function normalizeSymbols(s: string) {
  return s
    .replace(/∑/g, "\\sum ")
    .replace(/⇒/g, "\\Rightarrow ")
    .replace(/→/g, "\\to ")
    .replace(/≤/g, "\\le ")
    .replace(/≥/g, "\\ge ")
    .replace(/±/g, "\\pm ")
    .replace(/×/g, "\\times ")
    .replace(/·/g, "\\cdot ")
    .replace(/[“”]/g, '"')
    .replace(/[‘’]/g, "'");
}

function balanceBraces(formula: string) {
  let open = 0;
  for (const ch of formula) {
    if (ch === "{") open++;
    else if (ch === "}") open = Math.max(0, open - 1);
  }
  if (open > 0) return formula + "}".repeat(open);

  let needTrim = 0;
  for (const ch of formula) if (ch === "}") needTrim++;
  for (const ch of formula)
    if (ch === "{") needTrim = Math.max(0, needTrim - 1);
  if (needTrim > 0) {
    let i = formula.length - 1;
    while (i >= 0 && needTrim > 0) {
      if (formula[i] === "}") needTrim--;
      i--;
    }
    return formula.slice(0, i + 1);
  }
  return formula;
}

function autoFixAndValidateLatex(
  src: string,
  displayMode: boolean
): string | null {
  let f = src.trim();
  if (!f) return null;

  f = normalizeSymbols(f);
  f = f.replace(/\s+_/g, "_").replace(/\s+\^/g, "^");

  if (f.startsWith("\\(") && f.endsWith("\\)")) f = f.slice(2, -2);
  if (f.startsWith("\\[") && f.endsWith("\\]")) f = f.slice(2, -2);

  f = balanceBraces(f);

  try {
    katex.renderToString(f, {
      displayMode,
      throwOnError: true,
      strict: "warn",
    });
    return f;
  } catch {
    const pruned = f.replace(/}+$/g, "");
    try {
      katex.renderToString(pruned, {
        displayMode,
        throwOnError: true,
        strict: "warn",
      });
      return pruned;
    } catch {
      return null;
    }
  }
}

function normalizeAndSanitizeMarkdown(md: string): string {
  return transformOutsideCode(md, (text) => {
    let out = text;
    out = out.replace(/\$\s+([^$]+?)\s+\$/g, (_m, inner) => `$${inner}$`);
    out = out.replace(/\\\[(.+?)\\\]/gs, (_m, inner) => `$$${inner}$$`);
    out = out.replace(/\\\((.+?)\\\)/gs, (_m, inner) => `$${inner}$`);
    out = normalizeSymbols(out);

    out = out.replace(/\$\$([\s\S]*?)\$\$/g, (_m, inner) => {
      if (!seemsMathy(inner)) return `$$${inner}$$`;
      const fixed = autoFixAndValidateLatex(inner, true);
      return fixed ? `$$${fixed}$$` : "";
    });

    let res = "";
    for (let i = 0; i < out.length; i++) {
      const ch = out[i];
      if (ch === "$") {
        if (out[i + 1] === "$") {
          res += "$";
          continue;
        }
        let j = i + 1;
        let found = false;
        while (j < out.length) {
          if (out[j] === "\\") {
            j += 2;
            continue;
          }
          if (out[j] === "$") {
            found = true;
            break;
          }
          j++;
        }
        if (found) {
          const inner = out.slice(i + 1, j);
          if (seemsMathy(inner)) {
            const fixed = autoFixAndValidateLatex(inner, false);
            if (fixed) res += `$${fixed}$`;
          } else {
            res += `$${inner}$`;
          }
          i = j;
        } else {
          res += ch;
        }
      } else {
        res += ch;
      }
    }

    res = res.replace(/\s*\$\$\s*/g, "\n$$\n");
    return res;
  });
}

/* ---------------- Error classification ---------------- */

function isTransientError(msg?: string | null) {
  if (!msg) return false;
  const s = msg.toLowerCase();
  return /(^|\D)(502|503|504|429)(\D|$)|timeout|temporar|unavailable|gateway|rate limit|overload|capacity|backlog/.test(
    s
  );
}

/* ---------------- App ---------------- */

export default function App() {
  const [prompt, setPrompt] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [availableModels] = useState<string[]>(ALL_MODELS);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);

  // current turn's models (from /start)
  const [models, setModels] = useState<string[]>([]);

  // results: results[model][turnId] -> Row
  const [results, setResults] = useState<ResultsMap>({});

  // which models were used for each turn
  const [turnModels, setTurnModels] = useState<Record<number, string[]>>({});

  // user prompts per turn id
  const [turnPrompts, setTurnPrompts] = useState<Record<number, string>>({});

  // client-side turn counters
  const turnSeqRef = useRef(0);
  const activeTurnRef = useRef<number | null>(null);

  // AbortController for current run
  const abortRef = useRef<AbortController | null>(null);

  // Run button visual state: idle | busy | just-done
  const [runHue, setRunHue] = useState<"idle" | "busy" | "done">("idle");
  useEffect(() => {
    if (streaming) {
      setRunHue("busy");
    } else {
      // briefly show green after finishing
      setRunHue("done");
      const t = setTimeout(() => setRunHue("idle"), 1200);
      return () => clearTimeout(t);
    }
  }, [streaming]);

  // ----- TIMELINE ORDER: oldest → newest
  const turnIds = useMemo(() => {
    const s = new Set<number>();
    Object.values(results).forEach((rowsMap) =>
      Object.keys(rowsMap).forEach((k) => s.add(Number(k)))
    );
    Object.keys(turnModels).forEach((tid) => s.add(Number(tid)));
    return Array.from(s).sort((a, b) => a - b);
  }, [results, turnModels]);

  const newestTurnId = useMemo(
    () => (turnIds.length ? turnIds[turnIds.length - 1] : null),
    [turnIds]
  );

  const chatEndRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [turnIds]);

  const hasResults = useMemo(() => Object.keys(results).length > 0, [results]);

  function promptTextFor(turnId: number) {
    return turnPrompts[turnId] ?? "";
  }

  async function sendPrompt(body: any) {
    setError(null);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    let res: Response;
    try {
      res = await fetch("http://localhost:8000/api/chat-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
    } catch (err: any) {
      if (controller.signal.aborted) {
        // aborted locally: don't surface an error
        setStreaming(false);
        return;
      }
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
      if (!controller.signal.aborted) {
        setError(err?.message ?? String(err));
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
      activeTurnRef.current = null;
    }
  }

  function handleEvent(evt: StreamEvent) {
    const turnId = activeTurnRef.current;
    if (turnId == null) return;

    if (evt.event === "start") {
      setModels(evt.models);
      setTurnModels((prev) => ({ ...prev, [turnId]: evt.models }));
      setResults((prev) => {
        const next = { ...prev };
        evt.models.forEach((m) => (next[m] = next[m] || {}));
        return next;
      });
      return;
    }

    if (evt.event === "progress") {
      const { model, prompt } = evt;
      setResults((prev) => {
        const modelMap = { ...(prev[model] || {}) };
        modelMap[turnId] = { prompt_index: turnId, prompt, status: "running" };
        return { ...prev, [model]: modelMap };
      });
      return;
    }

    if (evt.event === "result") {
      const { model, prompt, response, error, duration_ms } = evt;
      setResults((prev) => {
        const modelMap = { ...(prev[model] || {}) };
        modelMap[turnId] = {
          prompt_index: turnId,
          prompt,
          response,
          error,
          status: "done",
          duration_ms,
        };
        return { ...prev, [model]: modelMap };
      });
      return;
    }
  }

  /** Abort the current run and erase any partial state of this turn. */
  function stopCurrentTurn() {
    const turnId = activeTurnRef.current;
    if (turnId == null) return;

    // Abort network streaming
    abortRef.current?.abort();

    // Remove this turn from all state (but keep past turns)
    setResults((prev) => {
      const next: ResultsMap = {};
      for (const [model, rows] of Object.entries(prev)) {
        const { [turnId]: _omit, ...rest } = rows;
        next[model] = rest;
      }
      return next;
    });
    setTurnModels((prev) => {
      const { [turnId]: _omit, ...rest } = prev;
      return rest;
    });
    setTurnPrompts((prev) => {
      const { [turnId]: _omit, ...rest } = prev;
      return rest;
    });

    activeTurnRef.current = null;
    setStreaming(false);
    setError(null);
  }

  async function resetMemory(modelsToReset?: string[]) {
    try {
      await fetch("http://localhost:8000/api/reset-memory", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ models: modelsToReset ?? null }),
      });
      if (modelsToReset?.length) {
        setResults((prev) => {
          const next = { ...prev };
          modelsToReset.forEach((m) => delete next[m]);
          return next;
        });
      } else {
        setResults({});
        setModels([]);
        setTurnModels({});
        setTurnPrompts({});
        activeTurnRef.current = null;
        abortRef.current?.abort();
        abortRef.current = null;
        turnSeqRef.current = 0;
      }
    } catch {
      /* ignore */
    }
  }

  const onRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || streaming) return;

    const currentPrompt = prompt;
    setPrompt(""); // reset input immediately

    // If first prompt & none selected, auto-select all chips so they turn blue during the run
    if (selectedModels.length === 0 && turnSeqRef.current === 0) {
      setSelectedModels(ALL_MODELS);
    }

    const newTurn = ++turnSeqRef.current;
    activeTurnRef.current = newTurn;
    setTurnPrompts((prev) => ({ ...prev, [newTurn]: currentPrompt }));

    const body = {
      prompt: currentPrompt,
      models: selectedModels.length ? selectedModels : undefined,
    };
    await sendPrompt(body);
  };

  function toggleModel(name: string) {
    setSelectedModels((prev) =>
      prev.includes(name) ? prev.filter((m) => m !== name) : [...prev, name]
    );
  }
  function chipClass(name: string) {
    return selectedModels.includes(name) ? "chip chip--selected" : "chip";
  }
  function orderModels(list: string[]) {
    const idx = (m: string) => {
      const i = ALL_MODELS.indexOf(m);
      return i === -1 ? Number.MAX_SAFE_INTEGER : i;
    };
    return [...new Set(list)].sort(
      (a, b) => idx(a) - idx(b) || a.localeCompare(b)
    );
  }

  return (
    <div className="app">
      <header className="header">
        <div className="container">
          <h1 className="title">KongLLM Multi-Model Runner</h1>
          <p className="subtitle">
            Type while a run is in progress. Stop cancels only the current turn.
          </p>

          <div className="chip-row">
            {availableModels.map((m) => (
              <button
                key={m}
                type="button"
                className={chipClass(m)}
                onClick={() => toggleModel(m)}
                // You can still change selection while running if you want; next turn will use it.
                aria-pressed={selectedModels.includes(m)}
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
              className={streaming ? "input input--busy" : "input"}
            />
            <button
              className={`btn btn-run ${
                runHue === "busy"
                  ? "is-busy"
                  : runHue === "done"
                  ? "is-done"
                  : ""
              }`}
              disabled={!prompt.trim() || streaming}
            >
              {streaming ? "Running…" : "Run"}
            </button>

            {streaming && (
              <button
                type="button"
                className="btn btn-stop"
                onClick={stopCurrentTurn}
                title="Stop current turn"
              >
                Stop
              </button>
            )}

            <button
              type="button"
              className="btn btn-secondary"
              onClick={() =>
                resetMemory(selectedModels.length ? selectedModels : undefined)
              }
              disabled={streaming}
              title={
                selectedModels.length
                  ? "Reset only selected models"
                  : "Reset all models"
              }
            >
              Reset memory
            </button>
          </form>

          {error && <div className="error">Error: {error}</div>}
        </div>
      </header>

      {/* Chat timeline (oldest → newest) with auto-scroll to bottom */}
      <main className="container chat-timeline">
        {turnIds.map((turnId) => {
          const isNewest = newestTurnId !== null && newestTurnId === turnId;
          const userText = promptTextFor(turnId);

          const planned = turnModels[turnId] ?? [];
          const fromResults = Object.keys(results).filter(
            (m) => results[m]?.[turnId]
          );
          const modelsForTurn = orderModels([...planned, ...fromResults]);

          return (
            <section className="chat-turn" key={`turn-${turnId}`}>
              <div className="user-bubble-wrap">
                <div className="user-label">USER PROMPT</div>
                <div className="user-bubble">{userText}</div>
              </div>

              <div className="responses-wrap">
                <div className="responses-title">RESPONSES</div>

                {modelsForTurn.map((modelName) => {
                  const row = results[modelName]?.[turnId];

                  if (!row) {
                    if (isNewest && !streaming) {
                      return (
                        <details
                          key={`na-${modelName}-${turnId}`}
                          className="resp-dropdown"
                          open
                        >
                          <summary className="resp-summary">
                            <span className="caret" aria-hidden>
                              ▸
                            </span>
                            <span className="resp-model">{modelName}</span>
                            <span className="summary-badge badge-na">
                              <span className="badge-text">n/a</span>
                            </span>
                          </summary>
                          <div className="resp-body">
                            <div className="placeholder">
                              Not available right now.
                            </div>
                          </div>
                        </details>
                      );
                    }
                    return null;
                  }

                  const normalized = normalizeAndSanitizeMarkdown(
                    row.response || ""
                  );
                  const isRunning = row.status === "running";
                  const isNA =
                    row.status === "done" &&
                    !!row.error &&
                    isTransientError(row.error);

                  return (
                    <details
                      key={`resp-${modelName}-${turnId}`}
                      className={`resp-dropdown ${
                        isRunning ? "is-running" : ""
                      }`}
                      open
                    >
                      <summary className="resp-summary">
                        <span className="caret" aria-hidden>
                          ▸
                        </span>
                        <span className="resp-model">{modelName}</span>

                        {isRunning ? (
                          <span className="summary-badge badge-running">
                            <span className="badge-text">running</span>
                          </span>
                        ) : isNA ? (
                          <span className="summary-badge badge-na">
                            <span className="badge-text">n/a</span>
                          </span>
                        ) : row.error ? (
                          <span className="summary-badge badge-error">
                            <span className="badge-text">error</span>
                          </span>
                        ) : (
                          <span className="summary-badge badge-ok">
                            <span className="badge-text">ready</span>
                          </span>
                        )}

                        {row.status === "done" &&
                          row.duration_ms !== undefined && (
                            <span className="duration">
                              {Math.round(row.duration_ms)} ms
                            </span>
                          )}
                      </summary>

                      <div className="resp-body">
                        {row.status === "done" && isNA && (
                          <div className="placeholder">
                            Not available right now.
                          </div>
                        )}

                        {row.status === "done" && !row.error && normalized && (
                          <article className="md">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm, remarkMath] as any}
                              rehypePlugins={
                                [
                                  rehypeHighlight as any,
                                  [
                                    rehypeKatex as any,
                                    { throwOnError: true, strict: "warn" },
                                  ],
                                ] as any
                              }
                              components={{
                                a: (props: any) => (
                                  <a
                                    {...props}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                  />
                                ),
                                code: ({
                                  inline,
                                  className,
                                  children,
                                  ...props
                                }: any) =>
                                  inline ? (
                                    <code className={className} {...props}>
                                      {children}
                                    </code>
                                  ) : (
                                    <pre className="md-pre">
                                      <code className={className} {...props}>
                                        {children}
                                      </code>
                                    </pre>
                                  ),
                              }}
                            >
                              {normalized}
                            </ReactMarkdown>
                          </article>
                        )}

                        {row.status === "done" && row.error && !isNA && (
                          <pre className="row-pre row-pre-error">
                            {row.error}
                          </pre>
                        )}
                      </div>
                    </details>
                  );
                })}
              </div>
            </section>
          );
        })}

        <div ref={chatEndRef} />
        {!hasResults && !streaming && (
          <p className="empty-note">
            No turns yet. Pick models (or leave empty to run all), type a
            prompt, and click Run.
          </p>
        )}
      </main>
    </div>
  );
}
