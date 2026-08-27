"""Registry of the published requirements a draft is checked against.

Every other criterion in the evaluator measures something we decided was
important. This registry measures requirements that exist independently of this
project, published by the Ministry of Labour of Russia, which is what lets a
customer's safety engineer verify a mapping instead of trusting our judgement.

Two kinds of entry live here, and the difference is stated rather than blurred:

* **paragraph-level** — the requirement was read in the text of the order and
  carries its paragraph number. Order 772n is covered this way.
* **document-level** — the requirement is a well-known subject of the industry
  rules named in `source`, but the paragraph was not verified against the
  official text. `paragraph` is None for these, and reports must say so.

Fabricating a paragraph number would make the check worse than useless: a
reviewer who looked it up and found something else would stop believing the rest
of the report, and they would be right to.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegulatorySource:
    key: str
    document: str
    title: str


@dataclass(frozen=True)
class RegulatoryRequirement:
    source: str
    label: str
    issue: str
    markers: tuple[str, ...]
    paragraph: str | None = None
    profiles: tuple[str, ...] = ()

    def applies_to(self, profile: str) -> bool:
        return not self.profiles or profile in self.profiles

    def citation(self) -> str:
        return f"{self.paragraph}" if self.paragraph else "тематическое требование"


SOURCES: dict[str, RegulatorySource] = {
    "772n": RegulatorySource(
        "772n",
        "Приказ Минтруда России от 29.10.2021 № 772н",
        "Основные требования к порядку разработки и содержанию правил и инструкций по охране труда",
    ),
    "883n": RegulatorySource(
        "883n",
        "Приказ Минтруда России от 11.12.2020 № 883н",
        "Правила по охране труда при строительстве, реконструкции и ремонте",
    ),
    "833n": RegulatorySource(
        "833n",
        "Приказ Минтруда России от 27.11.2020 № 833н",
        "Правила по охране труда при размещении, монтаже, техническом обслуживании и ремонте технологического оборудования",
    ),
    "835n": RegulatorySource(
        "835n",
        "Приказ Минтруда России от 27.11.2020 № 835н",
        "Правила по охране труда при работе с инструментом и приспособлениями",
    ),
    "758n": RegulatorySource(
        "758n",
        "Приказ Минтруда России от 29.10.2020 № 758н",
        "Правила по охране труда в жилищно-коммунальном хозяйстве",
    ),
    "871n": RegulatorySource(
        "871n",
        "Приказ Минтруда России от 09.12.2020 № 871н",
        "Правила по охране труда на автомобильном транспорте",
    ),
    "866n": RegulatorySource(
        "866n",
        "Приказ Минтруда России от 07.12.2020 № 866н",
        "Правила по охране труда при производстве отдельных видов пищевой продукции",
    ),
    "928n": RegulatorySource(
        "928n",
        "Приказ Минтруда России от 18.12.2020 № 928н",
        "Правила по охране труда в медицинских организациях",
    ),
    "881n": RegulatorySource(
        "881n",
        "Приказ Минтруда России от 11.12.2020 № 881н",
        "Правила по охране труда в подразделениях пожарной охраны",
    ),
    "gost_3_1105": RegulatorySource(
        "gost_3_1105",
        "ГОСТ 3.1105-2011 (ЕСТД)",
        "Формы и правила оформления документов общего назначения",
    ),
    "gost_12_2_003": RegulatorySource(
        "gost_12_2_003",
        "ГОСТ 12.2.003-91 (ССБТ)",
        "Оборудование производственное. Общие требования безопасности",
    ),
    "gost_12_3_002": RegulatorySource(
        "gost_12_3_002",
        "ГОСТ 12.3.002-2014 (ССБТ)",
        "Процессы производственные. Общие требования безопасности",
    ),
    "pp_2464": RegulatorySource(
        "pp_2464",
        "Постановление Правительства РФ от 24.12.2021 № 2464",
        "Порядок обучения по охране труда и проверки знания требований охраны труда",
    ),
}


# Read in the text of section III of Order 772n; each carries its paragraph.
_GENERAL: tuple[RegulatoryRequirement, ...] = (
    RegulatoryRequirement(
        "772n",
        "указан порядок оказания первой помощи",
        "не указан порядок оказания первой помощи пострадавшим",
        ("перв", "помощь пострадав", "аптечк", "медицинск"),
        paragraph="п. 25",
    ),
    RegulatoryRequirement(
        "772n",
        "указан порядок извещения о травме или неисправности",
        "не указан порядок извещения о травме или неисправности",
        ("сообщить", "извест", "уведом", "доложить"),
        paragraph="п. 22, 25",
    ),
    RegulatoryRequirement(
        "772n",
        "описаны действия по окончании работы",
        "не описаны действия по окончании работы",
        ("по окончании", "передать смену", "передача смены", "заверш"),
        paragraph="п. 26",
    ),
    RegulatoryRequirement(
        "772n",
        "указаны требования личной гигиены",
        "не указаны требования личной гигиены",
        ("гигиен", "вымыть руки", "снять спецодежду", "санитарн"),
        paragraph="п. 22, 26",
    ),
    RegulatoryRequirement(
        "772n",
        "указан режим работы и перерывов",
        "не указан режим работы и перерывов",
        ("режим работ", "перерыв", "время отдыха", "регламентированн"),
        paragraph="п. 22",
    ),
    RegulatoryRequirement(
        "772n",
        "названы опасные факторы и профессиональные риски",
        "не названы опасные факторы и профессиональные риски",
        ("опасн", "риск", "вредн", "фактор"),
        paragraph="п. 22",
    ),
    RegulatoryRequirement(
        "772n",
        "описана проверка оборудования и защитных устройств до работы",
        "не описана проверка оборудования и защитных устройств до работы",
        ("огражд", "защитн", "исправн", "блокиров"),
        paragraph="п. 23",
    ),
    RegulatoryRequirement(
        "772n",
        "описан порядок остановки и уборки рабочего места",
        "не описан порядок остановки и уборки рабочего места",
        ("отключ", "останов", "убрать", "очист", "отход"),
        paragraph="п. 26",
    ),
)


# Subject-level entries. The industry rules are named and in force; the specific
# paragraph was not verified against the official text, so none is claimed.
_BY_PROFILE: tuple[RegulatoryRequirement, ...] = (
    RegulatoryRequirement(
        "883n",
        "учтены работы на высоте и ограждение зоны работ",
        "не учтены работы на высоте или ограждение зоны работ",
        ("высот", "огражден", "страхов", "каск", "леса", "подмащ"),
        profiles=("construction",),
    ),
    RegulatoryRequirement(
        "833n",
        "учтено обесточивание и блокировка оборудования перед обслуживанием",
        "не учтено обесточивание или блокировка оборудования перед обслуживанием",
        ("обесточ", "блокиров", "отключ", "вывешен", "плакат"),
        profiles=("manufacturing",),
    ),
    RegulatoryRequirement(
        "835n",
        "учтена проверка исправности инструмента и приспособлений",
        "не учтена проверка исправности инструмента и приспособлений",
        ("инструмент", "приспособл", "исправн"),
        profiles=("manufacturing", "construction"),
    ),
    RegulatoryRequirement(
        "758n",
        "учтены работы в колодцах, подвалах или замкнутых пространствах",
        "не учтены требования к работам в замкнутых пространствах",
        ("колодец", "колодц", "замкнут", "загазован", "вентил", "подвал"),
        profiles=("housing_utilities",),
    ),
    RegulatoryRequirement(
        "871n",
        "учтен предрейсовый или предсменный контроль транспортного средства",
        "не учтен предрейсовый или предсменный контроль транспортного средства",
        ("предрейс", "предсмен", "осмотр транспорт", "техническое состояние"),
        profiles=("transport",),
    ),
    RegulatoryRequirement(
        "866n",
        "учтены санитарная обработка и требования к спецодежде",
        "не учтены санитарная обработка или требования к спецодежде",
        ("санитарн", "дезинф", "спецодежд", "мойк", "обработк"),
        profiles=("food_production",),
    ),
    RegulatoryRequirement(
        "928n",
        "учтены биологический фактор и обращение с медицинскими отходами",
        "не учтены биологический фактор или обращение с медицинскими отходами",
        ("биологическ", "инфекц", "отход", "дезинф", "стерилиз"),
        profiles=("healthcare",),
    ),
    RegulatoryRequirement(
        "881n",
        "учтены связь, оповещение и средства защиты органов дыхания",
        "не учтены связь, оповещение или средства защиты органов дыхания",
        ("связь", "оповещ", "органов дыхания", "сиз од", "звено"),
        profiles=("emergency_response",),
    ),
)

# Standards and the training rules. The two ЕСТД requirements carry paragraph
# numbers because they were read in the text of the standard; the rest are
# subject-level.
#
# ГОСТ 12.0.004-2015 is deliberately absent. It covers exactly this ground, but
# its application in Russia is suspended until 01.09.2026 in favour of Government
# Decree 2464, and citing a suspended standard to a safety engineer would cost
# more credibility than the extra check is worth.
_STANDARDS: tuple[RegulatoryRequirement, ...] = (
    RegulatoryRequirement(
        "gost_3_1105",
        "есть вводная часть с областью распространения и назначением",
        "не указаны область распространения и назначение документа",
        ("предназначена", "область применения", "распростран", "назначени"),
        paragraph="п. 6.4.2",
    ),
    RegulatoryRequirement(
        "gost_3_1105",
        "описание выполнено в технологической последовательности",
        "описание не выстроено в технологической последовательности",
        ("последовательн", "шаг", "этап", "порядок выполнения"),
        paragraph="п. 6.4.1",
    ),
    RegulatoryRequirement(
        "gost_12_2_003",
        "учтены органы управления, защитные устройства и аварийная остановка",
        "не учтены органы управления, защитные устройства или аварийная остановка",
        ("орган управления", "органов управления", "аварийн", "защитн", "блокиров"),
    ),
    RegulatoryRequirement(
        "gost_12_3_002",
        "названы меры устранения или снижения опасных производственных факторов",
        "не названы меры устранения или снижения опасных производственных факторов",
        ("устран", "исключ", "снизить", "не допускать", "предотврат"),
    ),
    RegulatoryRequirement(
        "pp_2464",
        "учтены инструктаж, стажировка или допуск к работе",
        "не учтены инструктаж, стажировка или допуск к работе",
        ("инструктаж", "стажировк", "допуск", "обучен", "проверка знаний"),
    ),
)


REQUIREMENTS: tuple[RegulatoryRequirement, ...] = _GENERAL + _STANDARDS + _BY_PROFILE


def requirements_for(profile: str) -> tuple[RegulatoryRequirement, ...]:
    return tuple(item for item in REQUIREMENTS if item.applies_to(profile))


def cited_documents(profile: str) -> tuple[str, ...]:
    keys = {item.source for item in requirements_for(profile)}
    return tuple(SOURCES[key].document for key in sorted(keys))
