# AGENT_WRITING_PLAN.md

Покроковий план написання статті 3 за допомогою ШІ-агента.
Кожна фаза має **вхід**, **дію**, **вихід** і **критерій завершення**.
Агент не переходить до наступної фази, поки критерій не виконано.

---

## Загальні правила для агента

| Правило | Пояснення |
|---|---|
| R1 | Мова тексту статті — **англійська**. Українська — тільки `\abstractUkr` у `paper3.tex`. |
| R2 | **Жодне числове значення не пишеться руками в `.tex`.** Усі числа — через макроси з `numbers.tex`, який генерується скриптом `experiments/analysis/emit_numbers_tex.py`. |
| R3 | Компіляція — **тільки `pdflatex`** (MMC.sty використовує `[T2A]{fontenc}` + `babel`). НЕ xelatex, НЕ lualatex. |
| R4 | Бібліографія — **вручну** через `\bibitem` у `bib/references.tex`. MMC.sty перевизначає `thebibliography`. bibtex/biblatex НЕ використовувати. |
| R5 | Ліміт — **10 сторінок A4**. Після кожної фази перевіряти обсяг (див. `PAGE_BUDGET.md`). |
| R6 | Кожне твердження про новизну має відповідати рядку в `NOVELTY_CLAIMS.md`. |
| R7 | Нічого, що не було виміряно, не подається як виміряне. Невиміряне → `\TODO{}` або розділ Limitations. |

---

## Фаза 0. Підготовка (ГОТОВО)

**Вхід:** `MMC.sty`, дві опубліковані статті, план дисертації.

**Дії:**
- [x] Створено структуру `paper_3/`
- [x] `paper3.tex` — преамбула, EN/UKR метадані
- [x] `macros.tex` — нотація
- [x] `numbers.tex` — плейсхолдери `\TODO{}`
- [x] `sections/01..12` — повний текст із теоремами
- [x] `bib/references.tex` — 36 джерел

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
- [ ] Обсяг ≤ 10 сторінок — **НЕ виконано**: 14 PDF-сторінок
  (= 11 EN тіло+висновки + 2 бібліографія + 1 UKR-титул).
  Без заглушок рисунків обсяг той самий → проблема в тексті, не у figures.
  Потрібне додаткове скорочення ≈ 3 стор. EN+refs (див. `PAGE_BUDGET.md`).

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

## Фаза 2. Постановка експериментів

**Вхід:** `notes/EXPERIMENT_PROTOCOL.md`, код у `experiments/`.

**Дії:**
1. Створити **публічний** GitHub-репозиторій (публічний → безлімітні хвилини Actions).
2. Скопіювати `experiments/` у корінь репозиторію, `experiments/workflows/experiment.yml` → `.github/workflows/experiment.yml`.
3. Прогнати smoke-тест: `make smoke` (n=4, c=4, 60 s) — переконатися, що мережа піднімається і TPS > 0.
4. Запустити повну матрицю: `gh workflow run experiment.yml`.
5. Дочекатися завершення, зібрати артефакти: `gh run download`.
6. Покласти сирі дані в `data/raw/`.

**Критерій:** `data/raw/` містить ≥ 80 JSON-файлів результатів прогонів.

---

## Фаза 3. Аналіз і генерація чисел

**Дії:**
```powershell
python experiments/analysis/fit_bifactor.py   --in data/raw --out data/processed
python experiments/analysis/bootstrap_pi.py   --in data/processed --out data/processed
python experiments/analysis/sizing.py         --in data/processed --out data/processed
python experiments/analysis/make_figures.py   --in data/processed --out figures
python experiments/analysis/emit_numbers_tex.py --in data/processed --out numbers.tex
```

**Критерій:** у `numbers.tex` не лишилося жодного `\TODO`.

---

## Фаза 4. Наповнення тексту результатами

**Дії (по секціях):**

| Секція | Що зробити |
|---|---|
| `09_results.tex` | Розкоментувати `\includegraphics`, видалити `\rule{}{}`-заглушки. Заповнити `\TODO{}` у таблицях числами з `data/processed/model_comparison.csv` та `sizing_ablation.csv`. Дописати інтерпретацію F-тесту `q`-інваріантності. |
| `10_case_study.tex` | Розкоментувати рисунки. Перевірити, що вікно `[nmin, nmax]` непорожнє; якщо порожнє — переписати підрозділ як демонстрацію `Corollary~\ref{cor:infeasible}`. |
| `11_limitations.tex` | Додати фактичний максимальний виміряний `n`. |
| `01_introduction.tex` | Уточнити чисельні твердження у Contributions відповідно до отриманих результатів. |
| `12_conclusions.tex` | Переписати **останнім**, після того як усі числа відомі. |

**Критерій:** у всьому проєкті немає `\TODO`, `\rule{`-заглушок і закоментованих `\includegraphics`.

---

## Фаза 5. Фінальне вичитування

**Чеклист:** `notes/CHECKLIST.md`.

Ключове:
- [ ] Обсяг ≤ 10 сторінок
- [ ] ≥ 25 джерел, усі цитовані в тексті, усі DOI/URL перевірені
- [ ] Немає дубльованих заголовків секцій (дефект статті 1)
- [ ] Немає дубльованих блоків Limitations (дефект статті 1)
- [ ] Усі перехресні посилання вказують на правильні номери (дефект статті 1)
- [ ] Немає незаповнених шаблонних плейсхолдерів `Vol.x, No.x` (дефект статті 1)
- [ ] Український `\abstractUkr` вичитаний
- [ ] Розбіжність між статтями 1 і 2 явно пояснена через `Theorem~\ref{thm:identifiability}`
- [ ] Клас відмов чесно названий «omission + duplication», а не «Byzantine»

---

## Порядок написання (якщо переписувати з нуля)

Порядок **не** збігається з порядком секцій:

1. `04_bifactor_model` — теорема ідентифікованості (ядро новизни)
2. `03_rnm_protocol` — обґрунтування протоколу вимірювання
3. `06_safety_model` + `07_sizing_problem` — теорема про вікно
4. `05_prediction_intervals`
5. `08_experiments` — дизайн під уже сформульовану теорію
6. `09_results`
7. `10_case_study`
8. `02_related_work` — після того як внесок відомий
9. `01_introduction`
10. `11_limitations`
11. `12_conclusions`
12. `\abstract` / `\abstractUkr` у `paper3.tex` — **найостанніші**
