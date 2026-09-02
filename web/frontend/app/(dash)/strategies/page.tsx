"use client";

export const dynamic = "force-dynamic";
import { useEffect, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { Card, Btn } from "@/components/ui";

const TYPES = ["csp", "covered_call", "credit_spread"];

type Strategy = any;

const EMPTY = {
  name: "",
  enabled: false,
  universe: "SPY,QQQ,AAPL",
  strategy_types: ["csp", "credit_spread"],
  interval_minutes: 15,
  params: { target_delta: 0.2, min_dte: 25, max_dte: 45, profit_target_pct: 0.5, stop_loss_multiple: 2 },
  risk: { max_risk_per_trade_pct: 0.02, max_concurrent_positions: 6, max_single_underlying_exposure_pct: 0.25 },
};

export default function StrategiesPage() {
  const [list, setList] = useState<Strategy[]>([]);
  const [editing, setEditing] = useState<any | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = () => apiGet("/api/strategies").then((d) => setList(d.strategies || []));
  useEffect(() => {
    load();
  }, []);

  async function save() {
    setMsg(null);
    const body = {
      ...editing,
      universe: String(editing.universe)
        .split(",")
        .map((s: string) => s.trim())
        .filter(Boolean),
    };
    try {
      if (editing.id) await apiSend(`/api/strategies/${editing.id}`, "PUT", body);
      else await apiSend("/api/strategies", "POST", body);
      setEditing(null);
      load();
    } catch (e: any) {
      setMsg(String(e));
    }
  }

  async function runNow(id: string, mode: string) {
    setMsg(null);
    try {
      await apiSend(`/api/strategies/${id}/run?mode=${mode}`, "POST");
      setMsg(`Queued ${mode} for ${id.slice(0, 8)}. Watch the Trades tab.`);
    } catch (e: any) {
      setMsg(String(e));
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Strategies</h1>
        <Btn onClick={() => setEditing({ ...EMPTY })}>+ New strategy</Btn>
      </div>
      {msg && <div className="text-xs text-amber-400">{msg}</div>}

      <div className="grid gap-3">
        {list.map((s) => (
          <Card key={s.id}>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <div className="font-medium">
                  {s.name}{" "}
                  <span className="text-[10px] rounded bg-panel px-1.5 py-0.5 opacity-70">
                    {s.mode}
                  </span>
                </div>
                <div className="text-xs opacity-60">
                  {(s.universe || []).join(", ")} · {(s.strategy_types || []).join("/")} · every{" "}
                  {s.interval_minutes}m
                  {s.last_run_at && ` · last ${new Date(s.last_run_at).toLocaleTimeString()}`}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-xs flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={s.enabled}
                    onChange={(e) =>
                      apiSend(
                        `/api/strategies/${s.id}/enabled?enabled=${e.target.checked}`,
                        "PATCH",
                      ).then(load)
                    }
                  />
                  enabled
                </label>
                <Btn variant="ghost" onClick={() => runNow(s.id, "scan")}>
                  Run scan
                </Btn>
                <Btn variant="ghost" onClick={() => setEditing({ ...s, universe: (s.universe || []).join(",") })}>
                  Edit
                </Btn>
                <Btn
                  variant="danger"
                  onClick={() =>
                    apiSend(`/api/strategies/${s.id}`, "DELETE").then(load)
                  }
                >
                  Delete
                </Btn>
              </div>
            </div>
          </Card>
        ))}
        {list.length === 0 && (
          <p className="text-xs opacity-50">No strategies yet.</p>
        )}
      </div>

      {editing && (
        <Card title={editing.id ? "Edit strategy" : "New strategy"}>
          <div className="grid md:grid-cols-2 gap-3 text-sm">
            <Field label="Name">
              <input
                className="w-full"
                value={editing.name}
                onChange={(e) => setEditing({ ...editing, name: e.target.value })}
              />
            </Field>
            <Field label="Universe (comma-separated)">
              <input
                className="w-full"
                value={editing.universe}
                onChange={(e) => setEditing({ ...editing, universe: e.target.value })}
              />
            </Field>
            <Field label="Strategy types">
              <div className="flex gap-3">
                {TYPES.map((t) => (
                  <label key={t} className="text-xs flex items-center gap-1">
                    <input
                      type="checkbox"
                      checked={editing.strategy_types.includes(t)}
                      onChange={(e) =>
                        setEditing({
                          ...editing,
                          strategy_types: e.target.checked
                            ? [...editing.strategy_types, t]
                            : editing.strategy_types.filter((x: string) => x !== t),
                        })
                      }
                    />
                    {t}
                  </label>
                ))}
              </div>
            </Field>
            <Field label="Run interval (minutes)">
              <input
                type="number"
                className="w-full"
                value={editing.interval_minutes}
                onChange={(e) =>
                  setEditing({ ...editing, interval_minutes: Number(e.target.value) })
                }
              />
            </Field>
            <NumField obj={editing} setObj={setEditing} group="params" k="target_delta" step={0.01} />
            <NumField obj={editing} setObj={setEditing} group="params" k="min_dte" />
            <NumField obj={editing} setObj={setEditing} group="params" k="max_dte" />
            <NumField obj={editing} setObj={setEditing} group="params" k="profit_target_pct" step={0.05} />
            <NumField obj={editing} setObj={setEditing} group="params" k="stop_loss_multiple" step={0.5} />
            <NumField obj={editing} setObj={setEditing} group="risk" k="max_risk_per_trade_pct" step={0.005} />
            <NumField obj={editing} setObj={setEditing} group="risk" k="max_concurrent_positions" />
            <NumField
              obj={editing}
              setObj={setEditing}
              group="risk"
              k="max_single_underlying_exposure_pct"
              step={0.05}
            />
          </div>
          <div className="mt-3 flex items-center gap-2">
            <span className="text-[10px] rounded bg-panel px-1.5 py-0.5 opacity-60">
              paper only
            </span>
            <div className="ml-auto flex gap-2">
              <Btn variant="ghost" onClick={() => setEditing(null)}>
                Cancel
              </Btn>
              <Btn onClick={save}>Save</Btn>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="text-xs opacity-60 mb-1">{label}</div>
      {children}
    </label>
  );
}

function NumField({
  obj,
  setObj,
  group,
  k,
  step = 1,
}: {
  obj: any;
  setObj: (o: any) => void;
  group: "params" | "risk";
  k: string;
  step?: number;
}) {
  return (
    <Field label={`${group}.${k}`}>
      <input
        type="number"
        step={step}
        className="w-full"
        value={obj[group]?.[k] ?? ""}
        onChange={(e) =>
          setObj({
            ...obj,
            [group]: { ...obj[group], [k]: e.target.value === "" ? undefined : Number(e.target.value) },
          })
        }
      />
    </Field>
  );
}
