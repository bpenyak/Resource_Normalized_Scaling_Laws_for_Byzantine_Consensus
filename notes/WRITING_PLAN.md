# WRITING_PLAN.md

Покроковий план написання статті 3.
Кожна фаза має **вхід**, **дію**, **вихід** і **критерій завершення**.
До наступної фази не переходити, поки критерій не виконано.

---

## Загальні правила

| Правило | Пояснення |
|---|---|
| R1 | Мова тексту статті — **англійська**. Українська — тільки `\abstractUkr` у `paper3.tex`. |
| R2 | **Жодне числове значення не пишеться руками в `.tex`.** Усі числа — через макроси з `numbers.tex`, який генерується скриптом `experiments/analysis/emit_numbers_tex.py`. |
| R3 | Компіляція — **тільки `pdflatex`** (MMC.sty використовує `[T2A]{fontenc}` + `babel`). НЕ xelatex, НЕ lualatex. |
| R4 | Бібліографія — **вручну** через `\bibitem` у `bib/references.tex`. MMC.sty перевизначає `thebibliography`. bibtex/biblatex НЕ використовувати. |
| R5 | Ліміт — **10 сторінок A4**. Після кожної фази перевіряти обсяг (див. `PAGE_BUDGET.md`). |
| R6 | Кожне твердження про новизну має відповідати рядку в `NOVELTY_CLAIMS.md`. |
| R7 | Нічого, що не було виміряно, не подається як виміряне. Невиміряне → `\TODO{}` або розділ Limitations. |
| R8 | Після **будь-якої** зміни тексту/макросів/бібліографії/рисунків статті — одразу синхронізувати `overleaf_files/` (ті самі відносні шляхи) і перезібрати `overleaf_files.zip`. |

---

## Фаза 0. Підготовка (ГОТОВО)

**Вхід:** `MMC.sty`, дві опубліковані статті, план дисертації.

**Дії:**
- [x] Створено структуру `paper_3/`
- [x] `paper3.tex` — преамбула, EN/UKR метадані
- [x] `macros.tex` — нотація
- [x] `numbers.tex` — плейсхолдери `\TODO{}`
- [x] `sections/01..07` — повний текст із твердженнями (згодом оформлені як Proposition; злито з 12 до 7 секцій у «Cutting paper»)
- [x] `bib/references.tex` — 27 джерел (скорочено з 36 при злитті)

**Критерій:** `pdflatex paper3.tex` проходить без помилок (з `\TODO` мітками).

---

## Фаза 1. Валідація каркаса (ГОТОВО з зауваженням щодо обсягу)

**Дія:**
```powershell
cd c:\pol\paper_3
# pdflatex з MiKTeX: %LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64
pdflatex -interaction=nonstopmode paper3.tex
pdflatex -interaction=nonstopmode paper3.tex   # для перехресних посилань
```

**Перевірити:**
- [x] Немає `Undefined control sequence` (exit 0, 0× `!` у `.log`)
- [x] Немає `Citation ... undefined` (усі ключі з секцій є в `bib/references.tex`)
- [x] Немає `Reference ... undefined` (усі `\ref` мають `\label`)
- [x] Обсяг ≤ 10 сторінок — після Фази 3 було 15 PDF; виконано у Фазі 5
  (скорочення за `PAGE_BUDGET.md`), поточний стан: **10 EN+refs + 1 UKR = 11 PDF**.

**Виправлення під час фази 1 (у `macros.tex`):**
- `\renewcommand` для `\Prob`/`\Var` (конфлікт із `babel-russian`)
- `\zq` → символ `z` (текст пише `\zq_{...}`, не `\zq{...}`)
- math-safe `\TODO` (MMC `\marginpar` ламається в `$...$`)
- патч `\Ukrainian` (баг `babel-ukrainian` 1.5a: `\selectlanguage{\ukrainian}`)
- дрібне: `$-\zq_{1-\epsp}\hat{V}^{1/2}$` у доведенні леми

**Критерій:** чистий `.log`, PDF згенеровано — **виконано**.
Обсяг ≤ 10 — **відкрито**; блокує подачу, не блокує перехід до Фази 2
(експерименти не залежать від подальшого скорочення тексту).

