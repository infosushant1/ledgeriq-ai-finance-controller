import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API = "/api";

async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, options);
  const text = await res.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = { detail: text }; }
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

const money = (v) => v == null || v === "" ? "—" : `₹${Number(v).toLocaleString("en-IN", {maximumFractionDigits: 2})}`;
const pct = (v) => `${Number(v || 0).toFixed(1)}%`;
const title = (s = "") => s.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, c => c.toUpperCase());

function Icon({ children }) {
  return <span className="icon">{children}</span>;
}

function App() {
  const [summary, setSummary] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [exceptions, setExceptions] = useState([]);
  const [audit, setAudit] = useState([]);
  const [selected, setSelected] = useState(null);
  const [selectedType, setSelectedType] = useState("");
  const [chat, setChat] = useState("");
  const [chatAnswer, setChatAnswer] = useState("");
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("System ready");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("ALL");
  const [tab, setTab] = useState("overview");

  async function refresh() {
    const [s, t, e, a] = await Promise.all([
      api("/summary"), api("/transactions"), api("/exceptions"), api("/audit?limit=80")
    ]);
    setSummary(s); setTransactions(t); setExceptions(e); setAudit(a);
  }

  useEffect(() => { refresh().catch(e => setMessage(e.message)); }, []);

  async function action(label, fn) {
    setBusy(label); setMessage(`${label}…`);
    try {
      const result = await fn();
      setMessage(result?.message || `${label} complete`);
      await refresh();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setBusy("");
    }
  }

  async function generateDemo() {
    await action("Generating demo data", () => api("/generate-demo", { method: "POST" }));
  }

  async function reconcile() {
    await action("Running reconciliation", () => api("/reconcile", { method: "POST" }));
  }

  async function askCopilot(question = chat) {
    if (!question.trim()) return;
    setBusy("copilot");
    try {
      const result = await api("/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({question})
      });
      setChatAnswer(result.answer);
      await refresh();
    } catch (e) { setChatAnswer(`Error: ${e.message}`); }
    finally { setBusy(""); }
  }

  async function openTransaction(id) {
    setSelectedType("transaction");
    setSelected(await api(`/transactions/${id}`));
  }

  async function openException(id) {
    setSelectedType("exception");
    setSelected(await api(`/exceptions/${id}`));
  }

  async function review(id, status) {
    await action(`Review → ${status}`, () => api(`/exceptions/${id}/review`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({status})
    }));
    if (selectedType === "exception") setSelected(await api(`/exceptions/${id}`));
  }

  async function explainException(id) {
    setBusy("ai");
    try {
      const result = await api(`/exceptions/${id}/ai-explain`, {method:"POST"});
      setSelected(prev => ({...prev, ai: result}));
      await refresh();
    } catch (e) {
      setMessage(`AI explanation error: ${e.message}`);
    } finally { setBusy(""); }
  }

  const filtered = useMemo(() => transactions.filter(t => {
    const q = search.toLowerCase();
    const hit = !q || [t.order_id, t.gateway_id, t.bank_id, t.status].join(" ").toLowerCase().includes(q);
    const statusHit = filter === "ALL" || t.status === filter;
    return hit && statusHit;
  }), [transactions, search, filter]);

  const topExceptions = exceptions.slice(0, 7);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">$</div>
          <div><b>LedgerIQ</b><span>AI Finance Controller</span></div>
        </div>
        <nav>
          {[
            ["overview", "◔", "Overview"],
            ["reconciliation", "⌁", "Reconciliation"],
            ["exceptions", "⚠", "Exceptions"],
            ["copilot", "✦", "Finance Copilot"],
            ["audit", "◫", "Audit Trail"]
          ].map(([id, icon, label]) => (
            <button key={id} className={tab === id ? "nav active" : "nav"} onClick={() => setTab(id)}>
              <Icon>{icon}</Icon>{label}
              {id === "exceptions" && exceptions.length ? <em>{exceptions.length}</em> : null}
            </button>
          ))}
        </nav>
        <div className="sidebarBottom">
          <div>✓ Audit-ready workflow</div>
          <small>Deterministic matching + AI reasoning</small>
        </div>
      </aside>

      <main className="main">
        <header className="header">
          <div>
            <div className="eyebrow">FINANCE OPERATIONS / CONTROL CENTER</div>
            <h1>{tab === "overview" ? "Reconciliation overview" : title(tab)}</h1>
            <p>Close the loop between orders, payments and settlements.</p>
          </div>
          <div className="actions">
            <button className="button secondary" onClick={() => document.getElementById("fileInput").click()}>
              <Icon>↥</Icon> Upload CSVs
            </button>
            <input id="fileInput" type="file" multiple accept=".csv" hidden onChange={async (e) => {
              const files = [...e.target.files];
              const map = {};
              files.forEach(f => map[f.name] = f);
              if (!map["orders.csv"] || !map["payment_gateway.csv"] || !map["bank_transactions.csv"]) {
                setMessage("Select orders.csv, payment_gateway.csv and bank_transactions.csv together.");
                return;
              }
              const form = new FormData();
              form.append("orders", map["orders.csv"]);
              form.append("payment_gateway", map["payment_gateway.csv"]);
              form.append("bank_transactions", map["bank_transactions.csv"]);
              await action("Uploading CSVs", () => api("/upload", {method:"POST", body:form}));
            }} />
            <button className="button secondary" onClick={generateDemo} disabled={!!busy}><Icon>✦</Icon> Demo data</button>
            <button className="button primary" onClick={reconcile} disabled={!!busy}><Icon>⟳</Icon> Run reconciliation</button>
          </div>
        </header>

        <div className={`status ${message.startsWith("Error") ? "error" : ""}`}>
          <span className="dot"></span>{message}<span className="engine">Engine online ↗</span>
        </div>

        <section className="cards">
          <Metric label="Records processed" value={summary?.total_records ?? 0} />
          <Metric label="Matched / probable" value={summary?.matched_or_probable ?? 0} tone="good" />
          <Metric label="Needs review" value={summary?.needs_review ?? 0} tone="warn" />
          <Metric label="Unresolved" value={summary?.unresolved ?? 0} tone="bad" />
          <Metric label="Amount at risk" value={money(summary?.amount_at_risk)} tone="risk" />
          <Metric label="Throughput" value={summary?.throughput_records_per_second ? `${Number(summary.throughput_records_per_second).toLocaleString()} / sec` : "—"} />
        </section>

        <section className="quality">
          <div>
            <span>Match rate</span><b>{pct(summary?.match_rate)}</b>
          </div>
          <div>
            <span>Precision</span><b>{pct(summary?.precision)}</b>
          </div>
          <div>
            <span>Recall</span><b>{pct(summary?.recall)}</b>
          </div>
          <div>
            <span>F1 score</span><b>{pct(summary?.f1_score)}</b>
          </div>
          <div>
            <span>Processing time</span><b>{summary?.processing_time_seconds ? `${summary.processing_time_seconds}s` : "—"}</b>
          </div>
          <div>
            <span>Validation set</span><b>{summary?.validation_records ?? 0}</b>
          </div>
        </section>

        {(tab === "overview" || tab === "reconciliation") && (
          <section className="gridMain">
            <div className="panel ledger">
              <div className="panelHead">
                <div><h2>Transaction ledger</h2><small>{filtered.length} visible records · click a row for decision evidence</small></div>
                <div className="filters">
                  <input placeholder="Search order / gateway / bank" value={search} onChange={e => setSearch(e.target.value)} />
                  <select value={filter} onChange={e => setFilter(e.target.value)}>
                    <option>ALL</option><option>MATCHED</option><option>PROBABLE_MATCH</option><option>NEEDS_REVIEW</option><option>UNRESOLVED</option>
                  </select>
                </div>
              </div>
              <div className="tableWrap">
                <table>
                  <thead><tr><th>Order</th><th>Gateway</th><th>Bank</th><th>Amount</th><th>Status</th><th>Confidence</th></tr></thead>
                  <tbody>
                    {filtered.slice(0, 120).map(t => (
                      <tr key={t.id} onClick={() => openTransaction(t.id)}>
                        <td>{t.order_id || "—"}</td><td>{t.gateway_id || "—"}</td><td>{t.bank_id || "—"}</td>
                        <td>{money(t.order_amount ?? t.gateway_amount ?? t.bank_amount)}</td>
                        <td><span className={`pill ${t.status.toLowerCase()}`}>{title(t.status)}</span></td>
                        <td>{pct((t.confidence || 0) * 100)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="panel exceptionsPanel">
              <div className="panelHead"><div><h2>Exception queue</h2><small>Human attention only where confidence is insufficient</small></div></div>
              <div className="exceptionList">
                {topExceptions.map(e => (
                  <button className="exceptionRow" key={e.id} onClick={() => openException(e.id)}>
                    <div className={`exceptionIcon ${e.severity.toLowerCase()}`}>⚠</div>
                    <div className="exceptionText">
                      <b>{title(e.exception_type)}</b>
                      <span>{e.order_id || "Source-only transaction"} · {money(e.amount_at_risk)} at risk</span>
                    </div>
                    <div className="priority">{Math.round(e.priority_score)}<small>priority</small></div>
                    <span>›</span>
                  </button>
                ))}
                {!topExceptions.length && <div className="empty">No exceptions. Generate demo data and run reconciliation.</div>}
              </div>
            </div>
          </section>
        )}

        {(tab === "overview" || tab === "exceptions") && (
          <section className="lowerGrid">
            <div className="panel">
              <div className="panelHead"><div><h2>Exception intelligence</h2><small>Breakdown by operational failure mode</small></div></div>
              <div className="breakdown">
                {(summary?.exception_breakdown || []).map(x => {
                  const max = Math.max(...(summary.exception_breakdown || []).map(y => y.count), 1);
                  return <div className="breakItem" key={x.type}>
                    <div><span>{title(x.type)}</span><b>{x.count}</b></div>
                    <div className="bar"><i style={{width:`${(x.count/max)*100}%`}} /></div>
                  </div>
                })}
                {!summary?.exception_breakdown?.length && <div className="empty">No exceptions yet.</div>}
              </div>
            </div>

            <div className="panel copilotPanel">
              <div className="panelHead"><div><h2>Finance Copilot</h2><small>Grounded in the current reconciliation</small></div><span className="aiBadge">✦ GROUNDED</span></div>
              <div className="quickPrompts">
                {["What is the amount at risk?", "Which exception is most common?", "How many unresolved records?", "What is the match rate?"].map(q =>
                  <button key={q} onClick={() => askCopilot(q)}>{q}</button>
                )}
              </div>
              <div className="chatBox">
                {chatAnswer && <div className="answer">{chatAnswer}</div>}
                <input value={chat} onChange={e => setChat(e.target.value)} onKeyDown={e => e.key === "Enter" && askCopilot()} placeholder="Ask about the current reconciliation…" />
                <button onClick={() => askCopilot()} disabled={busy === "copilot"}>Ask</button>
              </div>
            </div>
          </section>
        )}

        {tab === "audit" && (
          <section className="panel auditPanel">
            <div className="panelHead"><div><h2>Audit trail</h2><small>System decisions, AI explanations and human review actions</small></div></div>
            <div className="auditList">
              {audit.map(a => <div className="auditRow" key={a.id}>
                <span className="auditTime">{a.created_at ? new Date(a.created_at).toLocaleString() : ""}</span>
                <b>{title(a.action)}</b><span>{a.actor}</span><p>{a.details}</p>
              </div>)}
            </div>
          </section>
        )}

        <footer>
          <span>LedgerIQ v3.0 · Deterministic money-critical matching + optional LLM reasoning</span>
          <span>Validation metrics are computed from the generated ground-truth labels.</span>
        </footer>
      </main>

      {selected && (
        <div className="drawerBackdrop" onClick={() => setSelected(null)}>
          <aside className="drawer" onClick={e => e.stopPropagation()}>
            <button className="close" onClick={() => setSelected(null)}>×</button>
            {selectedType === "transaction" ? (
              <>
                <div className="eyebrow">DECISION EVIDENCE</div>
                <h2>{selected.transaction.order_id || selected.transaction.gateway_id || selected.transaction.bank_id}</h2>
                <span className={`pill ${selected.transaction.status.toLowerCase()}`}>{title(selected.transaction.status)}</span>
                <div className="evidenceGrid">
                  <Evidence label="Order amount" value={money(selected.transaction.order_amount)} />
                  <Evidence label="Gateway amount" value={money(selected.transaction.gateway_amount)} />
                  <Evidence label="Bank amount" value={money(selected.transaction.bank_amount)} />
                  <Evidence label="Confidence" value={pct((selected.transaction.confidence || 0)*100)} />
                </div>
                <h3>Why this decision?</h3>
                <p>{selected.transaction.reason || "No explanation recorded."}</p>
                <div className="signals">{(selected.transaction.signals || []).map(s => <span key={s}>✓ {s}</span>)}</div>
                <h3>Audit trail</h3>
                <AuditMini items={selected.audit || []} />
              </>
            ) : (
              <>
                <div className="eyebrow">EXCEPTION INVESTIGATION</div>
                <h2>{title(selected.exception.exception_type)}</h2>
                <div className="drawerMeta">{selected.exception.order_id} · <b>{selected.exception.severity}</b> · priority {Math.round(selected.exception.priority_score)}</div>
                <div className="riskBox">₹{Number(selected.exception.amount_at_risk || 0).toLocaleString("en-IN", {maximumFractionDigits:2})}<small>amount at risk</small></div>
                <div className="evidenceGrid">
                  <Evidence label="Expected" value={money(selected.exception.expected_amount)} />
                  <Evidence label="Actual" value={money(selected.exception.actual_amount)} />
                  <Evidence label="Difference" value={money(selected.exception.difference)} />
                  <Evidence label="Confidence" value={pct((selected.exception.confidence || 0)*100)} />
                </div>
                <h3>System explanation</h3>
                <p>{selected.exception.explanation}</p>
                <h3>Recommended action</h3>
                <p>{selected.exception.recommended_action}</p>
                <div className="drawerButtons">
                  <button className="button secondary" onClick={() => explainException(selected.exception.id)} disabled={busy === "ai"}>✦ {busy === "ai" ? "Thinking…" : "AI explain"}</button>
                  <button className="button success" onClick={() => review(selected.exception.id, "APPROVED")}>Approve</button>
                  <button className="button danger" onClick={() => review(selected.exception.id, "REJECTED")}>Reject</button>
                  <button className="button ghost" onClick={() => review(selected.exception.id, "OPEN")}>Re-open</button>
                </div>
                {selected.ai && <div className="aiResult"><b>{selected.ai.provider}</b><p>{selected.ai.answer}</p><strong>Recommended: </strong>{selected.ai.recommended_action}</div>}
                <h3>Audit trail</h3>
                <AuditMini items={selected.audit || []} />
              </>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}

function Metric({label, value, tone=""}) {
  return <div className="metric"><span className={`metricDot ${tone}`}></span><small>{label}</small><strong>{value}</strong></div>;
}
function Evidence({label,value}) { return <div className="evidence"><span>{label}</span><b>{value}</b></div>; }
function AuditMini({items}) {
  return <div className="auditMini">{items.map((a,i)=><div key={i}><b>{title(a.action)}</b><span>{a.actor}</span><p>{a.details}</p><small>{a.created_at ? new Date(a.created_at).toLocaleString() : ""}</small></div>)}</div>;
}

createRoot(document.getElementById("root")).render(<App />);
