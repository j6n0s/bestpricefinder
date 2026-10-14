# Brief for a local agent: capture the GVH and KSH samples the cloud build cannot reach

**Who this is for:** a Claude Code session on the user's own computer, which can reach the internet without the cloud container's network policy.
**Written by:** the cloud agent, 2026-10-13. It answers the request in [QUESTIONS.md](QUESTIONS.md) ("REQUEST: raw GVH fixture samples").

## What to paste into the local session

> Clone https://github.com/j6n0s/bestpricefinder and switch to the branch `claude/practical-newton-fdz8jp`. Read `AGENTS.md`, then do everything in `docs/LOCAL_AGENT.md`, Part A. Ask me for the contact e-mail to send in the User-Agent. Don't do Part B unless I ask.

**Part A was done on 2026-10-14.** For the small follow-up (Part C), paste this instead:

> In your clone of https://github.com/j6n0s/bestpricefinder, run `git switch claude/practical-newton-fdz8jp && git pull --no-rebase`. Read `AGENTS.md`, then do `docs/LOCAL_AGENT.md`, Part C. Ask me for the contact e-mail.

## Why this is needed

The app takes its prices from GVH Árfigyelő. The cloud agent builds and tests it, but its container cannot reach these three hosts (the egress proxy answers 403):

- `arfigyelo.gvh.hu` (the JSON API)
- `cdnarfigyeloprodweu.azureedge.net` (the daily XLSX)
- `www.ksh.hu` (the KSH ara0044 average-price table)

So far the GVH parsers have been built from documented field lists and a fake server, not from real responses ([server/bpf/gvh/ASSUMPTIONS.md](../server/bpf/gvh/ASSUMPTIONS.md)). Your job is to fetch a small set of **real, unmodified** responses once and commit them. The cloud agent then checks every parser against them.

A ready capture tool does the fetching, so nothing needs to be improvised: [server/tools/capture_gvh_samples.py](../server/tools/capture_gvh_samples.py). It was tested against the fake GVH server in [server/tests/test_capture_tool.py](../server/tests/test_capture_tool.py).

## Rules (binding; from AGENTS.md and BUILD-BRIEF §8)

1. **Work only on the branch `claude/practical-newton-fdz8jp`.** Never push to `main`. Never force-push. Stage explicit paths only (no `git add -A` or `git add .`).
2. **Add only the sample files and one QUESTIONS.md entry.** The samples go in `server/tests/fixtures/gvh/raw/` and `data/ksh/raw/`. Change nothing else in `server/`, `web/`, `deploy/` or `data/`: the cloud agent owns them. Don't "fix" a sample or a parser so that a test passes. A failing test is the information we need.
3. **Be polite to the sources.** Run the tool once. It waits ≥1.2 s between requests and sends about 20–35 in total. It stops by itself at the first 403, 429 or 5xx. Don't rerun it in a loop or retry: report the stop instead.
4. **Fetch nothing else.** Fetch nothing from Kifli, Tesco, Spar, Wolt, foodora or Auchan websites (no scraping), and download no product images or logos.
5. **Commit no secrets:** no `.env` files, keys, cookies, database dumps or `pgdata/`. The tool keeps no cookies or `Set-Cookie` headers.
6. **Use the user's own contact e-mail in the User-Agent.** Ask the user for it, and don't commit it anywhere else.

## Part A: capture the samples (about 10 minutes)

### A1. Get the code and the tools