---

## Фаза 2. Постановка експериментів (ГОТОВО)

**Вхід:** `notes/EXPERIMENT_PROTOCOL.md`, код у `experiments/`.

**Дії:**
1. [x] Публічний GitHub-репозиторій: https://github.com/bpenyak/Resource_Normalized_Scaling_Laws_for_Byzantine_Consensus
2. [x] Workflow: `.github/workflows/experiment.yml` (+ SMOKE у `matrix.yaml`)
3. [x] Smoke-тест на CI: status=`ok`, TPS≈35.3
4. [x] Повна матриця: run https://github.com/bpenyak/Resource_Normalized_Scaling_Laws_for_Byzantine_Consensus/actions/runs/30359901702
   (137 measure jobs; workflow `failure` через X9 + aggregate, але артефакти збережені)
5. [x] Артефакти завантажені: `gh run download 30359901702`
6. [x] `data/raw/`: спочатку 130 JSON; зараз **134 JSON** (94 ok, 40 fail; X9 = 0/24)

**Критерій:** `data/raw/` містить ≥ 80 JSON — **виконано**.

---

## Фаза 3. Аналіз і генерація чисел (ГОТОВО)

**Дії:**
```powershell
python experiments/analysis/fit_bifactor.py   --in data/raw --out data/processed
python experiments/analysis/bootstrap_pi.py   --in data/processed --out data/processed
python experiments/analysis/sizing.py         --in data/processed --out data/processed
python experiments/analysis/make_figures.py   --in data/processed --out figures
python experiments/analysis/emit_numbers_tex.py --in data/processed --out numbers.tex --core-hours 27.2
```

**Критерій:** у `numbers.tex` не лишилося жодного `\TODO` — **виконано**
(`\resCoreHours=27.2` з Σ `wall_seconds`×4 vCPU / 3600 по ok-прогонах).

**Артефакти:** `data/processed/` (fit, coverage, qinvariance, sizing, …),
`figures/` (5 PDF: bifactor, confounding, roc, sensitivity, window),
`numbers.tex` без плейсхолдерів.

**Ключові числа (поточні):**
β=1.651±0.151, γ=0.178±0.070, R²=0.727;
q-інваріантність відхилена (p=0.002); AUC=0.506;
вікно sizing `[4,4]`, n*=4, κ=13.0 (ядер на валідатор); coverage 90.9% / 95.5%; n_max=16; 94 ok runs.

---

## Фаза 4. Наповнення тексту результатами (ГОТОВО)

> **Структура:** `01`–`07` (після «Cutting paper»).
> Коміт `cb9109a` уже синхронізував sizing/experiments/case study/conclusions
> з виміряними результатами.

**Статус по секціях:**

| Секція | Статус |
|---|---|
| `05_experiments.tex` | [x] `fig_confounding` активний; `tab:results` з макросів; q-інваріантність інтерпретована |
| `06_case_study.tex` | [x] `fig_window` активний; вікно `[4,4]` (непорожнє, вироджене); Limitations з X9/q-inv/AUC |
| `04_sizing.tex` | [x] узгоджено з κ-scale-up у коміті `cb9109a` |
| `07_conclusions.tex` | [x] оновлено в `cb9109a` |
| `01_introduction.tex` | [x] Contributions узгоджені з числами (якісні формулювання; числа через макроси) |
| `paper3.tex` abstract | [x] фіналізовано; єдине число — `AUC=\resAuc` через макрос |

**Критерій:** немає `\TODO` / `\rule{}`-заглушок у секціях — **виконано**.
Залишок Фази 4 закрито у Фазах 5–6.

---

## Фаза 5. Фінальне вичитування (ГОТОВО)

**Чеклист:** `notes/CHECKLIST.md` — пройдено 2026-07-29.

Ключове:
- [x] Обсяг ≤ 10 сторінок EN+refs
- [x] ≥ 25 джерел, усі цитовані; кожне з `\url{...}`
- [x] Немає дубльованих заголовків / Limitations
- [x] Немає шаблонів `Vol.x` / `\received{xx…}`
- [x] `peniak2026b` DOI + стор. 255--261; `peniak2026a` accepted + URL MMC
- [x] Клас відмов — omission + duplication
- [x] Data availability → https://github.com/bpenyak/Resource_Normalized_Scaling_Laws_for_Byzantine_Consensus

