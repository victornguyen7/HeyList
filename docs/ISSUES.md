# HeyList — Issues

## Open

| # | Issue | Notes |
|---|---|---|
| 1 | App is still the default `create-next-app` scaffold | `app/page.tsx` and the page title in `app/layout.tsx` are the template defaults |
| 2 | Frontend has none of the planned stack yet | `backend/requirements.txt` covers PayPal, Supabase, and Ollama, but `package.json` has no Supabase client or PayPal Checkout JS SDK |
| 3 | The LLM API key was written in plain text in the project notes | Keep it out of the repo: load it from an environment variable, and rotate the key if the notes were shared |
| 4 | `backend/__pycache__/` was committed in `4a2b88f` | `.gitignore` only affects untracked files. Fix is staged (`git rm -r --cached backend/__pycache__`); closes once committed |
| 5 | PayPal amounts must be strings, not cents | Orders need `{"currency_code": "USD", "value": "23.98"}`. Convert without floats: `f"{c // 100}.{c % 100:02d}"`. Currency isn't set anywhere yet; USD likely for the sandbox |
| 6 | No way to buy two of the same item | `total_cents` rejects duplicate IDs. Fine for packing lists; if quantity is added later, the selection becomes `{id: qty}` |
| 7 | Small cleanups in `backend/sample_list.py` | Test file is `test_simple_list.py` but the module is `sample_list.py`; no newline at end of file; `priceCents` is camelCase (fine if it matches the frontend JSON) |

## Closed

None yet.
