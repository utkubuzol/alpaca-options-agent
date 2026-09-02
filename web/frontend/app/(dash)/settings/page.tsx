"use client";

export const dynamic = "force-dynamic";
import { useEffect, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { Card, Btn } from "@/components/ui";

const EVENT_KINDS = ["fill", "error", "risk_decision", "candidate", "scan"];

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-xl font-semibold">Settings</h1>
      <BrokerSection />
      <NotificationSection />
    </div>
  );
}

function BrokerSection() {
  const [state, setState] = useState<any>(null);
  const [apiKey, setApiKey] = useState("");
  const [secret, setSecret] = useState("");
  const [baseline, setBaseline] = useState(100000);
  const [msg, setMsg] = useState<string | null>(null);

  const load = () => apiGet("/api/broker-credentials").then(setState);
  useEffect(() => {
    load();
  }, []);

  async function save() {
    setMsg(null);
    try {
      await apiSend("/api/broker-credentials", "PUT", {
        api_key: apiKey,
        secret_key: secret,
        paper: true,
        baseline_equity: baseline,
      });
      setApiKey("");
      setSecret("");
      setMsg("Saved.");
      load();
    } catch (e: any) {
      setMsg(String(e));
    }
  }

  async function test() {
    setMsg("Testing…");
    try {
      const r = await apiSend("/api/broker-credentials/test", "POST");
      setMsg(`OK — equity ${r.equity}, market ${r.market_open ? "open" : "closed"}.`);
    } catch (e: any) {
      setMsg(String(e));
    }
  }

  return (
    <Card title="Alpaca paper credentials">
      {state?.configured && (
        <p className="text-xs opacity-60 mb-2">
          Configured · key {state.api_key_preview} · baseline {state.baseline_equity}
        </p>
      )}
      <div className="grid gap-2">
        <input
          placeholder="API key id"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
        <input
          placeholder="API secret"
          type="password"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
        />
        <input
          type="number"
          placeholder="baseline equity"
          value={baseline}
          onChange={(e) => setBaseline(Number(e.target.value))}
        />
        <div className="flex gap-2">
          <Btn onClick={save} disabled={!apiKey || !secret}>
            Save
          </Btn>
          <Btn variant="ghost" onClick={test}>
            Test connection
          </Btn>
        </div>
        {msg && <p className="text-xs text-amber-400">{msg}</p>}
        <p className="text-[11px] opacity-50">
          Paper keys only — get them at app.alpaca.markets/paper/dashboard/overview. Stored
          encrypted at rest.
        </p>
      </div>
    </Card>
  );
}

function NotificationSection() {
  const [s, setS] = useState<any>({
    telegram_chat_id: "",
    telegram_bot_token: "",
    whatsapp_number: "",
    channels: { telegram: true, whatsapp: false },
    event_kinds: ["fill", "error"],
  });
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    apiGet("/api/notification-settings").then((d) =>
      setS((prev: any) => ({ ...prev, ...d, telegram_bot_token: "" })),
    );
  }, []);

  async function save() {
    setMsg(null);
    try {
      await apiSend("/api/notification-settings", "PUT", s);
      setMsg("Saved.");
    } catch (e: any) {
      setMsg(String(e));
    }
  }
  async function test() {
    setMsg("Sending…");
    try {
      await apiSend("/api/notification-settings/test", "POST");
      setMsg("Sent — check Telegram.");
    } catch (e: any) {
      setMsg(String(e));
    }
  }

  return (
    <Card title="Notifications">
      <div className="grid gap-2 text-sm">
        <label className="text-xs opacity-60">Telegram chat id</label>
        <input
          value={s.telegram_chat_id || ""}
          onChange={(e) => setS({ ...s, telegram_chat_id: e.target.value })}
          placeholder="e.g. 123456789"
        />
        <label className="text-xs opacity-60">
          Telegram bot token (optional — blank uses the platform bot)
        </label>
        <input
          type="password"
          value={s.telegram_bot_token || ""}
          onChange={(e) => setS({ ...s, telegram_bot_token: e.target.value })}
          placeholder={s.has_custom_bot_token ? "•••• (set) — type to replace" : ""}
        />
        <label className="text-xs opacity-60">WhatsApp number (coming soon)</label>
        <input disabled placeholder="stub — not yet delivered" />

        <div className="flex gap-4 mt-1">
          {["telegram", "whatsapp"].map((c) => (
            <label key={c} className="text-xs flex items-center gap-1">
              <input
                type="checkbox"
                disabled={c === "whatsapp"}
                checked={!!s.channels?.[c]}
                onChange={(e) =>
                  setS({ ...s, channels: { ...s.channels, [c]: e.target.checked } })
                }
              />
              {c}
            </label>
          ))}
        </div>

        <div className="text-xs opacity-60 mt-1">Notify on:</div>
        <div className="flex gap-3 flex-wrap">
          {EVENT_KINDS.map((k) => (
            <label key={k} className="text-xs flex items-center gap-1">
              <input
                type="checkbox"
                checked={s.event_kinds?.includes(k)}
                onChange={(e) =>
                  setS({
                    ...s,
                    event_kinds: e.target.checked
                      ? [...(s.event_kinds || []), k]
                      : s.event_kinds.filter((x: string) => x !== k),
                  })
                }
              />
              {k}
            </label>
          ))}
        </div>

        <div className="flex gap-2 mt-2">
          <Btn onClick={save}>Save</Btn>
          <Btn variant="ghost" onClick={test}>
            Send test
          </Btn>
        </div>
        {msg && <p className="text-xs text-amber-400">{msg}</p>}
        <p className="text-[11px] opacity-50">
          Get your chat id: DM your bot (or @userinfobot) and it replies with the numeric id.
        </p>
      </div>
    </Card>
  );
}
