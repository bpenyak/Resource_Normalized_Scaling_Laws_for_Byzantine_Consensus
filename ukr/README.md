# Українська версія статті (`ukr/`)

Паралельний каталог до англійської версії в корені `paper_3/`.

## Збірка

```powershell
cd c:\pol\paper_3\ukr
pdflatex -interaction=nonstopmode paper3.tex
pdflatex -interaction=nonstopmode paper3.tex
```

Лише **pdflatex** (T2A + babel), як і для англійської версії.

## Вміст

| Шлях | Призначення |
|---|---|
| `paper3.tex` | Головний файл (мова тіла — українська) |
| `sections/*.tex` | Повний переклад секцій 1–7 |
| `macros.tex`, `numbers.tex`, `MMC.sty` | Копії з кореня (числа спільні) |
| `figures/` | Копії PDF-рисунків |
| `bib/references.tex` | Та сама англомовна бібліографія |

В кінці PDF — сторінка з англійською анотацією.

## Синхронізація з EN

Після зміни чисел/рисунків у корені:

```powershell
Copy-Item ..\numbers.tex,..\macros.tex .\ -Force
Copy-Item ..\figures\fig_*.pdf .\figures\ -Force
```

Текст секцій синхронізуйте вручну (або окремим перекладом), бо `ukr/sections/` —
окремі файли.
