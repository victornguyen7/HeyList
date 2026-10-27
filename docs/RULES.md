# HeyList — Rules for paid API keys

The Anthropic API key bills the owner's own money for every call. The AWS keys do the same for Textract, and the Ollama key uses the owner's Ollama plan. Claude is not called by the app for now (decision 38); the rules below still apply to the key in `.env.local`. These rules apply to everyone working on this project, people and AI coding assistants alike.

## 1. Anthropic's rules (from Anthropic's own pages)

Sources, checked 2026-10-15:
[API Key Best Practices](https://support.claude.com/en/articles/9767949-api-key-best-practices-keeping-your-keys-safe-and-secure) ·
[Authentication docs](https://platform.claude.com/docs/en/manage-claude/authentication) ·
[Commercial Terms of Service](https://www.anthropic.com/legal/commercial-terms) ·
[Usage Policy](https://www.anthropic.com/legal/aup)

**Keeping the key safe** (best-practices article and authentication docs)

- The key is like a credit card number: whoever has it can run up charges on the account.
- Don't share it with anyone, **including Anthropic**. Keep it out of public discussions, emails and support tickets. Anyone else who needs API access gets their own key.
- Never put it in code or config files that get committed. Accidental exposure in public repositories and third-party tools is one of the most common causes of leaks.
- On third-party tools (web IDEs, cloud hosts, CI), store it only as an encrypted secret. Putting it there gives that tool's maker access to it.
- Store keys in a secrets manager, rotate them periodically, and **disable or delete any key you suspect has leaked** (Disable can be undone; Delete is permanent).
- A key can be created with an expiration (3 hours to 30 days, a custom length, or never) to limit how long a leaked key stays usable. Expiration is set when the key is created and can't be changed.
- Regularly review the key's usage in the Claude Console.
- Prefer a personal key for your own development and a service account key for shared or automated workloads (such as a deployed server).

**Commercial Terms** (sections D.2, D.4, D.5)

- "Customer is responsible for all activity under its account". That includes every call made with a leaked key.
- Tell Anthropic promptly if you believe the account is compromised.
- Use the API only in compliance with the Terms and the **Usage Policy**.
- Don't use the API to build a competing product, train competing AI models, resell the API (unless Anthropic expressly approves), or reverse engineer or duplicate it.
- Powering your own product for your own users is allowed (section A.1). HeyList does this: Claude matches receipt lines for the app's users, who never see or use the key.

## 2. How this project applies them

**Where the key lives**

- Only in `.env.local` (local) and the hosting provider's encrypted environment variables (Render). `.env.local` is git-ignored (`.gitignore`: `.env*`); `.env.example` holds names only, never values.
- Server-side only. No code reads `ANTHROPIC_API_KEY` at the moment; when Claude comes back, only the backend may. Never give it a `NEXT_PUBLIC_` name, never send it to the browser, never return it from an API route.
- Never print, log, paste or screenshot it, including in terminal output, error messages, issues, docs, chat with an AI assistant, and support tickets. To check that it is set, check "set or empty", never the value or any part of it.

**What may spend money**

- `backend/eval_starter.py` makes one Ollama call per evaluation case (20 a run). It refuses to run without `--yes`; run it only when the owner has agreed, and report the result.
- Nothing calls Claude for now. Ollama does starting lists, receipt matching (`receipts.match_lines`) and, while Textract is unavailable, receipt reading (`receipts.read_with_ollama`).
- When Claude comes back: `claude-haiku-5-5`, the cheapest current model ($0.10 per million input tokens, $0.50 per million output tokens, under 100K-token prompts), low effort, bounded `max_tokens`. Don't switch to a larger model without the owner's agreement.
- A matching call takes at most 150 receipt lines and 300 list items, and is made only after lines were found and only when the list has open items.
- Paid routes are rate-limited: 10 receipt scans per list per hour and 20 starting lists per hour across all clients (`allow()` in `backend/main.py`; the backend sits behind proxies, so it can't safely tell clients apart). There are no accounts, so anyone with a list link could otherwise keep spending.

**Tests and development**

- Unit tests never call Ollama or Textract: they mock `llm.chat` and use botocore's `Stubber`. Running `python -m unittest` costs nothing.
- A real (paid) call is made only by hand, only when the owner has asked for it, and the token usage is reported back.
- AI coding assistants working on this repo follow the same rules: never read out, echo or copy the key, and ask before any paid call.

**Owner's checklist (Claude Console)**

- Set a monthly spend limit for the workspace, and keep credit low enough that a leak can't cost much.
- Create the key with an expiration, and use a separate key for the deployed server (a service account key) from your own development key.
- Look at usage now and then; an unexpected rise means a leak or a bug.

## 3. If the key leaks

1. Disable or delete it in the Claude Console at once (API keys page), then create a new one.
2. Put the new key in `.env.local` and Render's environment; never in a file that is committed.
3. If it reached git, removing the commit is not enough: the key is already exposed, so step 1 is what protects you.
4. Check usage in the Console for calls you didn't make, and tell Anthropic if you believe the account was compromised (Commercial Terms D.5).

## 4. AWS keys (Textract)

The same handling applies to `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. In addition, the IAM user for this app should have only the permission it needs, `textract:AnalyzeExpense`, and nothing else. A leaked key with broad permissions could run up charges on any AWS service.
