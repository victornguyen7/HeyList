# HeyList — Decisions

Decisions recorded in the project notes. A reason is listed only where the notes give one.

| # | Decision | Reason |
|---|---|---|
| 1 | Build a website, mobile-first, rather than a native app (native app later) | Works in a phone browser with nothing to install |
| 2 | Keep the app general-purpose; packing before a holiday is only the first use case | It should fit groceries, errands, routines, and any other daily list |
| 3 | Keep the app neutral, for daily use by many groups, not tied to companies | Tested by trying it with three very different users: student, busy parent, older relative |
| 4 | Three ways to work with a list — type, voice, photo | Users pick whichever is easiest at that moment |
| 5 | Voice and photo results are shown to the user to confirm before they apply | — |
| 6 | Sharing is by link, with no account needed to view or check items | Sharing in existing apps usually requires everyone to have an account |
| 7 | Simple interface: large text, few screens, one big talk button, advanced options hidden | Must work for first-time smartphone users |
| 8 | A PayPal order counts as proof of purchase | No receipt scan needed when buying in the app |
| 9 | Settle-up on shared lists uses PayPal invoices | — |
| 10 | Split math, budget totals, and assignment of unclaimed items are done in code, not by AI | — |
| 11 | Use one LLM with vision for both lists and receipts | — |
| 12 | Use the Ollama API for the LLM | — |
| 13 | Use the Web Speech API for voice | — |
| 14 | Use Next.js for the app | — |
| 15 | Use Supabase for lists, receipts storage, and realtime | — |
| 16 | Deploy on Render | Hackathon sponsor; $50 credit received |
| 17 | Use the PayPal sandbox: Checkout JS SDK + Orders API, Invoicing API | — |
| 18 | Use sponsor tools APIMatic Context Plugin, Postman, and Render; Channel3 only as a stretch | — |
| 19 | History is the retention hook: buy again from a past list, plus price memory | — |
