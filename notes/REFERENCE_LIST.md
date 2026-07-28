# REFERENCE_LIST.md

Реєстр джерел. Джерело істини — `bib/references.tex`. Цей файл відстежує
**де цитується** і **чи перевірено**.

Статус: `?` — не перевірено, `OK` — DOI/URL відкрито і підтверджено,
`FIX` — потребує виправлення.

---

## BFT-консенсус (10)

| Ключ | Джерело | Цитується в | Статус |
|---|---|---|---|
| `castro1999` | PBFT, OSDI'99 | 02 | ? |
| `lamport1982` | Byzantine Generals, TOPLAS | 02 | ? |
| `dwork1988` | Partial synchrony, JACM | 02 | ? |
| `yin2019` | HotStuff, PODC'19 | 02 | ? |
| `buchman2016` | Tendermint, MSc thesis | 02 | ? |
| `gilad2017` | Algorand, SOSP'17 | 02 | ? |
| `miller2016` | HoneyBadgerBFT, CCS'16 | 02 | ? |
| `stathakopoulou2019` | Mir-BFT, arXiv | 02 | ? |
| `vukolic2015` | PoW vs BFT | 02 | ? |
| `kiayias2017` | Ouroboros, CRYPTO'17 | 02 | ? |

## Бенчмаркінг (5)

| Ключ | Джерело | Цитується в | Статус |
|---|---|---|---|
| `androulaki2018` | Hyperledger Fabric, EuroSys'18 | 02 | ? |
| `thakkar2018` | Fabric benchmarking, MASCOTS'18 | 02 | ? |
| `baliga2018` | Quorum performance, arXiv | 02 | ? |
| `dinh2017` | BLOCKBENCH, SIGMOD'17 | 02 | ? |
| `sousa2018` | BFT-SMaRt ordering, DSN'18 | 02 | ? |

## Закони масштабування (4)

| Ключ | Джерело | Цитується в | Статус |
|---|---|---|---|
| `amdahl1967` | Amdahl's law | 02, 09 | ? |
| `gustafson1988` | Reevaluating Amdahl, CACM | 02 | ? |
| `gunther2007` | USL, Guerrilla Capacity Planning | 02, 09 | ? |
| `gunther2015` | Hadoop superlinear scalability | 02 | ? |

## Концентрація та статистика (6)

| Ключ | Джерело | Цитується в | Статус |
|---|---|---|---|
| `hoeffding1963` | Hoeffding inequality, JASA | 02, 06 | ? |
| `boucheron2013` | Concentration inequalities | 02 | ? |
| `efron1993` | Introduction to the bootstrap | 02 | ? |
| `davison1997` | Bootstrap methods | 02 | ? |
| `seber2003` | Nonlinear regression | 02 | ? |
| `bates1988` | Nonlinear regression analysis | 02 | ? |

## Оптимізація за невизначеності (3)

| Ключ | Джерело | Цитується в | Статус |
|---|---|---|---|
| `charnes1959` | Chance-constrained programming | 02, 07 | ? |
| `nemirovski2007` | Convex approximations of CC programs | 02 | ? |
| `bental2009` | Robust optimization | 02 | ? |

## Е-урядування та е-голосування (4)

| Ключ | Джерело | Цитується в | Статус |
|---|---|---|---|
| `springall2014` | Estonian i-voting, CCS'14 | 02, 10 | ? |
| `specter2020` | Voatz, USENIX Sec'20 | 02, 10 | ? |
| `park2021` | Bad to worse, J. Cybersecurity | 02, 10 | ? |
| `bensasson2014` | Zerocash, S&P'14 | 02 | ? |

## Інструменти (2)

| Ключ | Джерело | Цитується в | Статус |
|---|---|---|---|
| `pedregosa2011` | scikit-learn, JMLR | 02 | ? |
| `besu` | Hyperledger Besu docs | 02, 08 | ? |

## Власні попередні роботи (2)

| Ключ | Джерело | Цитується в | Статус |
|---|---|---|---|
| `peniak2026a` | α-calibration, MMC | 01, 02, 04, 09, 12 | **FIX** — потрібні том/номер/сторінки |
| `peniak2026b` | Adaptive hybrid consensus, НВ УжНУ 49(2) 1–8, DOI 10.24144/2616-7700.2026.49(2).1-8 | 01, 02, 06, 09, 10, 12 | ? |

---

**Разом: 36.** Вимога: ≥ 25. Запас на випадок вилучення непідтверджених.

---

## Кандидати на додавання (якщо потрібно збільшити)

- Ongaro & Ousterhout, Raft, USENIX ATC'14 — контраст crash-fault vs BFT
- Bessani et al., BFT-SMaRt, DSN'14
- Nakamoto, Bitcoin whitepaper — історичний контекст
- Wood, Ethereum Yellow Paper — платформа
- Hemmerlé et al. / інші роботи з capacity planning для розподілених БД

## Кандидати на вилучення (якщо треба скоротити обсяг)

Порядок вилучення (найменш критичні першими):
1. `bensasson2014` — приватність не є темою статті
2. `gunther2015` — `gunther2007` покриває USL
3. `bates1988` — дублює `seber2003`
4. `davison1997` — дублює `efron1993`
5. `bental2009` — дублює `nemirovski2007`

Після вилучення всіх п'яти лишається 31 — все ще > 25.
