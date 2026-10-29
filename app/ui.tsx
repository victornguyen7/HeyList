"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

// Shared pieces of the soft glass design (Figma "HeyList — Soft glass" and "HeyList — Web (soft glass)").
// One codebase for both: below the lg breakpoint (1024px) it is the phone layout, above it the website layout.

export const button = "flex h-12 items-center justify-center rounded-[30px] bg-list px-6 text-base font-medium text-on-accent disabled:opacity-40";
export const buttonAi = "flex h-12 items-center justify-center rounded-[30px] bg-ai px-6 text-base font-medium text-on-accent disabled:opacity-40";
export const buttonGlass = "flex h-12 items-center justify-center rounded-[30px] border border-line bg-surface-2 px-6 text-base font-medium text-text disabled:opacity-40";
export const card = "glass rounded-3xl p-[18px]";
export const row = "flex items-center gap-3.5 rounded-[18px] bg-surface px-4 py-3.5";
export const chip = "rounded-[20px] border border-line bg-surface-2 px-3.5 py-[9px] text-sm font-medium";
export const field = "h-12 rounded-[20px] bg-bg px-4 text-base";
// Figma "Mini button": a small action inside a row or card (Find in stores, Remind, Buy again). Never full width.
export const mini = "inline-flex h-8 shrink-0 items-center justify-center self-start rounded-full border border-ai/35 bg-surface-2 px-3.5 text-[13px] font-medium whitespace-nowrap text-ai disabled:opacity-40";
// Figma "Pay buttons": PayPal as the black pill, Venmo as the white one, side by side.
export const payPayPal = "flex h-12 flex-1 items-center justify-center rounded-full bg-list px-4 text-[15px] font-semibold whitespace-nowrap text-on-accent disabled:opacity-40";
export const payVenmo = "flex h-12 flex-1 items-center justify-center rounded-full border border-line bg-surface-2 px-4 text-[15px] font-semibold whitespace-nowrap text-ai disabled:opacity-40";
// Figma "Action row": one line of a More actions menu.
export const menuRow = "flex h-[52px] w-full items-center justify-between gap-3 px-[18px] text-left text-base font-medium disabled:opacity-40";

// Figma "Pay card": what is being paid for and how much, above the pay buttons.
export function PayCard({ title, amount, note, children }: { title: string; amount: string; note?: string; children: React.ReactNode }) {
  return (
    <div className={`${card} flex flex-col gap-3.5`}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="min-w-0 text-[15px] font-medium text-muted">{title}</span>
        <span className="text-2xl text-money tabular-nums">{amount}</span>
      </div>
      {children}
      {note && <p className="text-xs text-muted">{note}</p>}
    </div>
  );
}

export function Brand() {
  return (
    <span className="flex items-center gap-2">
      {/* eslint-disable-next-line @next/next/no-img-element -- 12px design asset */}
      <img src="/ui/dot.svg" alt="" width={12} height={12} />
      <span className="text-[22px] font-semibold">HeyList</span>
    </span>
  );
}

// The nav links, the current one highlighted. path is "" while it isn't known yet.
function NavLinks({ path }: { path: string }) {
  const link = (href: string, label: string, active: boolean) => (
    <Link href={href} className={active ? "font-medium text-text" : "text-muted hover:text-text"} aria-current={active ? "page" : undefined}>
      {label}
    </Link>
  );
  return (
    <div className="flex gap-9 text-base">
      {link("/", "My lists", path === "/" || path.startsWith("/lists"))}
      {link("/history", "History", path === "/history")}
    </div>
  );
}

function CurrentNavLinks() {
  return <NavLinks path={usePathname()} />;
}

// Website top bar (Figma "Web nav"). Hidden on phones, which use the in-page links instead.
export function WebNav() {
  return (
    <nav className="glass hidden items-center justify-between rounded-full py-2.5 pr-2.5 pl-7 lg:flex" aria-label="HeyList">
      <Link href="/">
        <Brand />
      </Link>
      {/* usePathname suspends while prerendering a list page, whose ID is only known at request time
          (Cache Components), so only the links wait; the rest of the bar is prerendered. */}
      <Suspense fallback={<NavLinks path="" />}>
        <CurrentNavLinks />
      </Suspense>
      <div className="flex items-center gap-4">
        <Link href="/login" className="text-[15px] text-muted hover:text-text">
          Log in
        </Link>
        <Link href="/" className={`${button} h-10 w-[120px] px-0 text-[15px]`}>
          New list
        </Link>
      </div>
    </nav>
  );
}

// The page frame: the blurred colour glows behind everything, the web nav, then the page.
export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        {/* eslint-disable @next/next/no-img-element -- decorative design assets */}
        <img src="/ui/glow-top.svg" alt="" width={576} height={576} className="absolute top-[-248px] left-[-8px] lg:hidden" />
        <img src="/ui/glow-low.svg" alt="" width={468} height={468} className="absolute top-[416px] left-[-244px] lg:hidden" />
        <img src="/ui/glow-web.svg" alt="" width={1080} height={840} className="absolute top-[100px] left-[-380px] hidden lg:block" />
        {/* eslint-enable @next/next/no-img-element */}
      </div>
      <div className="mx-auto flex w-full max-w-[1200px] flex-1 flex-col gap-7 px-4 pt-[50px] pb-[120px] lg:gap-10 lg:px-6 lg:pt-8 lg:pb-12">
        <WebNav />
        {children}
      </div>
    </>
  );
}

// Progress ring (Figma "Ring"): a light track with the done share in the list colour. className can resize it per
// breakpoint (it scales from its viewBox).
export function Ring({ done, total, size, className = "" }: { done: number; total: number; size: number; className?: string }) {
  const stroke = size / 8;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const share = total ? done / total : 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden className={`shrink-0 -rotate-90 ${className}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-2)" strokeWidth={stroke} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="var(--list)"
        strokeWidth={stroke}
        strokeDasharray={`${circumference * share} ${circumference}`}
      />
    </svg>
  );
}

// A person's initial in a blue circle (Figma "Avatar"). ring adds the background-coloured edge used in stacks.
export function Avatar({ name, size = 36, ring = false }: { name: string; size?: number; ring?: boolean }) {
  return (
    <span
      title={name}
      style={{ width: size, height: size }}
      className={`flex shrink-0 items-center justify-center rounded-full bg-ai text-[15px] font-medium text-on-accent ${ring ? "-mr-2.5 border-2 border-bg" : ""}`}
    >
      {name.slice(0, 1).toUpperCase()}
    </span>
  );
}

// Item row check circle (Figma "Check"): an empty ring, or filled with a tick when done.
export function Check({ done }: { done: boolean }) {
  return done ? (
    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-list">
      {/* eslint-disable-next-line @next/next/no-img-element -- 16px design asset */}
      <img src="/ui/check.svg" alt="" width={16} height={16} />
    </span>
  ) : (
    <span className="block size-7 shrink-0 rounded-full border-2 border-muted" />
  );
}
