# -*- coding: utf-8 -*-
"""Generate conference theses (max 2 pages) from paper 3, matching instructions.md."""
import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, Twips

OUT = r"C:\pol\paper_3\tezu\Пеняк Б О_тези.docx"

NB_HYPHEN = "\u2011"  # rendered as Word non-breaking hyphen


def set_run_font(run, name="Times New Roman", size=11, italic=False, bold=False):
    run.font.name = name
    run.font.size = Pt(size)
    run.italic = italic
    run.bold = bold
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:ascii"), name)
    rFonts.set(qn("w:hAnsi"), name)
    rFonts.set(qn("w:cs"), name)
    rFonts.set(qn("w:eastAsia"), name)
    lang = rPr.find(qn("w:lang"))
    if lang is None:
        lang = OxmlElement("w:lang")
        rPr.append(lang)
    lang.set(qn("w:val"), "uk-UA")
    lang.set(qn("w:eastAsia"), "uk-UA")


def add_run(
    p,
    text,
    *,
    italic=False,
    bold=False,
    sub=False,
    sup=False,
    font="Times New Roman",
    size=11,
    all_caps=False,
):
    text = re.sub(r"(?<=\w)-(?=\w)", NB_HYPHEN, text)
    run = p.add_run(text)
    if NB_HYPHEN in text:
        for t in run._element.findall(qn("w:t")):
            run._element.remove(t)
        for i, part in enumerate(text.split(NB_HYPHEN)):
            if i:
                run._element.append(OxmlElement("w:noBreakHyphen"))
            if part:
                t = OxmlElement("w:t")
                t.set(qn("xml:space"), "preserve")
                t.text = part
                run._element.append(t)
    set_run_font(run, name=font, size=size, italic=italic, bold=bold)
    if sub:
        run.font.subscript = True
    if sup:
        run.font.superscript = True
    if all_caps:
        run.font.all_caps = True
    return run


def set_para_format(
    p,
    *,
    align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    first_line=None,
    left=None,
    hanging=None,
    space_before=0,
    space_after=0,
    line=240,
):
    pf = p.paragraph_format
    pf.alignment = align
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    # 240 twips = single
    pPr = p._p.get_or_add_pPr()
    spacing = pPr.find(qn("w:spacing"))
    if spacing is None:
        spacing = OxmlElement("w:spacing")
        pPr.append(spacing)
    spacing.set(qn("w:before"), str(int(space_before * 20)))
    spacing.set(qn("w:after"), str(int(space_after * 20)))
    spacing.set(qn("w:line"), str(line))
    spacing.set(qn("w:lineRule"), "auto")
    if first_line is not None:
        pf.first_line_indent = first_line
    else:
        pf.first_line_indent = Cm(0)
    if left is not None:
        pf.left_indent = left
    if hanging is not None:
        pf.first_line_indent = -hanging
        pf.left_indent = hanging


def empty_line(doc):
    p = doc.add_paragraph()
    set_para_format(p, align=WD_ALIGN_PARAGRAPH.CENTER, first_line=Cm(0))
    add_run(p, "")
    return p


