"use client";

import {
  AgStudioAiModule,
  createAiHarness,
  directLlmRunner,
  studioTheme,
  type AgAiHarnessSetup,
  type AgAiPromptStarter,
  type AgDataSourcesDefinition,
  type AgFieldDefinition,
  type AgReportState,
} from "ag-studio";
import { AgStudio, AgStudioProvider, createWidgets } from "ag-studio-react";
import { useEffect, useMemo, useRef } from "react";
import type { List } from "../api";
import { dashboardData } from "./data";
import { ollamaAdapter } from "./ollama-adapter";
import { ProofMeter, Scoreboard, type DashboardContext, type DashboardRegistry } from "./widgets";

// The Dashboard (phase 7D, decision 62): one AG Studio dashboard over the money of every list this browser has
// opened. Browser only; the page loads this file with next/dynamic and ssr: false.

const money = { format: "currencyFormat", formatOptions: { format: "$#,##0.00" } } as const;
const text = (id: string, name: string, description: string): AgFieldDefinition => ({ id, name, format: "textFormat", description });
const dollars = (id: string, name: string, description: string): AgFieldDefinition => ({ id, name, description, ...money });

function sources(lists: List[]): AgDataSourcesDefinition<DashboardRegistry> {
  const { ledger, balances, transfers, items } = dashboardData(lists);
  return {
    description:
      "Shared shopping lists from HeyList: what people bought for each list, how it was proven (PayPal payment, receipt, or ticked by hand), " +
      "each person's equal share, and who still owes whom. Amounts are US dollars.",
    sources: [
      {
        id: "ledger",
        name: "Spending",
        description: "One row per money line: a purchase, a receipt's tax, tip and fees, a PayPal charge for an item already covered, or a refund.",
        data: ledger,
        fields: [
          { id: "id", name: "Line", format: "textFormat", description: "Row identifier", hide: true },
          { id: "date", name: "Date", format: "dateFormat", description: "When the item was bought or the receipt confirmed" },
          text("month", "Month", "Year and month, like 2026-10"),
          text("list", "List", "The shared list's title"),
          text("listType", "List type", "groceries, trip, home, party or other"),
          text("item", "Item", "The item bought, or 'Tax, tip and fees'"),
          text("who", "Who paid", "The person who paid"),
          text("kind", "Kind", "Purchase, Fees, Bought twice, or Refund"),
          text("proof", "Proof", "PayPal, Receipt, or Hand tick (someone's word)"),
          dollars("amount", "Spent", "Money spent on the list; 0 on refund rows"),
          dollars("proven", "Proven spending", "The part of Spent backed by PayPal or a receipt"),
          dollars("refunded", "Refunded", "Money PayPal gave back for an item someone had already bought"),
        ],
      },
      {
        id: "balances",
        name: "Balances",
        description: "Each person on each list: what they paid, their equal share, settle-up payments sent (+) or received (−), and the balance (+ gets back, − owes).",
        data: balances,
        fields: [
          { id: "id", name: "Row", format: "textFormat", description: "Row identifier", hide: true },
          text("list", "List", "The shared list's title"),
          text("person", "Person", "Someone on the list"),
          dollars("paid", "Paid", "What they paid for list items"),
          dollars("share", "Share", "Their equal share of the list's spending"),
          dollars("settled", "Settled", "Settle-up payments sent minus received"),
          dollars("balance", "Balance", "Positive: gets money back. Negative: owes"),
        ],
      },
      {
        id: "transfers",
        name: "Who owes whom",
        description: "The fewest payments that make everyone even, plus settle-up payments already made with PayPal.",
        data: transfers.map((t) => ({ ...t, owed: t.status === "Owed" ? t.amount : 0 })),
        fields: [
          { id: "id", name: "Row", format: "textFormat", description: "Row identifier", hide: true },
          { id: "listId", name: "List ID", format: "textFormat", description: "List identifier", hide: true },
          text("list", "List", "The shared list's title"),
          text("from", "From", "Who pays"),
          text("to", "To", "Who gets paid"),
          dollars("amount", "Amount", "The payment"),
          dollars("owed", "Still owed", "The amount while unpaid; 0 once paid"),
          text("status", "Status", "Owed, Paid with PayPal, or Pending at PayPal"),
        ],
      },
      {
        id: "items",
        name: "Items",
        description: "Every item on every list, with its status and prices.",
        data: items,
        fields: [
          { id: "id", name: "Item ID", format: "textFormat", description: "Row identifier", hide: true },
          text("list", "List", "The shared list's title"),
          text("item", "Item", "The item"),
          text("status", "Status", "Needed, Payment pending at PayPal, Paid with PayPal, On a receipt, or Marked bought by hand"),
          dollars("estimate", "Estimate", "Estimated cost for the quantity needed"),
          dollars("paid", "Price paid", "What was paid, once bought"),
          text("store", "Store", "The online store of a chosen product"),
        ],
      },
    ],
  };
}