You need `git` and `uv` (<https://docs.astral.sh/uv/>; on macOS `brew install uv`). `uv` downloads Python 3.14 by itself.

```sh
git clone https://github.com/j6n0s/bestpricefinder.git
cd bestpricefinder
git switch claude/practical-newton-fdz8jp
cd server
uv sync
uv run pytest tests/test_capture_tool.py -q   # all must pass: the tool works on this machine
```

The commands are for macOS/Linux. On Windows use WSL, or PowerShell with the same `uv` commands.

### A2. Run the capture once

Run this from `server/`, with the e-mail the user gave you:

```sh
uv run python tools/capture_gvh_samples.py --contact THE_USERS_EMAIL
```

It writes:

| Where | What |
| --- | --- |
| `server/tests/fixtures/gvh/raw/<name>.json` + `<name>.meta.json` | one API response per call, as received (`shops-head` keeps the first 40 shops; the full count is in its meta) |
| `server/tests/fixtures/gvh/raw/xlsx-sample.xlsx` + `xlsx-sample.meta.json` | today's daily XLSX cut down to the header + 150 rows, with the sheet name and cell types unchanged |
| `server/tests/fixtures/gvh/raw/capture-report.txt` | one line per item (status, size) |
| `data/ksh/raw/ara0044.csv` + `ara0044.csv.meta.json` | the KSH table exactly as downloaded |

**Expected output:** 15 API lines, fewer if one is skipped (`categories`, `chain-stores`, `shops-head`, `pbc-18-o0`, `pbc-18-last`, `pbc-18-default`, `pbc-18-shops`, `pbc-40-o0`, `pbc-7-o0`, `product-2804780000000`, `product-5997490112823`, `product-multichain`, `product-shop-ok`, `product-shop-notfound`, `search-400`), then the XLSX and the KSH file. The statuses should be:

- **HTTP 400** for `search-400` (intended);
- probably **HTTP 404** for `product-shop-notfound` (intended);
- **HTTP 200** for everything else.

**If something goes wrong:**

- **The tool stops with `STOPPED: … answered HTTP 403/429/5xx`:** the source refused or is down. Don't retry the same day, and don't commit the partial samples. Tell the user, write the A4 entry, and commit **only** `docs/QUESTIONS.md`. The files written up to that point are listed in `capture-report.txt`.
- **A body that is an HTML page instead of JSON:** stop and report it in A4 instead of retrying.
- **A "(skipped)" line:** fine, but mention it in A4.
- **The KSH step prints `WARNING: not the data file`:** open <https://www.ksh.hu/stadat_files/ara/hu/ara0044.html> in a browser and download the table's CSV once. Put the CSV in `data/ksh/raw/` next to a `.meta.json` with the URL and the date (same format as the one the tool wrote), and delete the wrong file.

### A3. Check the samples against the parsers

Run this from `server/`:

```sh
uv run pytest tests/test_gvh_fixtures.py -v
```

The `test_raw_*` tests now run on the real samples:

- `test_raw_sample_parses[...]` failing means a shape assumption is wrong.
- `test_raw_sample_has_no_unknown_fields[...]` failing means the real API sends fields we don't declare yet.
- `test_raw_xlsx_sample_parses_without_drift` failing means the XLSX columns differ.

**Don't fix anything.** Copy each failing test's name and the first lines of its error into A4.

Before committing, quickly look over the files:

- they are public price and store data only, with no personal data;
- no file is over 1 MB (`du -sh tests/fixtures/gvh/raw ../data/ksh/raw`);
- the `.meta.json` files hold no cookies.

### A4. Report and push

Append an entry at the bottom of `docs/QUESTIONS.md`, in this form:

```markdown
## 2026-MM-DD — local session — raw GVH/KSH samples captured
- Captured with server/tools/capture_gvh_samples.py at <time, Europe/Budapest>; statuses: <from capture-report.txt, one line>
- XLSX: sheet "<name>", <original_data_rows> rows, Last-Modified <…>
- KSH: <file name, size; or "downloaded by hand because …">
- tests/test_gvh_fixtures.py: <N passed / M failed>; failures: <test name — first error line>, …
- Anything surprising (redirects, rate limits, a shape different from BUILD-BRIEF §4.1): …
```

Then commit and push. Run this from the repository root:

```sh
git add server/tests/fixtures/gvh/raw data/ksh/raw docs/QUESTIONS.md
git status --short            # only those paths should be staged
git commit -m "Add real GVH and KSH samples captured on <date> (fixture request in QUESTIONS.md)"
git pull --no-rebase origin claude/practical-newton-fdz8jp   # the cloud agent may have pushed meanwhile
git push origin claude/practical-newton-fdz8jp
```

If the pull reports a conflict in `docs/QUESTIONS.md`, keep both sides' entries.

Tell the user it is done. They relay it to the cloud session, which will:

- update ASSUMPTIONS.md and fix the parsers if needed;
- convert the KSH file (`python -m bpf.content --convert-ksh … --ksh-format stadat`);
- run the whole test suite again.

## Part B (optional, only if the user asks): run the app on this machine

This checks what the cloud cannot: PostgreSQL 18 and (on a Mac) the macOS paths, with a real ingest.

1. Follow [RUNNING.md](RUNNING.md) sections 1–8 exactly. Skip §9–§11 (HTTPS, schedule, backups) unless the user wants the app running permanently.
2. The first ingest (§6) is a real run against GVH. It is rate-limited by the app itself, so let it finish and don't start it twice.
3. Then run the full-stack tests from [E2E.md](E2E.md) if Node.js is installed: `cd web && npm ci && npm run test:fullstack`.
4. Report in a new QUESTIONS.md entry:
   - OS and version, `postgres --version`, `node --version`;
   - each step that failed, with its exact error;
   - the counts that `deploy/local/doctor.sh` prints.

   Commit only that entry, and only if something needs fixing. Never commit `.env`, `pg-admin.env`, the backup key (it belongs in `~/.config/bestpricefinder/`, outside the repository), `.data/`, `pgdata/`, `backups/` or `log/`.

## Part C: the follow-up capture (2026-10-14; about 2 minutes)

Part A worked. Every parser has since been fixed against your samples, and the tool now reads the wrapped reference bodies (`{"shops": […]}`) correctly. Two samples are still missing:

- **`product-shop-ok`:** the per-store prices of one product. The tool could not find a Budapest Tesco store in the wrapped `/shops` body.
- **`product-multichain`:** a product sold by at least 4 chains. The tool now picks one from the XLSX column "Hány üzletláncban elérhető".

Same rules as above. From `server/`:

```sh
uv sync
uv run pytest tests/test_capture_tool.py -q   # all must pass
uv run python tools/capture_gvh_samples.py --contact THE_USERS_EMAIL --only product-shop-ok,product-multichain
uv run pytest tests/test_gvh_fixtures.py -v
```

**What the run does:**

- **Requests:** about 5 to 20 requests at most, one per 1.2 s: the XLSX once (read for the candidates, not saved), `/shops`, the detail of product 2804780000000, up to 15 candidate details, and the per-store prices.
- **Files it rewrites:**
  - `shops-head.json`, now cut to the first 40 shops as originally intended;
  - `product-2804780000000.json`, refreshed.
- **Files it adds:** `product-multichain.json` and `product-shop-ok.json`.

**What to report and push:** report in a new QUESTIONS.md entry, in the same form as A4. Then commit only these paths, and pull before you push:

- `server/tests/fixtures/gvh/raw`
- `docs/QUESTIONS.md`

**If something goes wrong:**

- **The tool stops with `STOPPED`:** follow A2.
- **A `(skipped)` line:** report it. Don't retry with other products by hand.
