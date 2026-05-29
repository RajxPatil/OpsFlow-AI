"use client";

import { useState } from "react";
import { api } from "./shared/api";

export default function Home() {
  const [email, setEmail] = useState("demo@opsflow.ai");
  const [password, setPassword] = useState("demo123");
  const [error, setError] = useState("");

  async function login() {
    setError("");
    try {
      const data = await api.login(email, password);
      localStorage.setItem("opsflow_token", data.access_token);
      window.location.href = "/dashboard";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 text-white">
      <section className="mx-auto flex min-h-screen max-w-6xl items-center px-6 py-12">
        <div className="grid w-full gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <div>
            <p className="mb-4 inline-flex rounded-full border border-cyan-300/30 bg-cyan-300/10 px-4 py-2 text-sm text-cyan-100">
              FDE-style AI workflow automation · Human-in-the-loop · Audit ready
            </p>
            <h1 className="text-5xl font-semibold tracking-tight md:text-7xl">
              OpsFlow AI
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
              Upload messy support tickets and operational data. Let the AI classify issues, propose actions, draft replies, and explain every recommendation. Humans approve before anything executes.
            </p>
            <div className="mt-8 grid max-w-2xl gap-4 sm:grid-cols-3">
              {[
                ["Approval workflow", "Every AI action requires review"],
                ["Audit logs", "Trace uploads, decisions, and outcomes"],
                ["Metrics", "Track automation and time saved"],
              ].map(([title, body]) => (
                <div key={title} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <h3 className="font-semibold">{title}</h3>
                  <p className="mt-2 text-sm text-slate-300">{body}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-3xl bg-white p-6 text-slate-900 shadow-soft">
            <h2 className="text-2xl font-semibold">Demo login</h2>
            <p className="mt-2 text-sm text-slate-500">Use the seeded recruiter demo workspace.</p>
            <label className="mt-6 block text-sm font-medium">Email</label>
            <input className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 outline-none focus:border-slate-900" value={email} onChange={(e) => setEmail(e.target.value)} />
            <label className="mt-4 block text-sm font-medium">Password</label>
            <input className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 outline-none focus:border-slate-900" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
            <button onClick={login} className="mt-6 w-full rounded-xl bg-slate-950 px-4 py-3 font-semibold text-white hover:bg-slate-800">
              Enter demo workspace
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
