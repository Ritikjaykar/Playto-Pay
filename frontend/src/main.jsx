import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { RefreshCcw, Send, WalletCards } from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

function rupees(paise) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format((paise || 0) / 100);
}

function uuid() {
  return crypto.randomUUID();
}

function App() {
  const [merchants, setMerchants] = useState([]);
  const [merchantId, setMerchantId] = useState("");
  const [summary, setSummary] = useState(null);
  const [amount, setAmount] = useState("");
  const [bankAccountId, setBankAccountId] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  async function loadMerchants() {
    const response = await fetch(`${API_BASE}/merchants`);
    const data = await response.json();
    setMerchants(data);
    if (!merchantId && data.length) setMerchantId(data[0].id);
  }

  async function loadSummary(activeMerchantId = merchantId) {
    if (!activeMerchantId) return;
    const response = await fetch(`${API_BASE}/summary`, { headers: { "X-Merchant-Id": activeMerchantId } });
    const data = await response.json();
    setSummary(data);
    setBankAccountId((current) => current || data.bank_accounts[0]?.id || "");
    setLoading(false);
  }

  useEffect(() => {
    loadMerchants();
  }, []);

  useEffect(() => {
    if (!merchantId) return;
    loadSummary(merchantId);
    const timer = setInterval(() => loadSummary(merchantId), 3000);
    return () => clearInterval(timer);
  }, [merchantId]);

  const sortedPayouts = useMemo(() => summary?.payouts || [], [summary]);

  async function requestPayout(event) {
    event.preventDefault();
    setMessage("");
    const amountPaise = Math.round(Number(amount) * 100);
    const response = await fetch(`${API_BASE}/payouts`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Merchant-Id": merchantId,
        "Idempotency-Key": uuid(),
      },
      body: JSON.stringify({ amount_paise: amountPaise, bank_account_id: bankAccountId }),
    });
    const data = await response.json();
    if (!response.ok) {
      setMessage(data.detail || "Payout request failed");
      return;
    }
    setAmount("");
    setMessage(`Payout ${data.id} created.`);
    loadSummary(merchantId);
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-5 py-6">
        <header className="flex flex-col gap-4 border-b border-ink/15 pb-5 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-normal">Playto Payout Engine</h1>
            <p className="mt-1 text-sm text-ink/65">Merchant balances, holds, and bank payout status.</p>
          </div>
          <div className="flex items-center gap-2">
            <select
              className="h-10 rounded border border-ink/20 bg-white px-3 text-sm"
              value={merchantId}
              onChange={(event) => {
                setLoading(true);
                setMerchantId(event.target.value);
                setBankAccountId("");
              }}
            >
              {merchants.map((merchant) => (
                <option key={merchant.id} value={merchant.id}>{merchant.name}</option>
              ))}
            </select>
            <button className="icon-button" onClick={() => loadSummary(merchantId)} title="Refresh">
              <RefreshCcw size={18} />
            </button>
          </div>
        </header>

        {loading || !summary ? (
          <div className="py-16 text-center text-ink/60">Loading dashboard...</div>
        ) : (
          <>
            <section className="grid gap-4 md:grid-cols-3">
              <BalanceTile label="Available" value={summary.balances.available} accent="mint" />
              <BalanceTile label="Held" value={summary.balances.held} accent="steel" />
              <BalanceTile label="Total" value={summary.balances.total} accent="coral" />
            </section>

            <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
              <form onSubmit={requestPayout} className="rounded border border-ink/15 bg-white p-4">
                <div className="mb-4 flex items-center gap-2">
                  <WalletCards size={20} />
                  <h2 className="text-lg font-semibold">Request payout</h2>
                </div>
                <label className="field-label">Amount in INR</label>
                <input
                  className="field"
                  type="number"
                  min="1"
                  step="0.01"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                  required
                />
                <label className="field-label mt-4">Bank account</label>
                <select className="field" value={bankAccountId} onChange={(event) => setBankAccountId(event.target.value)} required>
                  {summary.bank_accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.bank_name} {account.masked_account_number}
                    </option>
                  ))}
                </select>
                <button className="mt-5 flex h-10 w-full items-center justify-center gap-2 rounded bg-ink px-4 text-sm font-medium text-white" type="submit">
                  <Send size={16} />
                  Request
                </button>
                {message && <p className="mt-3 text-sm text-ink/70">{message}</p>}
              </form>

              <Panel title="Payout history">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[640px] text-left text-sm">
                    <thead className="border-b border-ink/10 text-ink/55">
                      <tr>
                        <th className="py-2">Payout</th>
                        <th>Amount</th>
                        <th>Status</th>
                        <th>Attempts</th>
                        <th>Bank</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedPayouts.map((payout) => (
                        <tr className="border-b border-ink/10" key={payout.id}>
                          <td className="py-3 font-mono text-xs">{payout.id.slice(0, 8)}</td>
                          <td>{rupees(payout.amount_paise)}</td>
                          <td><StatusBadge status={payout.status} /></td>
                          <td>{payout.attempts}</td>
                          <td>{payout.bank_account.bank_name}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
            </section>

            <Panel title="Recent ledger entries">
              <div className="grid gap-2">
                {summary.ledger_entries.map((entry) => (
                  <div className="grid gap-2 rounded border border-ink/10 px-3 py-2 text-sm md:grid-cols-[180px_1fr_140px_140px]" key={entry.id}>
                    <span className="font-medium">{entry.entry_type.replaceAll("_", " ")}</span>
                    <span className="text-ink/65">{entry.description}</span>
                    <span>{rupees(entry.available_delta_paise)} available</span>
                    <span>{rupees(entry.held_delta_paise)} held</span>
                  </div>
                ))}
              </div>
            </Panel>
          </>
        )}
      </div>
    </main>
  );
}

function BalanceTile({ label, value, accent }) {
  return (
    <div className={`balance-tile border-${accent}`}>
      <span className="text-sm text-ink/60">{label}</span>
      <strong className="mt-2 block text-2xl">{rupees(value)}</strong>
    </div>
  );
}

function Panel({ title, children }) {
  return (
    <section className="rounded border border-ink/15 bg-white p-4">
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function StatusBadge({ status }) {
  const tone = {
    pending: "bg-steel/10 text-steel",
    processing: "bg-amber-100 text-amber-800",
    completed: "bg-mint/15 text-green-800",
    failed: "bg-coral/15 text-red-800",
  }[status];
  return <span className={`rounded px-2 py-1 text-xs font-medium ${tone}`}>{status}</span>;
}

createRoot(document.getElementById("root")).render(<App />);
