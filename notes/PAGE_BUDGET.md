# PAGE_BUDGET.md

Жорсткий ліміт: **10 сторінок A4** (`\documentclass[12pt]{article}` + `MMC.sty`).

Українська анотація (`\maketitleUkr`) друкується окремою сторінкою в кінці
і, за практикою видання, у ліміт основного тексту не зараховується — але
краще закласти запас.

---

## Розподіл

| # | Секція | Файл | Бюджет, стор. | Факт |
|---|---|---|---|---|
| — | Титул + анотація EN | `paper3.tex` | 0.5 | |
| 1 | Introduction | `01_introduction.tex` | 1.0 | |
| 2 | Related work | `02_related_work.tex` | 1.0 | |
| 3 | RNM protocol | `03_rnm_protocol.tex` | 1.0 | |
| 4 | Bi-factor model + Theorem 1 + Alg. 1 | `04_bifactor_model.tex` | 1.5 | |
| 5 | Prediction intervals | `05_prediction_intervals.tex` | 0.5 | |
| 6 | Safety model | `06_safety_model.tex` | 0.5 | |
| 7 | Sizing + Theorem 2 + Alg. 2 | `07_sizing_problem.tex` | 1.5 | |
| 8 | Experiments | `08_experiments.tex` | 0.8 | |
| 9 | Results | `09_results.tex` | 1.2 | |
| 10 | Case study | `10_case_study.tex` | 0.5 | |
| 11 | Limitations | `11_limitations.tex` | 0.3 | |
| 12 | Conclusions | `12_conclusions.tex` | 0.4 | |
| — | References (36) | `bib/references.tex` | 1.3 | |
| | **Разом** | | **12.0** | |

**12.0 > 10.0.** Потрібне скорочення на ~2 сторінки. План нижче.

---

## План скорочення (за пріоритетом)

### Крок 1. Рисунки (−0.8 стор.)
З 5 запланованих рисунків лишити 3:
- **Залишити:** `fig:confounding` (ядро новизни N2)
- **Залишити:** `fig:window` (ядро новизни N4)
- **Залишити:** `fig:roc` (єдиний виміряний детектор)
- **Прибрати:** `fig:bifactor` → замінити на таблицю коефіцієнтів
- **Прибрати:** `fig:sensitivity` → замінити двома реченнями тексту

### Крок 2. Related work (−0.4 стор.)
Стиснути 7 підрозділів у 4 абзаци. Порівняльну таблицю `tab:related` прибрати —
її зміст переказати одним абзацом.

### Крок 3. Таблиці результатів (−0.3 стор.)
Об'єднати `tab:models` і `tab:ablation` в одну таблицю з двома блоками рядків.

### Крок 4. Доведення (−0.3 стор.)
Доведення `Lemma~\ref{lem:detequiv}` і `Lemma~\ref{lem:monotone}` — у два рядки
кожне, без розгорнутих викладок.

### Крок 5. Introduction (−0.2 стор.)
Підрозділ Scope злити з Contributions.

**Разом: −2.0 стор. → 10.0.**

---

## Що НЕ скорочувати

| Елемент | Чому |
|---|---|
| `Theorem~\ref{thm:identifiability}` + повне доведення | Це вся новизна статті |
| `Theorem~\ref{thm:window}` + повне доведення | Другий стовп новизни |
| `11_limitations.tex` | Чесність щодо класу відмов — критично для рецензування |
| Кількість джерел (≥ 25) | Вимога користувача |
| Український `\abstractUkr` | Вимога видання |

---

## Контроль обсягу

Після кожної фази:

```powershell
cd c:\pol\paper_3
pdflatex -interaction=nonstopmode paper3.tex | Select-String "Output written"
```

Або порахувати сторінки:

```powershell
(Get-Content build\paper3.log | Select-String "Output written.*\((\d+) pages").Matches.Groups[1].Value
```

---

## Аварійний план, якщо після всіх скорочень > 10 стор.

1. Перенести `10_case_study.tex` у додаток / supplementary → −0.5
2. Скоротити `08_experiments.tex` до таблиці `tab:design` + 3 абзаци → −0.4
3. Перевести `Algorithm~\ref{alg:calibration}` у нумерований список у тексті → −0.3