def main():
    doc = Document()

    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, side, Cm(2.3))
    section.header_distance = Cm(1.25)
    section.footer_distance = Cm(1.25)

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(11)
    rPr = normal.element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    rFonts.set(qn("w:ascii"), "Times New Roman")
    rFonts.set(qn("w:hAnsi"), "Times New Roman")
    rFonts.set(qn("w:cs"), "Times New Roman")

    # --- UDK ---
    p = doc.add_paragraph()
    set_para_format(p, align=WD_ALIGN_PARAGRAPH.LEFT, first_line=Cm(0))
    add_run(p, "УДК: 004.75:519.2")

    # --- Authors (right, caps, bold italic) ---
    p = doc.add_paragraph()
    set_para_format(p, align=WD_ALIGN_PARAGRAPH.RIGHT, first_line=Cm(0))
    add_run(p, "ПЕНЯК Б. О., ЛЮБІНСЬКИЙ Б. Б.", italic=True, bold=True, all_caps=True)

    # --- Organization ---
    p = doc.add_paragraph()
    set_para_format(p, align=WD_ALIGN_PARAGRAPH.RIGHT, first_line=Cm(0))
    add_run(p, "Національний університет «Львівська політехніка» (Україна)")

    empty_line(doc)

    # --- Title ---
    p = doc.add_paragraph()
    set_para_format(p, align=WD_ALIGN_PARAGRAPH.CENTER, first_line=Cm(0))
    add_run(
        p,
        "РЕСУРСНО-НОРМОВАНІ ЗАКОНИ МАСШТАБУВАННЯ BFT-КОНСЕНСУСУ",
        bold=True,
        all_caps=True,
    )

    empty_line(doc)

    # --- Abstract (italic, 2–8 lines, sentence case, justified, indent) ---
    p = doc.add_paragraph()
    set_para_format(p, first_line=Cm(0.9))
    add_run(
        p,
        "Визначення розміру BFT-множини валідаторів для електронного урядування "
        "узгоджує спад пропускної здатності зі зростанням сили виявлення відмов "
        "при збільшенні ",
        italic=True,
    )
    add_run(p, "n", italic=True)
    add_run(
        p,
        ". Запропоновано ресурсно-нормоване вимірювання та двофакторну модель; у "
        "ненасиченому режимі з шумом нульового середнього однофакторний показник "
        "прямує до ",
        italic=True,
    )
    add_run(p, "γλ", italic=True)
    add_run(p, " − ", italic=True)
    add_run(p, "β", italic=True)
    add_run(
        p,
        " (зміщення через пропущену змінну). На типовій CI для Besu/QBFT при "
        "фіксованій квоті ",
        italic=True,
    )
    add_run(p, "β", italic=True)
    add_run(
        p,
        " = 1,651 ± 0,151; за майже випадкового детектора детекційне обмеження "
        "послаблено (не застосовується), і вікно [4, 4] визначає лише пропускна "
        "здатність.",
        italic=True,
    )

    empty_line(doc)

    # --- Body 1: problem ---
    p = doc.add_paragraph()
    set_para_format(p, first_line=Cm(0.9))
    add_run(
        p,
        "Постановка проблеми. Permissioned візантійсько відмовостійкий (BFT) "
        "консенсус лежить в основі систем електронного урядування і ставить "
        "питання закупівлі: скільки валідаторів ",
    )
    add_run(p, "n", italic=True)
    add_run(
        p,
        " має мати мережа? Пропускна здатність схиляє до малого ",
    )
    add_run(p, "n", italic=True)
    add_run(
        p,
        ": кожен валідатор виконує кожну транзакцію, а протоколи родини PBFT "
        "обмінюються ",
    )
    add_run(p, "O", italic=True)
    add_run(p, "(")
    add_run(p, "n", italic=True)
    add_run(p, "2", sup=True)
    add_run(p, ") повідомленнями на блок [1]. Надійність виявлення відмов схиляє до великого ")
    add_run(p, "n", italic=True)
    add_run(
        p,
        ". На етапі проєктування виділені багатохостові стенди часто недоступні, "
        "а типові CI-раннери розміщують багато валідаторів на малій кількості ядер. "
        "Без нормування однофакторні підгонки TPS(",
    )
    add_run(p, "n", italic=True)
    add_run(p, ") ∝ ")
    add_run(p, "n", italic=True)
    add_run(p, "α", sup=True)
    add_run(
        p,
        " змішують вартість консенсусу з конкуренцією за ресурси хоста та з "
        "розкладом конкурентності генератора навантаження. Опубліковані показники "
        "тоді розходяться за величиною і іноді за знаком; попередні калібрування, "
        "екстрапольовані до шістдесяти валідаторів, відрізняються приблизно на "
        "порядок [2, 3].",
    )

    # --- Body 2: tasks ---
    p = doc.add_paragraph()
    set_para_format(p, first_line=Cm(0.9))
    add_run(
        p,
        "Вирішуються такі завдання: відокремити алгоритмічну вартість консенсусу "
        "від конкуренції за ресурси хоста; пояснити неідентифікованість "
        "однофакторного показника вздовж шляху конкурентності; сформулювати задачу "
        "визначення розміру множини валідаторів з імовірнісними обмеженнями на "
        "пропускну здатність і детекцію; відкалібрувати робочий процес на "
        "відтворюваній кампанії на типовій CI.",
    )

    # --- Body 3: RNM + model ---
    p = doc.add_paragraph()
    set_para_format(p, first_line=Cm(0.9))
    add_run(
        p,
        "Суть дослідження. Введено протокол ресурсно-нормованого вимірювання (RNM): "
        "кожен контейнер валідатора отримує фіксовану CPU-квоту ",
    )
    add_run(p, "q", italic=True)
    add_run(p, " незалежно від ")
    add_run(p, "n", italic=True)
    add_run(p, ", а нормована пропускна здатність дорівнює TPS / ")
    add_run(p, "q", italic=True)
    add_run(
        p,
        ". За протоколом RNM двофакторна характеристика має вигляд",
    )

    # formula (centered; Latin italic, Greek upright; unnumbered — no in-text number)
    p = doc.add_paragraph()
    set_para_format(
        p,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        first_line=Cm(0),
        space_before=6,
        space_after=6,
    )
    add_run(p, "TPS(", font="Cambria Math")
    add_run(p, "n", font="Cambria Math", italic=True)
    add_run(p, ", ", font="Cambria Math")
    add_run(p, "c", font="Cambria Math", italic=True)
    add_run(p, ") = ", font="Cambria Math")
    add_run(p, "T", font="Cambria Math", italic=True)
    add_run(p, "0", font="Cambria Math", sub=True)
    add_run(p, " · ", font="Cambria Math")
    add_run(p, "g", font="Cambria Math", italic=True)
    add_run(p, "(", font="Cambria Math")
    add_run(p, "c", font="Cambria Math", italic=True)
    add_run(p, ") · ", font="Cambria Math")
    add_run(p, "n", font="Cambria Math", italic=True)
    add_run(p, "−β", font="Cambria Math", sup=True)
    add_run(p, ",     ", font="Cambria Math")
    add_run(p, "g", font="Cambria Math", italic=True)
    add_run(p, "(", font="Cambria Math")
    add_run(p, "c", font="Cambria Math", italic=True)
    add_run(p, ") = ", font="Cambria Math")
    add_run(p, "c", font="Cambria Math", italic=True)
    add_run(p, "γ", font="Cambria Math", sup=True)
    add_run(p, " / [1 + (", font="Cambria Math")
    add_run(p, "c", font="Cambria Math", italic=True)
    add_run(p, "/", font="Cambria Math")
    add_run(p, "c", font="Cambria Math", italic=True)
    add_run(p, "*", font="Cambria Math", sup=True)
    add_run(p, ")", font="Cambria Math")
    add_run(p, "θ", font="Cambria Math", sup=True)
    add_run(p, "].", font="Cambria Math")

    p = doc.add_paragraph()
    set_para_format(p, first_line=Cm(0))
    add_run(p, "де ")
    add_run(p, "c", italic=True)
    add_run(p, " — конкурентність клієнтів, β > 0 — показник спаду за кількістю валідаторів, γ ∈ (0, 1] — показник конкурентності, ")
    add_run(p, "c", italic=True)
    add_run(p, "*", italic=True, sup=True)
    add_run(p, " — поріг насичення (форма у стилі USL [4]). У ненасиченому режимі ")
    add_run(p, "c", italic=True)
    add_run(p, " ≪ ")
    add_run(p, "c", italic=True)
    add_run(p, "*", italic=True, sup=True)
    add_run(p, " залежність лог-лінійна. Якщо вимірювання виконано вздовж шляху log ")
    add_run(p, "c", italic=True)
    add_run(p, " = λ log ")
    add_run(p, "n", italic=True)
    add_run(p, " + μ і шум має нульове середнє та скінченну дисперсію, нахил МНК однофакторної моделі задовольняє α̂ →ᴾ γλ − β; це стандартне зміщення через пропущену змінну [5]. Зокрема α̂ = −β лише за факторного дизайну λ = 0; без зазначення λ опубліковані однофакторні показники не слід трактувати як переносні властивості протоколу між стендами.")

    # --- Body 4: sizing ---
    p = doc.add_paragraph()
    set_para_format(p, first_line=Cm(0.9))
    add_run(
        p,
        "Калібрований показник є входом задачі з імовірнісними обмеженнями [6]: "
        "мінімізувати неспадну вартість Cost(",
    )
    add_run(p, "n", italic=True)
    add_run(
        p,
        ") за умов, що нижня межа прогнозного інтервалу пропускної здатності не "
        "нижча за піковий попит, а ймовірність пропуску скоординованої відмови з "
        "пропуском транзакцій (coordinated transaction-omission fault; інженерне "
        "наближення межі Гефдінга [7]) не перевищує заданого рівня. Допустимі "
        "розміри дискретні (ефективні BFT-множини мають вигляд 3f + 1), а допустима "
        "множина є замкненим інтервалом [",
    )
    add_run(p, "n", italic=True)
    add_run(p, "min", italic=True, sub=True)
    add_run(p, ", ", italic=False)
    add_run(p, "n", italic=True)
    add_run(p, "max", italic=True, sub=True)
    add_run(
        p,
        "]; порожній інтервал сертифікує, що жоден розмір множини валідаторів не "
        "задовольняє обидві вимоги, тож потрібно змінювати архітектуру або клас "
        "обладнання, а не лише ",
    )
    add_run(p, "n", italic=True)
    add_run(p, ".")

    # --- Body 5: experiments ---
    p = doc.add_paragraph()
    set_para_format(p, first_line=Cm(0.9))
    add_run(
        p,
        "Кампанію виконано у публічному CI-робочому процесі на чотириядерному "
        "хості: мережа Hyperledger Besu/QBFT за протоколом RNM, 94 успішні записи, ",
    )
    add_run(p, "n", italic=True)
    add_run(p, " ≤ 16. Спільний МНК на опорній квоті ")
    add_run(p, "q", italic=True)
    add_run(p, " = 0,25 дає ")
    add_run(p, "β", italic=True)
    add_run(p, " = 1,651 ± 0,151 і ")
    add_run(p, "γ", italic=True)
    add_run(p, " = 0,178 ± 0,070 (")
    add_run(p, "R", italic=True)
    add_run(p, "² = 0,727). Повторне семплювання вздовж ")
    add_run(p, "λ", italic=True)
    add_run(p, " = 1 дає ")
    add_run(p, "α̂", italic=True)
    add_run(p, " = −1,362 проти аналітичного ")
    add_run(p, "γλ", italic=True)
    add_run(p, " − ")
    add_run(p, "β", italic=True)
    add_run(p, " = −1,473. Інваріантність ")
    add_run(p, "β", italic=True)
    add_run(p, " щодо квоти на наборі ")
    add_run(p, "q", italic=True)
    add_run(p, " ∈ {0,20; 0,25; 0,33} відхилено (")
    add_run(p, "p", italic=True)
    add_run(p, " = 0,002): при ")
    add_run(p, "q", italic=True)
    add_run(
        p,
        " = 0,33 пропускна здатність уже не зростає з квотою, а сумарна "
        "резервація перевищує ємність хоста. Отже, RNM стабілізує ",
    )
    add_run(p, "β", italic=True)
    add_run(p, " за фіксованої квоти, а коефіцієнти звітовано при ")
    add_run(p, "q", italic=True)
    add_run(
        p,
        " = 0,25. Детектор omission/duplication має AUC = 0,506 (майже випадковий "
        "рівень); з ним детекційне обмеження невиконуване (потрібне ",
    )
    add_run(p, "n", italic=True)
    add_run(p, "min", italic=True, sub=True)
    add_run(
        p,
        " ≈ 3,3·10³), тож формально допустима множина порожня; обмеження "
        "послаблено (не застосовується), і вікно визначає лише пропускна "
        "здатність. Основна підгонка використовує всі ",
    )
    add_run(p, "n", italic=True)
    add_run(p, "; окрема переоцінка лише на ")
    add_run(p, "n", italic=True)
    add_run(p, " ≤ 9 (")
    add_run(p, "β", italic=True)
    add_run(p, " = 1,300) дає інтервали, що покривають 20 і 21 з 22 відкладених прогонів (90,9 % / 95,5 %) при ")
    add_run(p, "n", italic=True)
    add_run(p, " ∈ {11, 13, 16}. Сталий ")
    add_run(p, "β", italic=True)
    add_run(p, " усереднює нахил, що зростає з ")
    add_run(p, "n", italic=True)
    add_run(p, " (локально ≈ 1,4 → 2,8); це пояснюємо залишковою конкуренцією на хості, коли резервація ")
    add_run(p, "nq", italic=True)
    add_run(p, " наближається до чотирьох ядер (RNM усуває конкуренцію лише доки ")
    add_run(p, "nq", italic=True)
    add_run(p, " < кількості ядер хоста). Основне ")
    add_run(p, "β", italic=True)
    add_run(p, " консервативне щодо ")
    add_run(p, "n", italic=True)
    add_run(p, "max", italic=True, sub=True)
    add_run(
        p,
        ", але оптимістичне щодо κ (13,0 проти 16,7 за підгонки на малих n). Сценарій "
        "≈ 3·10⁷ бюлетенів за 12 год дає середнє "
        "≈ 694 TPS; за припущеного пік-фактора ≈ 3 пік становить ≈ 2,1·10³ TPS. "
        "Прогони на CI без відмов фіксують не більше ≈ 89 TPS (при ",
    )
    add_run(p, "n", italic=True)
    add_run(p, " = 7, ")
    add_run(p, "c", italic=True)
    add_run(p, " = 16, ")
    add_run(p, "q", italic=True)
    add_run(p, " = 0,25), тому модель працює в одиницях TPS/")
    add_run(p, "q", italic=True)
    add_run(p, ", а масштаб κ = 13,0 тлумачиться як кількість ядер на валідатор цільового обладнання. Лінійність пропускної здатності за квотою — головне припущення й основний ризик екстраполяції: κ у ≈ 52 рази перевищує калібровану квоту, тоді як уже при ")
    add_run(p, "q", italic=True)
    add_run(p, " = 0,33 пропускна здатність перестає зростати; тож κ — вимога до перевірки, а не виміряна можливість. Тоді вікно стискається до [4, 4]. Подвоєний попит або емульований WAN RTT 200 мс (")
    add_run(p, "β", italic=True)
    add_run(p, " на сітці WAN-експерименту зростає з 1,459 до 2,708) при фіксованому κ спорожнює допустиму множину; потрібно κ ≈ 26 або ≈ 73 відповідно.")

    # --- Body 6: conclusions ---
    p = doc.add_paragraph()
    set_para_format(p, first_line=Cm(0.9))
    add_run(
        p,
        "Висновки. Розбіжність однофакторних показників масштабування BFT може "
        "виникати з дизайну вимірювання (шлях конкурентності ",
    )
    add_run(p, "λ", italic=True)
    add_run(
        p,
        "), а не лише з властивостей протоколу. Ресурсно-нормоване калібрування "
        "при ",
    )
    add_run(p, "λ", italic=True)
    add_run(
        p,
        " = 0 стабілізує показник консенсусу за фіксованої квоти і перетворює "
        "його на відтворюваний робочий процес визначення розміру множини "
        "валідаторів; компроміс «пропускна здатність — детекція» сформульовано, "
        "але з виміряним детектором не продемонстровано. Для дослідженого "
        "розгортання Besu/QBFT на типовій CI відповідь на питання закупівлі — "
        "найменша допустима множина ",
    )
    add_run(p, "n", italic=True)
    add_run(
        p,
        " = 4; більший ",
    )
    add_run(p, "n", italic=True)
    add_run(
        p,
        " погіршує прогнозовану пропускну здатність. Числові коефіцієнти "
        "специфічні для розгортання; методика розрахована на перекалібрування за "
        "узгоджених умов вимірювання. Код, дані та артефакти CI-кампанії: "
        "https://github.com/bpenyak/Resource_Normalized_Scaling_Laws_for_Byzantine_Consensus.",
    )

    empty_line(doc)

    # --- Literature heading ---
    p = doc.add_paragraph()
    set_para_format(
        p,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        first_line=Cm(0),
        space_after=6,
    )
    add_run(p, "ПЕРЕЛІК ЛІТЕРАТУРИ")

    refs = [
        "Castro M., Liskov B. Practical Byzantine fault tolerance. Proceedings of the Third Symposium on Operating Systems Design and Implementation (OSDI). 1999. P. 173–186.",
        "Peniak B. O., Liubinskiy B. B., Solomka I. R. Minimal-sample performance prediction for Byzantine consensus: the α-calibration method. Mathematical Modeling and Computing. 2026. (прийнято до друку).",
        "Peniak B. O., Liubinskiy B. B. Adaptive hybrid consensus mechanism for blockchain-based e‑governance: a machine learning approach. Науковий вісник Ужгородського університету. Серія «Математика і інформатика». 2026. Т. 49, № 2. С. 255–261.",
        "Gunther N. J. Guerrilla capacity planning: a tactical approach to planning for highly scalable applications and services. Berlin : Springer, 2007.",
        "Wooldridge J. M. Econometric analysis of cross section and panel data. 2nd ed. Cambridge, MA : MIT Press, 2010. 1064 p.",
        "Charnes A., Cooper W. W. Chance-constrained programming. Management Science. 1959. Vol. 6, No. 1. P. 73–79.",
        "Hoeffding W. Probability inequalities for sums of bounded random variables. Journal of the American Statistical Association. 1963. Vol. 58, No. 301. P. 13–30.",
    ]
    hang = Cm(0.45)
    for i, text in enumerate(refs, 1):
        p = doc.add_paragraph()
        set_para_format(
            p,
            hanging=hang,
            space_after=3,
        )
        add_run(p, f"{i}.\u00a0{text}")

    doc.save(OUT)
    Path(r"C:\pol\paper_3\tezu\_wrote.txt").write_text("ok\n", encoding="utf-8")


if __name__ == "__main__":
    main()
