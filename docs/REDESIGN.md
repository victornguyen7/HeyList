# HeyList — Soft glass redesign

What changed in the UI redesign (commit `5b2682c`, 2026-10-27), why, and what is still different from the design. Source design: [Figma](https://www.figma.com/design/Wv3JGTqJewtLNMax2PWmSk), frames "HeyList — Soft glass (overview)" (mobile, 390 × 844) and "HeyList — Web (soft glass)" (web, 1440 × 1024). Decisions 46 and 47 in [DECISIONS.md](DECISIONS.md).

## 1. The approach

| Topic | What was done |
|---|---|
| Mobile vs website | One codebase and one link. Below 1024 px wide (Tailwind `lg`) the page uses the phone layout; at 1024 px and wider it uses the website layout. The browser's width decides, not its user agent, so a narrow laptop window also gets the phone layout (decision 46) |
| Phone layout | Content in one column, 16 px side margins, a floating tab bar at the bottom of list pages |
| Website layout | A frosted top bar (logo, My lists, History, New list), pill tabs on list pages, two columns (content left, summary right), content up to 1200 px wide |
| Colours | The Figma "soft glass" variables, as CSS variables in `app/globals.css`. The dark "Midnight" theme can be added later as a second set of the same variables |
| Dark theme | Not built. The owner chose soft glass first (ROADMAP) |

### Colour tokens

| Token | Value | Used for |
|---|---|---|
| `--bg` | `#e9ecf1` | Page base, input fields |
| `--text` | `#1c1f26` | Text |
| `--muted` | `#6a7180` | Secondary text |
| `--list` | `#1c1f26` | Main buttons, progress, "done" |
| `--ai` | `#5a7a9c` | AI hints, avatars, Scan receipt, PayPal pay button |
| `--money` | `#a8705e` | Amounts, notes to check, "paid less" |
| `--on-accent` | `#ffffff` | Text on coloured buttons |
| `--surface` | `#ffffff8c` | Cards and item rows (frosted) |
| `--surface-2` | `#ffffffcc` | Chips, tab bar, active tab |
| `--line` | `#ffffffb2` | Card edges |

The page background is the Figma gradient (`#86a5b8` → `#aec2cf` → `#d8dee6` → `#e9ecf1`) with the blurred colour glows from the design behind it.

## 2. Page by page

| Page | Before | After |
|---|---|---|
| **Home** | Title, one-line promise, a text field and a separate budget field | Phone: logo and History link, "What are we planning?", the AI card (prompt, mic, Make my list), idea chips, "Your lists" cards with a progress ring. Web: the same in two columns, a short description under the title, and a "Spent in <month>" card |
| **AI review** | A list of ticks under the form | Its own screen: ← Back, "AI made N items in X seconds", the list title, a budget card with a bar ("$154 of $200 budget · $46 left"), editable item rows (name, −/+ quantity, note, price), "+ Add an item", and **Looks good, create list** pinned to the bottom on phones |
| **List header** (all list tabs) | Title, text tabs, join form | ← Lists and **Share link** (phone share sheet, or copies the link), title, avatars of the people on the list, a join card if you haven't joined. Web: pill tabs and Share link beside the title |
| **Progress** | One list with ticks, steppers and dropdowns on every row | A ring with done/total, three stats (spent so far, still to get, receipts), **Scan receipt** and **Pay $X** (the items you claimed are already chosen), **Share out the rest evenly**, then "Still to get" and "Done". Tap an item's name to change its quantity or who buys it. Web: lists left, ring and buttons right |
| **Items** | Cards with a status chip | Item rows with a check circle, status and proof line, note, link to the receipt |
| **Money** | Four number cards, a progress bar, a per-person list | "Spent together" in large type, an "Equal share" chip, a Budget card, "Who paid what" bars (the tick marks the equal share; dark = paid more, clay = paid less), Receipt extras. Web: Settle up shown beside it |
| **Receipts** | Cards | Same content in the new card style; the scan button is the blue AI button |
| **Settle up** | "Who pays whom" list, then "How this was worked out" | "2 payments and everyone's even", a card per payment (avatar → amount and arrow → avatar, with a clay edge and a **Pay with PayPal** button when you are the payer), the payments made with PayPal, then "How this was worked out" (phase 4) |
| **History** | Totals and a plain list | Totals in cards, lists as the same cards as on Home, with **Buy again** |

## 3. Behaviour that changed

- **Budget in the sentence** (decision 47). The separate budget box is gone; "…, $200 budget" in the prompt sets it. Only an amount next to the word "budget" counts, so "$15 tickets" is not read as a budget.
- **Voice input** (decision 47). The mic fills the prompt using the browser's own speech recognition (Chrome, Safari). It is hidden where the browser doesn't support it. Nothing else about voice is built.
- **Idea chips.** Trip, Party, Groceries and Move-in fill the prompt with an example to edit.
- **Pay $X.** On Progress, the Pay button opens pay mode with the items you claimed already chosen.
- **Share link** button on list pages.
- **Quantity and "who buys it"** moved behind a tap on the item name, so the list stays clean (design shows only name, subtitle and price).
- The phase 2 line on the phone home page ("Say what you need. Share who buys what. See what really got done.") was replaced by the design's text; the web home page has the design's description instead.

Unchanged: every API call, the backend, the database, the AI prompts, payments and the split math.

## 4. Files

| File | Change |
|---|---|
| `app/globals.css` | New colour tokens, the `glass` card style, the background gradient. Removed the old `--accent`, `--chip`, `--card` tokens and the `<progress>` styles (no longer used) |
| `app/ui.tsx` | **New.** Shared pieces: button, card, row, chip and field classes; `Brand`, `WebNav`, `Shell` (glows, web nav, page width), `Ring`, `Avatar`, `Check` |
| `app/recent.tsx` | **New.** `useSeenLists()`, `spent()`, `ListCard` (used by Home and History) |
| `app/layout.tsx` | Wraps every page in `Shell` |
| `app/page.tsx` | Home: "Your lists" and "Spent this month" |
| `app/starter.tsx` | Prompt card, mic, chips, budget from the sentence, the AI review screen |
| `app/lists/[id]/list-context.tsx` | List header, Share link, web pill tabs, phone tab bar, join card. Re-exports the shared classes |
| `app/lists/[id]/layout.tsx` | Page width now comes from `Shell` |
| `app/lists/[id]/page.tsx` | Progress layout (ring, stats, two lists, web side column) |
| `app/lists/[id]/items/page.tsx`, `receipts/page.tsx`, `app/receipt-scan.tsx`, `app/history/page.tsx` | Restyled with the shared pieces |
| `app/split.tsx` | `WhoPaid`, `SettleUp`, `EqualShare` (shared by Money and Settle up); `SplitPanel` removed |
| `app/lists/[id]/money/page.tsx`, `settle/page.tsx` | Built from those components |
| `public/ui/*.svg` | **New.** Figma assets: logo dot, sparkle, mic, check, arrow, three background glows |

## 5. Different from the design

| In the design | In the app | Why |
|---|---|---|
| "How it works" in the web nav | Not shown | No such page |
| "Hey Vic" greeting | Not shown | No accounts |
| "Leaving in 6 days" | Shows "N people · you are <name>" | Lists have no date |
| Item categories ("Gear · ×1") | Who buys it and the quantity ("Ben · ×2") | Items have no category |
| "8/12 packed" | "2/6 done" | "Packed" only fits trips; lists are general (decision 2) |
| Ring and bars | Drawn in code from the real numbers | They show live data, so they can't be fixed images |
| Done tick | As designed, but hard to see | The Figma check icon is dark on a dark circle (issue 40) |

All of these are in issue 41 (or 40).

## 6. Problems found while checking, and fixed

| Problem | Fix |
|---|---|
| The production build failed on list pages: the web nav reads the current address, which Next.js can't know while prerendering a list page (Cache Components) | Only the nav links wait for it, inside a Suspense boundary, as the bundled Next.js docs require (`app/ui.tsx`) |
| The home page read today's date while prerendering, so "Spent this month" would have used the build date | Moved into a component that only renders once the lists have loaded in the browser (`ThisMonth` in `app/page.tsx`) |
| The prompt card was wider than a phone screen, pushing History off the edge | The text box can shrink now (`min-w-0`) |
| Empty check circles showed as thin bars | The empty circle is a block element now |
| "Pay $15" showed before anyone had joined (unclaimed items counted as yours) | "Your items" needs you to have joined |
| The budget line wrapped on phones | Whole dollars without ".00" on that card, as in the design, kept on one line |

## 7. How it was checked

- `tsc` and `eslint` clean; production `next build` passes.
- Built and run against a small fake backend (one sample list, the real `money.split()`), so the live database was not touched. Screenshots at 390 px (phone) and 1440 px (web) of Home, AI review, Progress, Money and Settle up were compared with the Figma screens.
- **Not checked:** a real phone, the live backend, Items/Receipts/History against a design (they have none), and voice on a phone.

## 8. Still to do

- Try it on a real phone before recording the demo ([SUBMISSION.md](SUBMISSION.md)).
- Re-export the check icon in a lighter colour (issue 40).
- The dark "Midnight" theme: add its colours as a second set of the variables, with a switch (ROADMAP).