const kpi = (field: string, title: string) => ({ type: "value" as const, dataMapping: { value: [{ id: field, aggregation: "sum" as const }] }, format: { title: { enabled: true, text: title } } });
const chart = (type: "bar-chart-grouped" | "column-chart-grouped" | "donut-chart", category: string, title: string) => ({
  type,
  dataMapping: { categoryKey: [{ id: category }], valueKey: [{ id: "ledger.amount", aggregation: "sum" as const }], tooltipKey: [] },
  format: { title: { enabled: true, text: title } },
});

// The starting dashboard. People rearrange it in edit mode, and the assistant adds to it.
const INITIAL_STATE = {
  pages: [
    {
      id: "money",
      name: "Where our money went",
      widgets: {
        spent: kpi("ledger.amount", "Spent"),
        proven: kpi("ledger.proven", "Proven by PayPal or receipt"),
        refunded: kpi("ledger.refunded", "Refunded"),
        owed: kpi("transfers.owed", "Still owed"),
        scoreboard: { type: "settle-scoreboard", dataMapping: {}, format: { title: { enabled: true, text: "Who still owes whom" } } },
        meter: {
          type: "proof-meter",
          dataMapping: { group: [{ id: "ledger.list" }], proof: [{ id: "ledger.proof" }], amount: [{ id: "ledger.amount", aggregation: "sum" }] },
          format: { title: { enabled: true, text: "How much is proven" } },
        },
        byPerson: chart("bar-chart-grouped", "ledger.who", "Spending by person"),
        byProof: chart("donut-chart", "ledger.proof", "Proof mix"),
        byMonth: chart("column-chart-grouped", "ledger.month", "Spending by month"),
        byType: chart("bar-chart-grouped", "ledger.listType", "Spending by list type"),
        ledger: {
          type: "grid",
          dataMapping: {
            cols: [
              { id: "ledger.date" },
              { id: "ledger.list" },
              { id: "ledger.item" },
              { id: "ledger.who" },
              { id: "ledger.kind" },
              { id: "ledger.proof" },
              { id: "ledger.amount", aggregation: "sum" },
              { id: "ledger.refunded", aggregation: "sum" },
            ],
          },
          format: { title: { enabled: true, text: "Every money line" } },
        },
      },
      widgetLayout: {
        spent: { xTrack: 0, yTrack: 0, xSpan: 6, ySpan: 6 },
        proven: { xTrack: 6, yTrack: 0, xSpan: 6, ySpan: 6 },
        refunded: { xTrack: 12, yTrack: 0, xSpan: 6, ySpan: 6 },
        owed: { xTrack: 18, yTrack: 0, xSpan: 6, ySpan: 6 },
        scoreboard: { xTrack: 0, yTrack: 6, xSpan: 12, ySpan: 14 },
        meter: { xTrack: 12, yTrack: 6, xSpan: 12, ySpan: 14 },
        byPerson: { xTrack: 0, yTrack: 20, xSpan: 12, ySpan: 14 },
        byProof: { xTrack: 12, yTrack: 20, xSpan: 12, ySpan: 14 },
        byMonth: { xTrack: 0, yTrack: 34, xSpan: 12, ySpan: 14 },
        byType: { xTrack: 12, yTrack: 34, xSpan: 12, ySpan: 14 },
        ledger: { xTrack: 0, yTrack: 48, xSpan: 24, ySpan: 18 },
      },
    },
    { id: "mine", name: "Your charts" },
  ],
  selectedPageId: "money",
  panels: { filters: { collapsed: true }, edit: { collapsed: true }, data: { collapsed: true } },
} as unknown as AgReportState<DashboardRegistry>;

// HeyList's look (globals.css): soft glass cards, the AI blue as accent, green and clay in the charts.
const THEME = studioTheme.withParams({
  accentColor: "#5a7a9c",
  foregroundColor: "#1c1f26",
  backgroundColor: "#ffffff",
  borderColor: "#dfe3ea",
  borderRadius: 14,
  fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
  studioCanvasBackgroundColor: "#e9ecf1",
  studioWidgetBackgroundColor: "#ffffffcc",
  studioWidgetBorderRadius: 24,
  chartPaletteFills1Color: "#5a7a9c",
  chartPaletteFills2Color: "#a8705e",
  chartPaletteFills3Color: "#1c1f26",
  chartPaletteFills4Color: "#86a5b8",
  chartPaletteFills5Color: "#d3a998",
});

