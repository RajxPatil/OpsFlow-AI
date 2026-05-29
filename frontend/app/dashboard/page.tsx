"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type React from "react";
import {
  api,
  AuditLog,
  Connector,
  IngestionJob,
  Metrics,
  SuggestedAction,
  SuggestedActionDetail,
  WorkItem,
  SystemStatus,
  SearchResult,
} from "../shared/api";

type ActionFilter = "all" | "high-confidence" | "slack" | "gmail" | "jira" | "github";

export default function Dashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [workItems, setWorkItems] = useState<WorkItem[]>([]);
  const [actions, setActions] = useState<SuggestedAction[]>([]);
  const [audit, setAudit] = useState<AuditLog[]>([]);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [selectedAction, setSelectedAction] = useState<SuggestedActionDetail | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [evidenceDrawerOpen, setEvidenceDrawerOpen] = useState(false);
  const [actionFilter, setActionFilter] = useState<ActionFilter>("all");
  const [search, setSearch] = useState("");
  const [semanticQuery, setSemanticQuery] = useState("");
  const [semanticResults, setSemanticResults] = useState<SearchResult[]>([]);
  const [semanticSearchLoading, setSemanticSearchLoading] = useState(false);
  const [semanticMessage, setSemanticMessage] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function refresh() {

    const [m, w, a, l, j, c, s] = await Promise.all([
      api.metrics(),
      api.workItems(),
      api.actions(),
      api.audit(),
      api.jobs(),
      api.connectors(),
      api.systemStatus(),
    ]);

    setMetrics(m);
    setWorkItems(w);
    setActions(a);
    setAudit(l);
    setJobs(j);
    setConnectors(c);
    setSystemStatus(s);
  }

  useEffect(() => {
    refresh().catch(() => {
      window.location.href = "/";
    });

    const timer = setInterval(() => refresh().catch(() => undefined), 5000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setEvidenceDrawerOpen(false);
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, []);

  const pendingActions = useMemo(() => actions.filter((a) => a.status === "pending"), [actions]);

  const reviewedActions = useMemo(
    () => actions.filter((a) => a.status === "approved" || a.status === "rejected"),
    [actions]
  );

  const filteredPendingActions = useMemo(() => {
    let list = pendingActions;

    if (actionFilter === "high-confidence") {
      list = list.filter((a) => a.confidence >= 0.8);
    } else if (actionFilter !== "all") {
      list = list.filter((a) => a.action_type.toLowerCase().includes(actionFilter));
    }

    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (a) =>
          a.title.toLowerCase().includes(q) ||
          a.explanation.toLowerCase().includes(q) ||
          a.action_type.toLowerCase().includes(q)
      );
    }

    return [...list].sort((a, b) => b.confidence - a.confidence);
  }, [pendingActions, actionFilter, search]);

  const highRisk = useMemo(() => workItems.filter((w) => w.risk_score >= 0.65), [workItems]);
  const latestJob = jobs[0];

  const demoProgress = useMemo(() => {
    const steps = [
      { label: "Data ingested", done: jobs.length > 0 },
      { label: "Worker processed", done: jobs.some((j) => j.status === "completed") },
      { label: "AI actions proposed", done: pendingActions.length > 0 || reviewedActions.length > 0 },
      { label: "Decision logged", done: reviewedActions.length > 0 },
    ];

    return steps;
  }, [jobs, pendingActions.length, reviewedActions.length]);

  async function upload(file?: File) {
    if (!file) return;

    setLoading(true);
    setMessage("");

    try {
      const result = await api.uploadCsv(file);

      setMessage(
        `Queued ${result.row_count} rows for ingestion. Worker is processing them in the background.`
      );

      await refresh();

      setTimeout(async () => {
        await refresh();
        setMessage(
          "Ingestion completed. AI recommendations are ready below in Pending AI-suggested actions."
        );

        document
          .getElementById("pending-actions")
          ?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 2500);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function generate() {
    setLoading(true);
    setMessage("");

    try {
      const result = await api.generateActions();
      await refresh();

      if (result.generated_actions === 0) {
        setMessage(
          "No new actions generated. Existing AI recommendations are already available in Pending AI-suggested actions."
        );
      } else {
        setMessage(`Generated ${result.generated_actions} new AI-suggested actions.`);
      }

      document
        .getElementById("pending-actions")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  }

  async function runSemanticSearch(queryOverride?: string) {
    const query = (queryOverride ?? semanticQuery).trim();

    if (query.length < 2) {
      setSemanticMessage("Enter at least 2 characters to search operational records.");
      return;
    }

    setSemanticSearchLoading(true);
    setSemanticMessage("");

    try {
      const results = await api.searchWorkItems(query, 8);
      setSemanticQuery(query);
      setSemanticResults(results);
      setSemanticMessage(
        results.length > 0
          ? `Found ${results.length} semantically related work item${results.length === 1 ? "" : "s"}.`
          : "No matching operational records found. Upload demo data first or try another query."
      );
    } catch (err) {
      setSemanticMessage(err instanceof Error ? err.message : "Semantic search failed");
    } finally {
      setSemanticSearchLoading(false);
    }
  }

  async function findSimilarWorkItems(item: WorkItem) {
    setSemanticSearchLoading(true);
    setSemanticMessage("");

    try {
      const results = await api.similarWorkItems(item.id, 5);
      setSemanticQuery(`Similar to: ${item.title}`);
      setSemanticResults(results);
      setSemanticMessage(
        results.length > 0
          ? `Found ${results.length} tickets similar to “${item.title}”.`
          : "No similar tickets found yet. Upload more data for better retrieval."
      );

      document
        .getElementById("semantic-search")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      setSemanticMessage(err instanceof Error ? err.message : "Similar-ticket retrieval failed");
    } finally {
      setSemanticSearchLoading(false);
    }
  }

  async function resetDemo() {
    const confirmed = window.confirm(
      "Reset the demo workspace? This clears uploaded tickets, AI actions, jobs, integrations, and audit logs."
    );
  
    if (!confirmed) return;
  
    setLoading(true);
    setMessage("");
  
    try {
      const result = await api.resetDemo();
      setSelectedAction(null);
      setEvidenceDrawerOpen(false);
      setActionFilter("all");
      setSearch("");
      setSemanticQuery("");
      setSemanticResults([]);
      setSemanticMessage("");
      setMessage(result.message);
      await refresh();
  
      document
        .getElementById("overview")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Demo reset failed");
    } finally {
      setLoading(false);
    }
  }

  async function review(id: string, decision: "approve" | "reject") {
    setLoading(true);

    try {
      if (decision === "approve") await api.approveAction(id);
      else await api.rejectAction(id);

      setSelectedAction(null);
      setEvidenceDrawerOpen(false);
      await refresh();

      setMessage(
        decision === "approve"
          ? "Action approved. Mock connector execution was recorded in the audit trail."
          : "Action rejected. Decision recorded for compliance and model feedback."
      );
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Review failed");
    } finally {
      setLoading(false);
    }
  }

  async function inspect(action: SuggestedAction) {
    const detail = await api.actionDetail(action.id);
    setSelectedAction(detail);
    setEvidenceDrawerOpen(true);
  }

  function logout() {
    localStorage.removeItem("opsflow_token");
    window.location.href = "/";
  }

  return (
    <main className="min-h-screen bg-[#f5f7fb] text-slate-950">
      <div className="grid min-h-screen lg:grid-cols-[292px_1fr]">
        <aside className="sticky top-0 hidden h-screen overflow-y-auto border-r border-white/10 bg-[#060816] p-6 text-white lg:block">
          <div className="rounded-[2rem] border border-white/10 bg-white/[0.07] p-5 shadow-2xl shadow-cyan-950/20">
            <div className="flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-2xl bg-cyan-400 text-sm font-black text-slate-950">
                O
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-cyan-200">OpsFlow AI</p>
                <p className="text-sm text-slate-400">Demo workspace</p>
              </div>
            </div>

            <h1 className="mt-6 text-2xl font-semibold tracking-tight">Command Center</h1>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Human-approved AI actions for messy ops workflows.
            </p>
          </div>

          <nav className="mt-8 space-y-2 text-sm">
            {[
              ["Overview", "overview"],
              ["Demo Flow", "demo-flow"],
              ["Ingestion Jobs", "ingestion-jobs"],
              ["Semantic Search", "semantic-search"],
              ["Pending Actions", "pending-actions"],
              ["Connectors", "connectors"],
              ["Audit Trail", "audit-trail"],
            ].map(([item, id]) => (
              <a
                key={item}
                href={`#${id}`}
                className="group flex items-center justify-between rounded-2xl px-4 py-3 text-slate-300 transition hover:bg-white/10 hover:text-white"
              >
                <span>{item}</span>
                <span className="text-slate-600 transition group-hover:translate-x-1 group-hover:text-cyan-200">
                  →
                </span>
              </a>
            ))}
          </nav>

          <div className="mt-8 rounded-3xl border border-cyan-400/20 bg-cyan-400/10 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-200">
              Workflow guardrails
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Ingest data → generate AI actions → inspect evidence → approve safely → preserve audit history.
            </p>
          </div>

          <button
            onClick={logout}
            className="mt-8 w-full rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
          >
            Logout
          </button>
        </aside>

        <section className="relative overflow-hidden px-5 py-6 md:px-8 lg:px-10">
          <div className="pointer-events-none absolute left-1/2 top-0 h-80 w-80 -translate-x-1/2 rounded-full bg-cyan-200/30 blur-3xl" />
          <div className="pointer-events-none absolute right-8 top-24 h-72 w-72 rounded-full bg-indigo-200/30 blur-3xl" />

          <header className="relative z-10 flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-white/80 px-3 py-1 text-xs font-semibold text-cyan-800 shadow-sm">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                Demo Ops Workspace · human-in-the-loop automation
              </div>

              <h2 className="mt-4 max-w-4xl text-4xl font-black tracking-tight text-slate-950 md:text-5xl">
                AI Workflow Automation Platform
              </h2>

              <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600">
                Upload operational data, queue background ingestion, inspect AI recommendations
                with evidence, and approve connector actions before execution.
              </p>

              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={loading}
                  className="rounded-2xl bg-slate-950 px-5 py-3 text-sm font-bold text-white shadow-xl shadow-slate-300 transition hover:-translate-y-0.5 hover:bg-slate-800 disabled:opacity-60"
                >
                  Upload CSV Demo Data
                </button>

                <button
                  onClick={() =>
                    document
                      .getElementById("pending-actions")
                      ?.scrollIntoView({ behavior: "smooth", block: "start" })
                  }
                  className="rounded-2xl border border-slate-200 bg-white px-5 py-3 text-sm font-bold text-slate-900 shadow-sm transition hover:-translate-y-0.5 hover:border-cyan-300 hover:text-cyan-800"
                >
                  Review {pendingActions.length} AI Actions
                </button>

                <button
                  onClick={resetDemo}
                  disabled={loading}
                  className="rounded-2xl border border-rose-200 bg-white px-5 py-3 text-sm font-bold text-rose-700 shadow-sm transition hover:-translate-y-0.5 hover:bg-rose-50 disabled:opacity-60"
                >
                  Reset Demo
                </button>

                <input
                  ref={fileInputRef}
                  className="hidden"
                  type="file"
                  accept=".csv"
                  onChange={(e) => upload(e.target.files?.[0])}
                />
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 xl:w-[640px]">
              <StatusCard
                label="Latest job"
                value={latestJob ? latestJob.status : "No jobs yet"}
                hint={
                  latestJob
                    ? `${latestJob.filename} · ${latestJob.row_count} rows`
                    : "Upload demo_tickets.csv"
                }
                tone={latestJob?.status === "completed" ? "green" : "blue"}
              />

              <StatusCard
                label="Approval queue"
                value={`${pendingActions.length} pending`}
                hint={`${reviewedActions.length} reviewed actions`}
                tone={pendingActions.length > 0 ? "amber" : "green"}
              />

              <StatusCard
                label="AI mode"
                value={systemStatus?.ai_provider ?? "mock"}
                hint={`DB ${systemStatus?.database ?? "-"} · Redis ${systemStatus?.redis ?? "-"}`}
                tone="blue"
              />
            </div>
          </header>

          {message && (
            <div className="relative z-10 mt-6 flex items-start gap-3 rounded-3xl border border-cyan-200 bg-cyan-50/90 px-5 py-4 text-sm text-cyan-950 shadow-sm">
              <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-cyan-600 text-xs font-bold text-white">
                i
              </span>
              <p className="leading-6">{message}</p>
            </div>
          )}

          <section id="overview" className="relative z-10 mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <MetricCard
              label="Work items"
              value={metrics?.total_work_items ?? 0}
              hint="Operational records"
              accent="cyan"
            />
            <MetricCard
              label="Pending approval"
              value={metrics?.pending_actions ?? 0}
              hint="Human-in-loop"
              accent="amber"
            />
            <MetricCard
              label="High risk"
              value={metrics?.high_risk_items ?? 0}
              hint="Risk score ≥ 65%"
              accent="rose"
            />
            <MetricCard
              label="Approval rate"
              value={`${Math.round((metrics?.approval_rate ?? 0) * 100)}%`}
              hint="Approved / reviewed"
              accent="emerald"
            />
            <MetricCard
              label="Minutes saved"
              value={metrics?.estimated_minutes_saved ?? 0}
              hint="Estimated automation ROI"
              accent="violet"
            />
          </section>

          <section id="demo-flow" className="relative z-10 mt-6 rounded-[2rem] border border-slate-200 bg-white/90 p-5 shadow-xl shadow-slate-200/60 backdrop-blur">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-cyan-700">
                  Workflow lifecycle
                </p>
                <h3 className="mt-1 text-xl font-bold tracking-tight">Track operational data from ingestion to approved execution</h3>
              </div>

              <div className="grid gap-3 md:grid-cols-4 xl:min-w-[720px]">
                {demoProgress.map((step, index) => (
                  <div
                    key={step.label}
                    className={`rounded-2xl border px-4 py-3 ${
                      step.done
                        ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                        : "border-slate-200 bg-slate-50 text-slate-500"
                    }`}
                  >
                    <p className="text-xs font-bold uppercase tracking-wide">Step {index + 1}</p>
                    <p className="mt-1 text-sm font-semibold">{step.label}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="relative z-10 mt-6 grid gap-6 xl:grid-cols-[1.12fr_0.88fr]">
            <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-xl shadow-slate-200/60">
              <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.22em] text-slate-400">
                    Async ingestion pipeline
                  </p>
                  <h3 className="mt-1 text-2xl font-bold tracking-tight">Ingest operational data</h3>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                    CSV upload is queued in Redis and processed by the worker:
                    queued → processing → completed. Actions are generated after ingestion.
                  </p>
                </div>

                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={loading}
                    className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm font-bold text-slate-900 transition hover:bg-slate-100 disabled:opacity-60"
                  >
                    Upload CSV
                  </button>

                  <button
                    onClick={generate}
                    disabled={loading}
                    className="rounded-2xl bg-slate-950 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-slate-800 disabled:opacity-60"
                  >
                    Generate Actions
                  </button>
                </div>
              </div>

              <div id="ingestion-jobs" className="mt-6 grid gap-3 md:grid-cols-2">
                {jobs.length === 0 && (
                  <EmptyState
                    title="No ingestion jobs yet"
                    text="Upload sample_data/demo_tickets.csv to trigger the background worker."
                  />
                )}

                {jobs.slice(0, 4).map((job) => (
                  <JobCard key={job.id} job={job} />
                ))}
              </div>
            </div>

            <div id="connectors" className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-xl shadow-slate-200/60">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.22em] text-slate-400">
                    FDE-style integrations
                  </p>
                  <h3 className="mt-1 text-2xl font-bold tracking-tight">Mock connectors</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    Demonstrates workflow automation without requiring private Slack/Gmail/Jira credentials.
                  </p>
                </div>
                <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">
                  mock live
                </span>
              </div>

              <div className="mt-5 space-y-3">
                {connectors.map((connector) => (
                  <ConnectorCard key={connector.id} connector={connector} />
                ))}
              </div>
            </div>
          </section>

          <section id="semantic-search" className="relative z-10 mt-6 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-xl shadow-slate-200/60">
            <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-violet-700">
                  Semantic ops search
                </p>
                <h3 className="mt-1 text-2xl font-bold tracking-tight">Find similar operational records</h3>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                  Search across ingested tickets using stored embeddings and lightweight lexical boosting.
                  This makes the project behave like an AI retrieval system, not just an action dashboard.
                </p>
              </div>

              <div className="rounded-3xl border border-violet-200 bg-violet-50 px-5 py-4 text-violet-950">
                <p className="text-xs font-bold uppercase tracking-wide">Retrieval corpus</p>
                <p className="mt-1 text-3xl font-black">{workItems.length}</p>
                <p className="mt-1 text-xs font-medium text-violet-700">work items indexed</p>
              </div>
            </div>

            <form
              className="mt-6 flex flex-col gap-3 lg:flex-row"
              onSubmit={(event) => {
                event.preventDefault();
                runSemanticSearch();
              }}
            >
              <input
                value={semanticQuery}
                onChange={(event) => setSemanticQuery(event.target.value)}
                placeholder="Search tickets: refund payment failed, outage, delivery delay..."
                className="min-h-[50px] flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition placeholder:text-slate-400 focus:border-violet-300 focus:bg-white focus:ring-4 focus:ring-violet-100"
              />

              <button
                type="submit"
                disabled={semanticSearchLoading || semanticQuery.trim().length < 2}
                className="rounded-2xl bg-slate-950 px-5 py-3 text-sm font-bold text-white transition hover:bg-slate-800 disabled:opacity-60"
              >
                {semanticSearchLoading ? "Searching..." : "Search records"}
              </button>
            </form>

            <div className="mt-4 flex flex-wrap gap-2">
              {["refund payment failed", "urgent outage", "delivery delay", "login OTP error"].map((query) => (
                <button
                  key={query}
                  onClick={() => runSemanticSearch(query)}
                  disabled={semanticSearchLoading}
                  className="rounded-full bg-slate-100 px-3 py-2 text-xs font-bold text-slate-600 transition hover:bg-violet-50 hover:text-violet-800 disabled:opacity-60"
                >
                  {query}
                </button>
              ))}
            </div>

            {semanticMessage && (
              <div className="mt-5 rounded-3xl border border-violet-200 bg-violet-50 px-5 py-4 text-sm font-semibold text-violet-900">
                {semanticMessage}
              </div>
            )}

            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              {semanticResults.length === 0 && (
                <EmptyState
                  title="No semantic results yet"
                  text="Upload demo data, then search for phrases like refund payment failed, outage, delivery delay, or login issue."
                />
              )}

              {semanticResults.map((result) => (
                <SearchResultCard
                  key={result.work_item.id}
                  result={result}
                  loading={semanticSearchLoading}
                  onFindSimilar={() => findSimilarWorkItems(result.work_item)}
                />
              ))}
            </div>
          </section>

          <section id="pending-actions" className="relative z-10 mt-6 grid gap-6">
            <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-xl shadow-slate-200/60">
              <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.22em] text-cyan-700">
                    Human approval queue
                  </p>
                  <h3 className="mt-1 text-2xl font-bold tracking-tight">
                    Pending AI-suggested actions
                  </h3>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                    Each recommendation includes confidence, explanation, payload, source evidence,
                    and simulated connector execution before approval.
                  </p>
                </div>

                <div className="rounded-3xl border border-amber-200 bg-amber-50 px-5 py-4 text-amber-950">
                  <p className="text-xs font-bold uppercase tracking-wide">Needs review</p>
                  <p className="mt-1 text-3xl font-black">{pendingActions.length}</p>
                </div>
              </div>

              <div className="mt-6 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div className="flex flex-wrap gap-2">
                  {[
                    ["all", "All"],
                    ["high-confidence", "High confidence"],
                    ["slack", "Slack"],
                    ["gmail", "Gmail"],
                    ["jira", "Jira"],
                    ["github", "GitHub"],
                  ].map(([value, label]) => (
                    <button
                      key={value}
                      onClick={() => setActionFilter(value as ActionFilter)}
                      className={`rounded-full px-3 py-2 text-xs font-bold transition ${
                        actionFilter === value
                          ? "bg-slate-950 text-white"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search actions..."
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm outline-none transition placeholder:text-slate-400 focus:border-cyan-300 focus:bg-white focus:ring-4 focus:ring-cyan-100 xl:w-72"
                />
              </div>

              <div className="mt-5 space-y-4">
                {filteredPendingActions.length === 0 && (
                  <EmptyState
                    title="No matching pending actions"
                    text="Upload CSV data, wait for the worker, or clear the current filter."
                  />
                )}

                {filteredPendingActions.map((action) => (
                  <ActionCard
                    key={action.id}
                    action={action}
                    loading={loading}
                    onInspect={() => inspect(action)}
                    onApprove={() => review(action.id, "approve")}
                    onReject={() => review(action.id, "reject")}
                  />
                ))}
              </div>
            </div>

            <div
              id="evidence-panel"
              className="hidden"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.22em] text-cyan-200">
                    Explainability layer
                  </p>
                  <h3 className="mt-1 text-2xl font-bold tracking-tight">Action evidence panel</h3>
                </div>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-bold text-slate-300">
                  audit-ready
                </span>
              </div>

              {!selectedAction && (
                <div className="mt-5 rounded-3xl border border-white/10 bg-white/[0.04] p-5">
                  <p className="text-sm leading-6 text-slate-300">
                    Click <span className="font-semibold text-white">Inspect</span> on any pending action
                    to show source evidence, model reasoning, execution payload, and simulated connector records.
                  </p>

                  <div className="mt-5 grid gap-3">
                    {["Source ticket", "AI reasoning", "Execution payload", "Mock connector result"].map(
                      (item) => (
                        <div key={item} className="rounded-2xl bg-white/[0.04] px-4 py-3 text-sm text-slate-300">
                          {item}
                        </div>
                      )
                    )}
                  </div>
                </div>
              )}

              {selectedAction && (
                <div className="mt-5 space-y-4">
                  <div className="rounded-3xl border border-cyan-400/20 bg-cyan-400/10 p-5">
                    <p className="text-xs font-bold uppercase tracking-wide text-cyan-200">
                      {formatType(selectedAction.action_type)}
                    </p>
                    <h4 className="mt-2 text-lg font-bold">{selectedAction.title}</h4>
                    <p className="mt-2 text-sm leading-6 text-slate-300">
                      {selectedAction.explanation}
                    </p>
                  </div>

                  <Panel title="Source evidence">
                    {selectedAction.evidence.map((e, idx) => (
                      <p key={idx} className="rounded-2xl bg-white/[0.04] p-3 text-sm leading-6 text-slate-300">
                        {e.content}
                      </p>
                    ))}
                  </Panel>

                  <Panel title="Execution payload">
                    <pre className="max-h-56 overflow-auto rounded-2xl bg-black/30 p-3 text-xs leading-5 text-slate-200">
                      {JSON.stringify(selectedAction.payload, null, 2)}
                    </pre>
                  </Panel>

                  <Panel title="Simulated integrations">
                    <pre className="max-h-56 overflow-auto rounded-2xl bg-black/30 p-3 text-xs leading-5 text-slate-200">
                      {JSON.stringify(selectedAction.simulated_integrations, null, 2)}
                    </pre>
                  </Panel>
                </div>
              )}
            </div>
          </section>

          <section className="relative z-10 mt-6 grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
            <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-xl shadow-slate-200/60">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.22em] text-rose-700">
                    Priority queue
                  </p>
                  <h3 className="mt-1 text-2xl font-bold tracking-tight">High-risk work items</h3>
                </div>
                <span className="rounded-full bg-rose-50 px-3 py-1 text-xs font-bold text-rose-700">
                  {highRisk.length} high risk
                </span>
              </div>

              <div className="mt-5 max-h-[560px] space-y-3 overflow-auto pr-2">
                {highRisk.length === 0 && (
                  <EmptyState title="No high-risk items yet" text="Risk score ≥ 65% will appear here." />
                )}

                {highRisk.map((item) => (
                  <WorkItemCard key={item.id} item={item} />
                ))}
              </div>
            </div>

            <div id="audit-trail" className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-xl shadow-slate-200/60">
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.22em] text-slate-400">
                    Compliance trail
                  </p>
                  <h3 className="mt-1 text-2xl font-bold tracking-tight">Audit timeline</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    Every upload, generated recommendation, approval, rejection, and mock integration event is recorded.
                  </p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">
                  {audit.length} events
                </span>
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {audit.length === 0 && (
                  <EmptyState title="Audit log is empty" text="Approve or reject actions to populate the timeline." />
                )}

                {audit.slice(0, 12).map((log) => (
                  <AuditCard key={log.id} log={log} />
                ))}
              </div>
            </div>
          </section>
        </section>
      </div>

      {evidenceDrawerOpen && selectedAction && (
        <EvidenceDrawer
          action={selectedAction}
          onClose={() => setEvidenceDrawerOpen(false)}
        />
      )}
    </main>
  );
}


function EvidenceDrawer({
  action,
  onClose,
}: {
  action: SuggestedActionDetail;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 bg-slate-950/60 px-3 py-4 backdrop-blur-sm md:px-6 md:py-6">
      <div className="ml-auto flex h-full w-full max-w-5xl flex-col overflow-hidden rounded-[2rem] border border-white/10 bg-[#070a18] text-white shadow-2xl shadow-slate-950/50">
        <div className="flex items-start justify-between gap-4 border-b border-white/10 px-5 py-5 md:px-7">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.22em] text-cyan-200">
              Action evidence panel
            </p>
            <h3 className="mt-2 text-2xl font-bold tracking-tight">{action.title}</h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
              Review source evidence, model reasoning, execution payload, and simulated connector records before approval.
            </p>
          </div>

          <button
            onClick={onClose}
            className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-bold text-white transition hover:bg-white/10"
          >
            Close
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-5 md:p-7">
          <div className="grid gap-5 xl:grid-cols-[0.92fr_1.08fr]">
            <div className="space-y-5">
              <div className="rounded-3xl border border-cyan-400/20 bg-cyan-400/10 p-5">
                <p className="text-xs font-bold uppercase tracking-wide text-cyan-200">
                  {formatType(action.action_type)}
                </p>
                <h4 className="mt-2 text-xl font-bold">Model recommendation</h4>
                <p className="mt-3 text-sm leading-7 text-slate-300">{action.explanation}</p>
              </div>

              <Panel title="Source evidence">
                {action.evidence.length === 0 && (
                  <p className="rounded-2xl bg-white/[0.04] p-3 text-sm leading-6 text-slate-300">
                    No evidence chunks were attached to this action.
                  </p>
                )}

                {action.evidence.map((e, idx) => (
                  <p key={idx} className="rounded-2xl bg-white/[0.04] p-4 text-sm leading-7 text-slate-300">
                    {e.content}
                  </p>
                ))}
              </Panel>
            </div>

            <div className="space-y-5">
              <Panel title="Execution payload">
                <pre className="max-h-[360px] overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-black/30 p-4 text-xs leading-6 text-slate-200">
                  {JSON.stringify(action.payload, null, 2)}
                </pre>
              </Panel>

              <Panel title="Simulated integrations">
                <pre className="max-h-[360px] overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-black/30 p-4 text-xs leading-6 text-slate-200">
                  {JSON.stringify(action.simulated_integrations, null, 2)}
                </pre>
              </Panel>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string | number;
  hint: string;
  accent: "cyan" | "amber" | "rose" | "emerald" | "violet";
}) {
  const accentMap = {
    cyan: "from-cyan-50 to-white text-cyan-700",
    amber: "from-amber-50 to-white text-amber-700",
    rose: "from-rose-50 to-white text-rose-700",
    emerald: "from-emerald-50 to-white text-emerald-700",
    violet: "from-violet-50 to-white text-violet-700",
  };

  return (
    <div className="group rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-xl shadow-slate-200/60 transition hover:-translate-y-1 hover:shadow-2xl">
      <div className={`mb-4 h-1.5 w-16 rounded-full bg-gradient-to-r ${accentMap[accent]}`} />
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <p className="mt-2 text-4xl font-black tracking-tight text-slate-950">{value}</p>
      <p className="mt-1 text-xs font-medium text-slate-400">{hint}</p>
    </div>
  );
}

function StatusCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint: string;
  tone: "green" | "blue" | "amber";
}) {
  const toneMap = {
    green: "bg-emerald-50 text-emerald-700 border-emerald-200",
    blue: "bg-cyan-50 text-cyan-700 border-cyan-200",
    amber: "bg-amber-50 text-amber-700 border-amber-200",
  };

  return (
    <div className="rounded-[1.75rem] border border-slate-200 bg-white/90 p-5 shadow-xl shadow-slate-200/60 backdrop-blur">
      <p className="text-xs font-bold uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-2 text-xl font-black capitalize text-slate-950">{value}</p>
      <p className="mt-1 text-xs leading-5 text-slate-500">{hint}</p>
      <div className={`mt-4 inline-flex rounded-full border px-3 py-1 text-xs font-bold ${toneMap[tone]}`}>
        live
      </div>
    </div>
  );
}

function EmptyState({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50/70 p-7 text-center">
      <div className="mx-auto grid h-11 w-11 place-items-center rounded-2xl bg-white text-xl shadow-sm">↯</div>
      <p className="mt-3 font-bold text-slate-800">{title}</p>
      <p className="mt-1 text-sm leading-6 text-slate-500">{text}</p>
    </div>
  );
}

function JobCard({ job }: { job: IngestionJob }) {
  const pct =
    job.status === "completed" ? 100 : job.status === "processing" ? 60 : job.status === "failed" ? 100 : 20;

  const statusClass =
    job.status === "completed"
      ? "bg-emerald-50 text-emerald-700"
      : job.status === "processing"
      ? "bg-cyan-50 text-cyan-700"
      : job.status === "failed"
      ? "bg-rose-50 text-rose-700"
      : "bg-amber-50 text-amber-700";

  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-cyan-200 hover:shadow-lg">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-bold text-slate-950">{job.filename}</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            {job.row_count} rows · {job.inserted_work_items} inserted · {job.generated_actions} actions
          </p>
        </div>

        <span className={`rounded-full px-3 py-1 text-xs font-bold capitalize ${statusClass}`}>
          {job.status}
        </span>
      </div>

      <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-cyan-600 transition-all duration-700" style={{ width: `${pct}%` }} />
      </div>

      {job.error_message && <p className="mt-3 text-xs font-medium text-rose-600">{job.error_message}</p>}
    </div>
  );
}

function ConnectorCard({ connector }: { connector: Connector }) {
  const icon = connector.name.toLowerCase().includes("slack")
    ? "#"
    : connector.name.toLowerCase().includes("gmail")
    ? "@"
    : connector.name.toLowerCase().includes("jira")
    ? "J"
    : "G";

  return (
    <div className="rounded-3xl border border-slate-200 p-4 transition hover:border-cyan-200 hover:bg-slate-50">
      <div className="flex items-start gap-4">
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-slate-950 text-sm font-black text-white">
          {icon}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <p className="font-bold text-slate-950">{connector.name}</p>
            <span className="shrink-0 rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">
              {connector.status.replaceAll("_", " ")}
            </span>
          </div>

          <p className="mt-1 text-sm leading-6 text-slate-500">{connector.description}</p>
          <p className="mt-3 text-xs font-medium text-slate-400">
            {connector.records} records · last sync {connector.last_sync}
          </p>
        </div>
      </div>
    </div>
  );
}

function ActionCard({
  action,
  loading,
  onInspect,
  onApprove,
  onReject,
}: {
  action: SuggestedAction;
  loading: boolean;
  onInspect: () => void;
  onApprove: () => void;
  onReject: () => void;
}) {
  const accent = getActionAccent(action.action_type);
  const confidence = Math.round(action.confidence * 100);

  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-cyan-200 hover:shadow-xl">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-3 py-1 text-xs font-black ${accent.badge}`}>
              {formatType(action.action_type)}
            </span>

            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">
              {confidence}% confidence
            </span>
          </div>

          <h4 className="mt-3 text-lg font-bold tracking-tight text-slate-950">{action.title}</h4>
          <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-600">{action.explanation}</p>
        </div>

        <div className="flex shrink-0 flex-wrap gap-2">
          <button
            onClick={onInspect}
            className="rounded-xl bg-slate-100 px-3 py-2 text-xs font-bold text-slate-800 transition hover:bg-slate-200"
          >
            Inspect
          </button>

          <button
            onClick={onApprove}
            disabled={loading}
            className="rounded-xl bg-emerald-600 px-3 py-2 text-xs font-bold text-white transition hover:bg-emerald-700 disabled:opacity-60"
          >
            Approve
          </button>

          <button
            onClick={onReject}
            disabled={loading}
            className="rounded-xl bg-rose-600 px-3 py-2 text-xs font-bold text-white transition hover:bg-rose-700 disabled:opacity-60"
          >
            Reject
          </button>
        </div>
      </div>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${accent.bar}`} style={{ width: `${confidence}%` }} />
      </div>
    </div>
  );
}

function SearchResultCard({
  result,
  loading,
  onFindSimilar,
}: {
  result: SearchResult;
  loading: boolean;
  onFindSimilar: () => void;
}) {
  const item = result.work_item;
  const score = Math.round(result.similarity * 100);

  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-violet-200 hover:shadow-xl">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap gap-2 text-xs font-bold">
            <span className="rounded-full bg-violet-50 px-3 py-1 text-violet-800">
              {score}% similar
            </span>
            <span className="rounded-full bg-cyan-50 px-3 py-1 text-cyan-800">
              {item.priority}
            </span>
            {item.category && (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">
                {item.category}
              </span>
            )}
          </div>

          <h4 className="mt-3 text-lg font-bold tracking-tight text-slate-950">{item.title}</h4>
          <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">{item.body}</p>
        </div>

        <span className="shrink-0 rounded-full bg-rose-50 px-3 py-1 text-xs font-black text-rose-700">
          risk {Math.round(item.risk_score * 100)}%
        </span>
      </div>

      <div className="mt-4 rounded-2xl bg-slate-50 p-4">
        <p className="text-xs font-black uppercase tracking-wide text-slate-400">Matched content</p>
        <p className="mt-2 line-clamp-4 text-sm leading-6 text-slate-600">{result.matched_content}</p>
      </div>

      <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <p className="text-xs leading-5 text-slate-400">{result.reason}</p>
        <button
          onClick={onFindSimilar}
          disabled={loading}
          className="shrink-0 rounded-xl bg-slate-950 px-3 py-2 text-xs font-bold text-white transition hover:bg-slate-800 disabled:opacity-60"
        >
          Find similar
        </button>
      </div>
    </div>
  );
}

function WorkItemCard({ item }: { item: WorkItem }) {
  return (
    <div className="rounded-3xl border border-slate-200 p-5 transition hover:border-rose-200 hover:bg-rose-50/20">
      <div className="flex items-start justify-between gap-3">
        <h4 className="font-bold tracking-tight text-slate-950">{item.title}</h4>
        <span className="shrink-0 rounded-full bg-rose-50 px-3 py-1 text-xs font-black text-rose-700">
          {Math.round(item.risk_score * 100)}%
        </span>
      </div>

      <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">{item.body}</p>

      <div className="mt-4 flex flex-wrap gap-2 text-xs font-bold">
        <span className="rounded-full bg-cyan-50 px-3 py-1 text-cyan-800">{item.channel}</span>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">{item.status}</span>
        {item.category && (
          <span className="rounded-full bg-purple-50 px-3 py-1 text-purple-800">{item.category}</span>
        )}
      </div>
    </div>
  );
}

function AuditCard({ log }: { log: AuditLog }) {
  return (
    <div className="rounded-3xl border border-slate-200 p-4 transition hover:bg-slate-50">
      <p className="text-xs font-black uppercase tracking-wide text-slate-400">
        {log.event_type.replaceAll("_", " ")}
      </p>
      <p className="mt-2 text-sm leading-6 text-slate-700">{log.description}</p>
      <p className="mt-3 text-xs font-medium text-slate-400">{new Date(log.created_at).toLocaleString()}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.05] p-4">
      <p className="mb-3 text-xs font-black uppercase tracking-[0.18em] text-slate-400">{title}</p>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function formatType(value: string) {
  return value.replaceAll("_", " ");
}

function getActionAccent(actionType: string) {
  const type = actionType.toLowerCase();

  if (type.includes("slack")) {
    return {
      badge: "bg-violet-50 text-violet-700",
      bar: "bg-violet-500",
    };
  }

  if (type.includes("gmail") || type.includes("email")) {
    return {
      badge: "bg-rose-50 text-rose-700",
      bar: "bg-rose-500",
    };
  }

  if (type.includes("jira") || type.includes("ticket")) {
    return {
      badge: "bg-blue-50 text-blue-700",
      bar: "bg-blue-500",
    };
  }

  if (type.includes("github")) {
    return {
      badge: "bg-slate-100 text-slate-800",
      bar: "bg-slate-700",
    };
  }

  return {
    badge: "bg-cyan-50 text-cyan-700",
    bar: "bg-cyan-500",
  };
}
