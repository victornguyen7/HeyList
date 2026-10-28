"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useSeenLists } from "../recent";
import { card } from "../ui";

// AG Studio runs only in the browser and is large, so it loads on this page alone and never on the server.
const DashboardStudio = dynamic(() => import("./studio"), { ssr: false, loading: () => <p className="text-base text-muted">Loading the dashboard…</p> });

// Dashboard (phase 7D, decision 62): the money of every list this browser has opened, in one AG Studio dashboard.
// Laptop layout only (decision 46): phones keep History's cards.
export default function DashboardPage() {
  const lists = useSeenLists();

  return (
    <main className="flex flex-1 flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h1 className="text-[32px] tracking-[-0.015em] lg:text-[48px] lg:font-medium">Dashboard</h1>
        <p className="text-base text-muted">Where your money went across your lists, and who still owes whom. Rearrange it, or ask the assistant.</p>
      </div>

      <p className={`${card} text-base lg:hidden`}>
        The dashboard is made for a laptop screen. On a phone, <Link href="/history" className="text-ai underline">History</Link> shows your lists and spending.
      </p>

      <div className="hidden lg:block">
        {!lists ? (
          <p className="text-base text-muted">Loading…</p>
        ) : lists === "failed" ? (
          <p role="status" className="text-base text-muted">
            Your lists could not be loaded right now. Reload the page to try again.
          </p>
        ) : lists.length === 0 ? (
          <p className="text-base text-muted">No lists yet. Lists you make or open on this device show up here.</p>
        ) : (
          <div className="h-[calc(100vh-180px)] min-h-[640px] overflow-hidden rounded-3xl">
            <DashboardStudio lists={lists} />
          </div>
        )}
      </div>
    </main>
  );
}