const WIDGETS = (defaults: { menu: unknown[] }) =>
  createWidgets<DashboardRegistry>({
    additionalTypes: [
      {
        id: "settle-scoreboard",
        label: "Who owes whom",
        icon: { url: "/ui/arrow.svg" },
        comp: Scoreboard,
        // Only the title and look in the edit panel: the scoreboard reads HeyList's own split, not a data mapping.
        form: (params) => params.createDefaults({ dataMappingItems: [] }),
        defaultSize: { width: 480, height: 360 },
        minSize: { width: 320, height: 200 },
        ai: { description: "HeyList's settle-up scoreboard: who still owes whom across the lists, with a Pay with PayPal button on each open payment. Takes no data mapping." },
      },
      {
        id: "proof-meter",
        label: "Proof meter",
        icon: { url: "/ui/arrow.svg" },
        comp: ProofMeter,
        form: (params) =>
          params.createDefaults({
            dataMappingItems: [
              { key: "group", label: "Compare" },
              { key: "proof", label: "Proof" },
              { key: "amount", label: "Amount" },
            ],
          }),
        dataMapping: {
          group: { type: "field", supportedRoles: ["category"], requires: { cardinality: "many" }, required: true, aiDescription: "What to compare, such as ledger.list or ledger.who." },
          proof: { type: "field", supportedRoles: ["category"], requires: { cardinality: "many" }, required: true, aiDescription: "The proof field: ledger.proof." },
          amount: { type: "field", supportedRoles: ["numeric"], requires: { per: "dataMapping.group", cardinality: "one" }, required: true, aiDescription: "The money: ledger.amount, summed." },
        },
        defaultSize: { width: 480, height: 360 },
        minSize: { width: 280, height: 160 },
        ai: { description: "Share of spending proven by PayPal or a receipt, versus ticked by hand, per group." },
      },
    ],
    menu: [...(defaults.menu as never[]), { label: "HeyList", widgetIds: ["settle-scoreboard", "proof-meter"] }],
  });

const PROMPTS: AgAiPromptStarter[] = [
  { label: "Who owes what?", prompt: "Who still owes what across our lists?" },
  { label: "Spending by person this month", prompt: "Add a chart of what each person spent this month." },
  { label: "Draft a friendly nudge", prompt: "Draft a short, friendly reminder for the person who owes the most." },
];

const NUDGE_RULES = [
  "You are HeyList's money assistant, working on a dashboard of shared shopping lists. Amounts are US dollars.",
  "Answer questions with real numbers from the data: use who_owes_whom for debts, and execute_query for anything else. Never guess an amount.",
  "To add or change charts, delegate: 'page' places widgets on the page, then 'widget' configures each one. Put new charts on the 'Your charts' page unless asked otherwise.",
  "When asked for a reminder or nudge, write two or three warm, light sentences, like a friend would ('hey, just a heads-up…'), with the list, the amount and who to pay. " +
    "Mention that they can pay with PayPal from the list's Settle up page. Never sound like a debt collector. You only draft it: you can't send messages, so say the person can copy it.",
  "Keep replies short.",
].join("\n");

export default function DashboardStudio({ lists }: { lists: List[] }) {
  const data = useMemo(() => sources(lists), [lists]);
  const context = useMemo<DashboardContext>(() => ({ transfers: dashboardData(lists).transfers }), [lists]);
  // The agent's tool reads the latest numbers, though the harness is built once.
  const latest = useRef(context);
  useEffect(() => {
    latest.current = context;
  }, [context]);

  const ai = useMemo<AgAiHarnessSetup>(
    () =>
      ({ api }) => {
        const adapter = ollamaAdapter();
        // A custom tool: the exact open debts from HeyList's own split, so the agent never adds money up itself.
        const whoOwesWhom = api.defineAiTool({
          name: "who_owes_whom",
          description: "List who still owes whom on each list (exact amounts from HeyList's split), and settle-up payments already made with PayPal.",
          params: (s) => s.object({}),
          execute: async (_args, ctx) => {
            const rows = latest.current.transfers.map(({ list, from, to, amount, status }) => ({ list, from, to, amount, status }));
            return rows.length ? ctx.success(`${rows.filter((r) => r.status === "Owed").length} payments still owed.`, { payments: rows }) : ctx.success("Everyone is even on every list.");
          },
        });
        return createAiHarness(api, ({ builtIn, tools }) => ({
          agents: [
            // HeyList's own agent leads; Studio's built-in page and widget agents do the dashboard work it hands them.
            directLlmRunner({
              id: "heylist",
              adapter,
              description: "HeyList's money assistant.",
              schema: (s) => s.undefined(),
              instructions: () => NUDGE_RULES,
              tools: () => [tools.studio.viewSchema(), tools.studio.viewPage(), tools.studio.executeQuery(), whoOwesWhom, tools.delegateTo(["page", "widget"])],
            }),
            directLlmRunner({ ...builtIn.page, adapter }),
            directLlmRunner({ ...builtIn.widget, adapter }),
          ],
          primary: "heylist",
          promptStarters: PROMPTS,
        }));
      },
    [],
  );

  return (
    <AgStudioProvider licenseKey={process.env.NEXT_PUBLIC_AG_STUDIO_LICENSE_KEY} modules={[AgStudioAiModule]}>
      <AgStudio<DashboardRegistry>
        style={{ height: "100%", width: "100%" }}
        data={data}
        context={context}
        initialState={INITIAL_STATE}
        widgets={WIDGETS as never}
        theme={THEME}
        mode="edit"
        ai={ai}
      />
    </AgStudioProvider>
  );
}
