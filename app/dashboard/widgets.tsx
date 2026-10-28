import type { AgBaseRegistry, AgBaseWidgetDefinition, AgDefaultWidgetDefinition, AgWidgetDataFormat, AgWidgetFieldReference, AgWidgetParams } from "ag-studio";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { usd } from "../api";
import { Avatar } from "../ui";
import type { TransferRow } from "./data";

// HeyList's own Dashboard widgets (decision 62): the parts AG Studio's charts and tables can't show the HeyList way.

export interface ScoreboardDef {
  type: "settle-scoreboard";
  dataMapping: Record<string, never>;
  format?: AgWidgetDataFormat<object>;
}
export interface ProofMeterDef {
  type: "proof-meter";
  dataMapping: { group: AgWidgetFieldReference[]; proof: AgWidgetFieldReference[]; amount: AgWidgetFieldReference[] };
  format?: AgWidgetDataFormat<object>;
}
export interface DashboardRegistry extends AgBaseRegistry {
  widgets: readonly (AgDefaultWidgetDefinition | AgBaseWidgetDefinition<"settle-scoreboard", ScoreboardDef> | AgBaseWidgetDefinition<"proof-meter", ProofMeterDef>)[];
}
// What the page hands every widget through Studio's context property.
export type DashboardContext = { transfers: TransferRow[] };

const SMILE = ["Nearly even", "Just a little left", "Almost there"];

// Settle-up scoreboard: who still owes whom across your lists, as a friendly scoreboard rather than a collections
// report. Paying opens that list's Settle up, where the PayPal payment goes straight to the person owed (7B).
export function Scoreboard({ context, widgetApi }: AgWidgetParams<ScoreboardDef, unknown, DashboardContext>) {
  const transfers = context?.transfers ?? [];
  const owed = transfers.filter((t) => t.status === "Owed");
  const done = transfers.filter((t) => t.status !== "Owed");

  useEffect(() => {
    widgetApi.setDisplayState(transfers.length ? "displayed" : "noData");
  }, [transfers.length, widgetApi]);

  return (
    <div className="flex h-full flex-col gap-3 overflow-auto p-1 text-text">
      <p className="text-lg font-medium">{owed.length === 0 ? "Everyone's even 🎉" : `${SMILE[owed.length % SMILE.length]} · ${owed.length} to settle`}</p>
      <ul className="flex flex-col gap-2">
        {owed.map((t) => (
          <li key={t.id} className="flex items-center gap-3 rounded-[18px] bg-white/70 px-3 py-2.5">
            <Avatar name={t.from} size={32} />
            <span className="min-w-0 flex-1 text-sm">
              <span className="font-medium">{t.from}</span> → <span className="font-medium">{t.to}</span>
              <span className="block truncate text-xs text-muted">{t.list}</span>
            </span>
            <span className="text-base font-medium text-money tabular-nums">{usd(Math.round(t.amount * 100))}</span>
            <Link href={`/lists/${t.listId}/settle`} className="rounded-full bg-ai px-3 py-1.5 text-xs font-medium text-on-accent">
              Pay with PayPal
            </Link>
          </li>
        ))}
        {done.map((t) => (
          <li key={t.id} className="flex items-center gap-3 px-3 py-1 text-sm text-muted">
            <span className="flex-1">
              {t.from} paid {t.to} · {t.list}
            </span>
            <span className="tabular-nums">{usd(Math.round(t.amount * 100))}</span>
            <span className={t.status === "Paid with PayPal" ? "text-list" : "text-money"}>{t.status === "Paid with PayPal" ? "✓ PayPal" : "pending"}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Proof meter: for each group (a list, by default), how much of the spending is proven by PayPal or a receipt, and
// how much rests on someone's word (a hand tick). HeyList's promise, "know what really got done", in one widget.
// It reads through Studio's data engine, so page filters and cross-filters apply.
export function ProofMeter({ dataMapping, widgetApi }: AgWidgetParams<ProofMeterDef>) {
  const [rows, setRows] = useState<{ group: string; proven: number; total: number }[]>([]);
  const loaded = useRef(false);

  useEffect(() => {
    const [group, proof, amount] = [dataMapping.group?.at(0), dataMapping.proof?.at(0), dataMapping.amount?.at(0)];
    if (!group || !proof || !amount) {
      widgetApi.setDisplayState("incompleteDataMapping");
      return;
    }
    let live = true;
    widgetApi.setDisplayState("loading", { prominent: !loaded.current });
    widgetApi.getData({ fields: [group, proof, amount] }).then((response) => {
      if (!live) return;
      const totals = new Map<string, { proven: number; total: number }>();
      for (const row of response.results.rows) {
        const key = String(row[group.key] ?? "—");
        const value = Number(row[amount.key]) || 0;
        const entry = totals.get(key) ?? { proven: 0, total: 0 };
        entry.total += value;
        if (row[proof.key] !== "Hand tick") entry.proven += value;
        totals.set(key, entry);
      }
      const next = [...totals].map(([key, t]) => ({ group: key, ...t })).filter((r) => r.total > 0);
      loaded.current = next.length > 0;
      setRows(next);
      widgetApi.setDisplayState(next.length ? "displayed" : "noData");
    });
    return () => {
      live = false;
    };
  }, [dataMapping, widgetApi]);

  return (
    <ul className="flex h-full flex-col gap-3 overflow-auto p-1 text-text">
      {rows.map((r) => {
        const share = Math.round((r.proven / r.total) * 100);
        return (
          <li key={r.group} className="flex flex-col gap-1">
            <span className="flex justify-between text-sm">
              <span className="truncate font-medium">{r.group}</span>
              <span className="tabular-nums text-muted">{share}% proven</span>
            </span>
            <span className="flex h-2.5 overflow-hidden rounded-full bg-money/25" role="img" aria-label={`${share}% proven by PayPal or a receipt`}>
              <span className="bg-list" style={{ width: `${share}%` }} />
            </span>
          </li>
        );
      })}
    </ul>
  );
}
