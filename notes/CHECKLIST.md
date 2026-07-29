# CHECKLIST.md

Фінальна перевірка перед подачею. Кожен пункт — або `[x]`, або пояснення чому ні.

Оновлено: Фаза 5 (2026-07-29).

---

## L. LaTeX / збірка

- [x] L1. Збірка **тільки `pdflatex`** (двічі) — Фаза 1/5
- [x] L2. У `.log` немає `Undefined control sequence`
- [x] L3. У `.log` немає `Citation ... undefined`
- [x] L4. У `.log` немає `Reference ... undefined`
- [x] L5. Немає `Overfull \hbox` > 10 pt (Фаза 5)
- [x] L6. Немає `\TODO` у `numbers.tex` / секціях / PDF (єдиний був `peniak2026a` — закрито як accepted)
- [x] L7. Немає заглушок `\rule{...}{...}`
- [x] L8. Рисунки: `fig_confounding`, `fig_roc`, `fig_window` + `tab:results`
- [x] L9. Обсяг: **10 EN+refs + 1 UKR = 11 PDF**

## R. Джерела

- [x] R1. ≥ 25 джерел (27 `\bibitem`)
- [x] R2. Кожен `\bibitem` цитований ≥1 раз (27/27)
- [x] R3. Кожен запис має `\url{...}` (DOI та/або відкритий PDF/arXiv/hdl); перевірено GET
      для відкритих URL; ACM/IEEE DOI лишаються канонічними `https://doi.org/...`
- [x] R4. Немає `Vol.x, No.x` шаблонів
- [x] R5. `peniak2026a` — MMC accepted/to appear + URL журналу (том/сторінки після виходу);
      `peniak2026b` — **49**(2), 255--261, DOI `10.24144/2616-7700.2026.49(2).255-261`
- [x] R6. Трансліт `Peniak` / `Liubinskyj` узгоджений
- [x] R7. Немає дубльованих джерел

## S. Структура

- [x] S1. Немає дубльованих заголовків секцій (7 унікальних)
- [x] S2. Один блок Limitations (`06_case_study.tex` §6.1)
- [x] S3. Перехресні посилання без undefined (Фаза 5 compile)
- [x] S4. Одна таблиця (`tab:results`)
- [x] S5. Рисунки 1–3 послідовно
- [x] S6. Усі fig/tab згадані в тексті

## M. Математика

- [x] M1. Thm.1 і Thm.2 мають Proof; Statement/Lemma теж
- [x] M2. Assumptions (separable, rho) — у Limitations
- [x] M3. Немає non-sequitur α=+0.5 з n^(−2)
- [x] M4. β>0 = спадання TPS з n (експліцитно)
- [x] M5. Ключові позначення введені в §3–4
- [x] M6. `\cc` для concurrency
- [x] M7. `neff = kf w / (1+(kf−1)ρ)` у `st:rho` (design effect на faulty subset)
- [x] M8. Thm.window спирається на lem:detequiv + st:rho

## N. Числа

- [x] N1. Числа через `numbers.tex`
- [x] N2. Перегенерований (`\resCoreHours=27.2`)
- [x] N3. Abstract якісний (без hardcode); діапазон через `\resNmaxMeasured`
- [x] N4. Conclusions узгоджені з результатами (без суперечливих чисел)
- [x] N5. `\resNmaxMeasured=16`

## H. Чесність

- [x] H1. Клас відмов: omission (+ duplication) — §4 Def, §5, §6 Limitations
- [x] H2. Зашифрований транспорт / не-equivocation — Limitations
- [x] H3. X6 явно «simulation… not as a measurement»
- [x] H4. Absolute TPS виключені (intro Scope + Limitations)
- [x] H5. Розбіжність статей 1/2 через Thm.1
- [x] H6. Нейтрально («including our own» / earlier studies)
- [x] H7. Remark про e-voting + springall/specter/park

## D. Дані та відтворюваність

- [x] D1. https://github.com/bpenyak/Resource_Normalized_Scaling_Laws_for_Byzantine_Consensus — у Data availability
- [x] D2. `data/raw/` — 134 JSON (94 ok)
- [x] D3. `make analyze` + `CORE_HOURS=` для emit (Makefile оновлено)
- [x] D4. `experiments/requirements.txt` існує
- [x] D5. `.github/workflows/experiment.yml`

## SEC. Безпека

- [x] SEC1. Немає реальних ключів (DEV_SEED у gen_network)
- [x] SEC2. Dev/test ключі явно позначені
- [x] SEC3. `.gitignore` виключає `*.key`, raw keys
- [x] SEC4. RPC на loopback у workflow / compose
- [x] SEC5. Немає секретів у коді workflow

## U. Українська частина

- [x] U1. `\abstractUkr` стиснуто й узгоджено з EN (вичитка носієм — бажана перед подачею)
- [x] U2. keywordsUkr ↔ keywords
- [x] U3. udkUkr = udk
- [x] U4. Пеняк / Любінський ↔ Peniak / Liubinskyj
- [x] U5. `\maketitleUkr` після бібліографії

## A. Метадані

- [x] A1. MSC 68M14, 68W20, 90C15, 62J02
- [x] A2. UDC 004.75:519.2
- [x] A3. `\received{29 July 2026}`
- [x] A4. Афіліація LPNU + email
- [x] A5. Conflict / Funding / Data / AI / Contributions заповнені