**Залишок перед подачею (людина):** вичитати `\abstractUkr` носієм; підставити том/сторінки `peniak2026a` після виходу.

---

## Фаза 6. Рецензентські ревізії (версії 13–16, ГОТОВО)

Коміти `ea8d874` (v13) … `327e676` (v16). Що змінилося відносно Фази 5:

- Наратив зміщено до **інженерного планування потужності**: what-if сценарії A/B/C
  у `06_case_study.tex`, масштаб `κ` (`\kappaScale`) як вимога до апаратури
  (`\resKappa`, `\resKappaDoubled`, `\resKappaWan`).
- Теореми перейменовано на **Proposition** (`prop:identifiability`, `prop:window`);
  `Algorithm 2` більше немає — задача формулюється як `Problem~\ref{prob:sizing}`.
- Детектор X5 (13 прогонів із відмовами та ROC) **близький до випадкового**
  (AUC=0.506): детекційне обмеження послаблено (не застосовується), вікно
  `[4,4]` задає лише пропускна здатність; «trade-off formulated, not demonstrated».
- `q`-інваріантність **відхилена** (p=0.002): β стабільний за фіксованого `q`,
  але залежить від його рівня; коефіцієнти звітуються при `q=0.25`.
- Додано X4 (β за RTT), порівняння моделей (log-RMSE), локальні β по піддіапазонах
  n, refit на `n≤9`; бібліографія — 29 джерел.
- Правило R2 посилено: `[\resNminCase,\resNmaxCase]`, `\resNminCase`,
  `\resDetectorThr` замість вписаних вручну `[4,4]`, `4`, `0.90`.
- Перелік літератури вкладено в 10 стор.: прибрано дублювання URL у
  Reproducibility та arXiv/ePrint-дзеркала записів, що мають DOI.
- Додано `ukr/` (повна укр. версія) і `tezu/` (тези); `numbers.tex` і `macros.tex`
  у `ukr/` копіюються з кореня.

---

## Порядок написання (якщо переписувати з нуля)

Порядок **не** збігається з порядком секцій (після злиття — 7 секцій):

1. `03_model.tex` — RNM + bi-factor + теорема ідентифікованості (ядро новизни)
2. `04_sizing.tex` — PI + detection + теорема про вікно
3. `05_experiments.tex` — дизайн і результати
4. `06_case_study.tex` — case study + limitations
5. `02_related_work.tex` — після того як внесок відомий
6. `01_introduction.tex`
7. `07_conclusions.tex`
8. `\abstract` / `\abstractUkr` у `paper3.tex` — **найостанніші**

---

## Поточний стан (після Фаз 3–6)

| Параметр | Значення |
|---|---|
| `data/raw/` | **134 JSON** (94 ok, 40 fail) |
| Успішні: X1 | 19/21 |
| Успішні: X2 | 20/27 |
| Успішні: X3 | 19/21 |
| Успішні: X4 | 18/20 |
| Успішні: X5 | **17**/24 (+ rerun у `artifacts/x5_rerun`); з них 13 прогонів із відмовами мають ROC (`\resDetRuns`) |
| Успішні: X9 | **0/24** (Quorum path не реалізований) |
| n_max measured | **16** |
| `data/processed/` | заповнений (fit/coverage/sizing/…) |
| `figures/` | 5 PDF |
| `numbers.tex` | **0 `\TODO`** (`\resCoreHours=27.2`) |
| `paper3.pdf` | **11 стор.** (10 EN+refs + 1 UKR; ліміт виконано) |
| Рисунки в тексті | `fig_confounding`, `fig_roc`, `fig_window` (+ `tab:results`) |
| Бібліографія | **29** `\bibitem`, усі цитовані |
| HEAD | `327e676` (v16) + узгодження макросів/обсягу (Фаза 6) |

**Наступний крок:** людська вичитка `\abstractUkr` + том/сторінки `peniak2026a` після публікації → подача.
