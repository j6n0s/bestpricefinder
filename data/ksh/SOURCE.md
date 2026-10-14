# Source of `ara0044.csv` (KSH national average prices)

- **Table:** KSH STADAT ara0044, "Egyes termékek és szolgáltatások fogyasztói átlagára (nyers adatok), havonta", <https://www.ksh.hu/stadat_files/ara/hu/ara0044.html>.
- **Licence:** CC BY 4.0 (<https://www.ksh.hu/copyright>). Attribution, required wherever a value is shown: "Forrás: KSH" with a link to <https://www.ksh.hu/stadat_files/ara/hu/ara0044.html>.
- **Use in the app:** "becsült országos átlagár (KSH)", a monthly national average. Never show it as a store price.
- **Converted from:** `data/ksh/raw/ara0044.csv`, the original file downloaded from <https://www.ksh.hu/stadat_files/ara/hu/ara0044.csv>.
- **Input sha256:** `506df2082faa372bb2f8e3774aff1b5d9867edd87b8c99bc39fddb7eab61976e`
- **Input format:** stadat (iso-8859-2 (with windows-1250 punctuation))
- **Fetched:** 2026-10-14
- **Command:** `python -m bpf.content --convert-ksh data/ksh/raw/ara0044.csv --ksh-format stadat --ksh-fetched 2026-10-14 --ksh-url https://www.ksh.hu/stadat_files/ara/hu/ara0044.csv`
- **Rows:** 61 food rows kept; 6 food rows dropped (listed below); 108 non-food rows dropped.
- **Periods:** 2026-07-01, 2026-09-01 (each row carries the month of its latest published value).

## Conversion rules

- Food rows only: codes 10000–15999. Catering (16xxx), drinks and coffee (17xxx), alcohol (18xxx), tobacco (19xxx) and every non-food group are dropped.
- The unit is the last comma-separated part of the item text: `kg`; `liter` → `l`; `db`/`darab` → `db`, with an optional leading count as `unit_qty` ("Tojás, 10 darab" → `db`, 10); "1 kg-ra számítva" → `kg`. A footnote marker glued to the unit is stripped ("kga" → `kg`, "dbj" → `db`). Rows whose unit is a package (`csomag`, `doboz`, `palack`…) or missing are dropped.
- `price` is HUF for `unit_qty` × `unit`. The database table `app.ksh_price` has no `unit_qty` column, so the loader stores `price / unit_qty` per one unit (eggs: 814 Ft / 10 db → 81.40 Ft/db).

## Dropped food rows

| code | item | reason |
|---|---|---|
| 12101 | Sertészsír, 400–500 g (kivéve mangalica) | unit cannot be normalised to kg, l or db |
| 13801 | Háztartási keksz, csomagolt 800–1000 g, csomag | unit cannot be normalised to kg, l or db |
| 14310 | Dobozos narancslé, 100%-os gyümölcstartalom, 1 l, doboz | unit cannot be normalised to kg, l or db |
| 14425 | Csemegekukorica-konzerv, doboz | unit cannot be normalised to kg, l or db |
| 15101 | Hasábburgonya, gyorsfagyasztott, félkész, 750–1000 g, csomag | unit cannot be normalised to kg, l or db |
| 15201 | Bors, fekete, őrölt, 16–25 g, csomag | unit cannot be normalised to kg, l or db |
