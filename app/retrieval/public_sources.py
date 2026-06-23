import math
import re
from dataclasses import dataclass

from app.schemas.instruction import ContextGenerationRequest, IndustryProfile, RetrievedSource


TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")


@dataclass(frozen=True)
class PublicSource:
    source_id: str
    title: str
    url: str
    authority: str
    document_type: str
    keywords: tuple[str, ...]
    instruction_types: tuple[str, ...]
    excerpt: str
    profiles: tuple[IndustryProfile, ...] = ("general",)


PUBLIC_SOURCE_CATALOG: tuple[PublicSource, ...] = (
    PublicSource(
        source_id="public_tr_ts_010_2011",
        title="ТР ТС 010/2011. О безопасности машин и оборудования",
        url="https://docs.cntd.ru/document/902307904",
        authority="Комиссия Таможенного союза",
        document_type="Технический регламент",
        keywords=("машины", "оборудование", "безопасность", "эксплуатация", "пуск", "останов", "риски"),
        instruction_types=("general", "equipment_startup", "equipment_shutdown", "maintenance", "inspection"),
        excerpt=(
            "Использовать как ориентир для требований безопасности машин и оборудования: "
            "оценка рисков, безопасная эксплуатация, предупреждение опасных действий, "
            "проверка защитных устройств и ограничение доступа к опасным зонам."
        ),
    ),
    PublicSource(
        source_id="public_gost_12_2_003_91",
        title="ГОСТ 12.2.003-91. Оборудование производственное. Общие требования безопасности",
        url="https://docs.cntd.ru/document/1200004631",
        authority="Межгосударственный совет по стандартизации",
        document_type="ГОСТ / ССБТ",
        keywords=("производственное", "оборудование", "ограждение", "блокировка", "опасная", "зона", "безопасность"),
        instruction_types=("general", "workplace_preparation", "equipment_startup", "inspection", "maintenance"),
        excerpt=(
            "Полезен для формулирования базовых требований к производственному оборудованию: "
            "опасные зоны, ограждения, блокировки, предупредительная маркировка, доступность органов управления "
            "и запрет работы при неисправных защитных элементах."
        ),
    ),
    PublicSource(
        source_id="public_gost_12_0_004_2015",
        title="ГОСТ 12.0.004-2015. Организация обучения безопасности труда",
        url="https://docs.cntd.ru/document/1200136072",
        authority="Межгосударственный совет по стандартизации",
        document_type="ГОСТ / ССБТ",
        keywords=("обучение", "инструктаж", "стажировка", "проверка", "знаний", "допуск", "безопасность"),
        instruction_types=("training", "workplace_preparation", "general"),
        excerpt=(
            "Подходит для учебных инструкций и onboarding-сценариев: фиксировать цель обучения, "
            "границы самостоятельных действий, проверку понимания, роль наставника и необходимость допуска."
        ),
    ),
    PublicSource(
        source_id="public_gost_12_4_011_89",
        title="ГОСТ 12.4.011-89. Средства защиты работающих. Общие требования и классификация",
        url="https://docs.cntd.ru/document/1200000277",
        authority="Госстандарт СССР / ССБТ",
        document_type="ГОСТ / ССБТ",
        keywords=("сиз", "средства", "защиты", "очки", "перчатки", "спецодежда", "классификация"),
        instruction_types=("general", "workplace_preparation", "equipment_startup", "maintenance", "inspection", "training"),
        excerpt=(
            "Использовать как справочный источник для раздела СИЗ: подбирать защиту по виду опасности "
            "и характеру работ, отдельно отмечать ограничения использования перчаток рядом с движущимися частями."
        ),
    ),
    PublicSource(
        source_id="public_mintrud_776n_suot",
        title="Приказ Минтруда России N 776н. Примерное положение о системе управления охраной труда",
        url="https://www.consultant.ru/document/cons_doc_LAW_405174/",
        authority="Минтруд России",
        document_type="Нормативный акт / охрана труда",
        keywords=("суот", "охрана", "труда", "риски", "работодатель", "процедуры", "управление"),
        instruction_types=("general", "training", "inspection", "maintenance", "workplace_preparation"),
        excerpt=(
            "Полезен для управленческих разделов инструкции: распределение ответственности, управление рисками, "
            "процедуры охраны труда, фиксация отклонений и необходимость проверки документа ответственными лицами."
        ),
    ),
    PublicSource(
        source_id="public_mintrud_833n",
        title="Правила по охране труда при размещении, монтаже, техническом обслуживании и ремонте технологического оборудования",
        url="https://www.consultant.ru/document/cons_doc_LAW_371725/",
        authority="Минтруд России",
        document_type="Правила по охране труда",
        keywords=("монтаж", "ремонт", "техническое", "обслуживание", "технологическое", "оборудование", "наряд", "допуск"),
        instruction_types=("maintenance", "inspection", "general", "equipment_shutdown"),
        excerpt=(
            "Применим к инструкциям обслуживания и ремонта: до начала работ определить границы операции, "
            "ответственных лиц, безопасное состояние оборудования, порядок допуска, инструмент и фиксацию дефектов."
        ),
    ),
    PublicSource(
        source_id="public_ppr_1479",
        title="Постановление Правительства РФ N 1479. Правила противопожарного режима",
        url="https://www.consultant.ru/document/cons_doc_LAW_367025/",
        authority="Правительство РФ",
        document_type="Правила пожарной безопасности",
        keywords=("пожар", "огонь", "эвакуация", "горючие", "материалы", "помещение", "авария"),
        instruction_types=("general", "workplace_preparation", "maintenance", "training"),
        excerpt=(
            "Использовать для пожарной части инструкции: не загромождать проходы, учитывать горючие материалы, "
            "фиксировать действия при пожаре и не допускать работ при нарушении противопожарных требований."
        ),
    ),
    PublicSource(
        source_id="public_sp_3670_20",
        title="СП 2.2.3670-20. Санитарно-эпидемиологические требования к условиям труда",
        url="https://docs.cntd.ru/document/566479118",
        authority="Главный государственный санитарный врач РФ",
        document_type="Санитарные правила",
        keywords=("условия", "труда", "санитарные", "шум", "вибрация", "микроклимат", "освещение"),
        instruction_types=("general", "inspection", "workplace_preparation", "training"),
        excerpt=(
            "Полезен для проверки условий труда: освещение, шум, вибрация, микроклимат, чистота рабочего места "
            "и необходимость эскалации при небезопасных или некомфортных условиях."
        ),
    ),
    PublicSource(
        source_id="public_pot_electro_903n",
        title="Правила по охране труда при эксплуатации электроустановок",
        url="https://www.consultant.ru/document/cons_doc_LAW_372376/",
        authority="Минтруд России",
        document_type="Правила по охране труда",
        keywords=("электроустановка", "электро", "напряжение", "блокировка", "отключение", "допуск", "энергия"),
        instruction_types=("maintenance", "inspection", "equipment_startup", "equipment_shutdown", "general"),
        excerpt=(
            "Подключать, когда операция затрагивает электрические шкафы, питание, отключение энергии или допуск: "
            "инструкция должна требовать проверки полномочий, безопасного состояния и запрета самовольных действий."
        ),
    ),
    PublicSource(
        source_id="public_consultant_ot_catalog",
        title="Открытый каталог нормативных актов по охране труда",
        url="https://www.consultant.ru/document/cons_doc_LAW_34683/",
        authority="КонсультантПлюс / правовая справочная система",
        document_type="Справочный каталог",
        keywords=("охрана", "труда", "правила", "инструкции", "нормативные", "акты", "справочник"),
        instruction_types=("general", "training", "maintenance", "inspection", "workplace_preparation", "equipment_startup", "equipment_shutdown"),
        excerpt=(
            "Использовать как навигационный справочник: при реальном внедрении подобрать отраслевые правила, "
            "инструкции и локальные документы именно под вид работ, участок и оборудование."
        ),
    ),
    PublicSource(
        source_id="public_gost_12_1_019_2017",
        title="ГОСТ 12.1.019-2017. Электробезопасность. Общие требования и номенклатура видов защиты",
        url="https://docs.cntd.ru/document/1200157557",
        authority="Межгосударственный совет по стандартизации",
        document_type="ГОСТ / ССБТ",
        keywords=("электробезопасность", "напряжение", "защита", "электрический", "ток", "оборудование", "допуск"),
        instruction_types=("equipment_startup", "equipment_shutdown", "inspection", "maintenance", "general"),
        excerpt=(
            "Полезен для операций, где есть электрические шкафы, питание, кабели или риск поражения током: "
            "отмечать запрет самостоятельного доступа без допуска и необходимость проверки безопасного состояния."
        ),
    ),
    PublicSource(
        source_id="public_gost_12_1_004_91",
        title="ГОСТ 12.1.004-91. Пожарная безопасность. Общие требования",
        url="https://docs.cntd.ru/document/9051953",
        authority="Госстандарт СССР / ССБТ",
        document_type="ГОСТ / ССБТ",
        keywords=("пожарная", "безопасность", "горючие", "материалы", "искры", "огонь", "эвакуация"),
        instruction_types=("general", "workplace_preparation", "maintenance", "training", "inspection"),
        excerpt=(
            "Использовать для базовых пожарных требований: убрать горючие материалы из зоны работ, "
            "не блокировать проходы и фиксировать действия при признаках возгорания."
        ),
    ),
    PublicSource(
        source_id="public_gost_12_3_002_2014",
        title="ГОСТ 12.3.002-2014. Процессы производственные. Общие требования безопасности",
        url="https://docs.cntd.ru/document/1200114628",
        authority="Межгосударственный совет по стандартизации",
        document_type="ГОСТ / ССБТ",
        keywords=("производственные", "процессы", "операция", "последовательность", "безопасность", "контроль", "технологический"),
        instruction_types=("general", "workplace_preparation", "equipment_startup", "equipment_shutdown", "inspection", "maintenance"),
        excerpt=(
            "Подходит для структуры производственной инструкции: безопасная последовательность действий, "
            "контроль исходного и итогового состояния, предотвращение опасных отклонений процесса."
        ),
    ),
    PublicSource(
        source_id="public_mintrud_290n_siz",
        title="Правила обеспечения работников средствами индивидуальной защиты и смывающими средствами",
        url="https://www.consultant.ru/document/cons_doc_LAW_447921/",
        authority="Минтруд России",
        document_type="Правила обеспечения СИЗ",
        keywords=("сиз", "средства", "индивидуальной", "защиты", "смывающие", "выдача", "работники", "риски"),
        instruction_types=("general", "workplace_preparation", "training", "maintenance", "inspection", "equipment_startup"),
        excerpt=(
            "Использовать для раздела СИЗ: защита должна соответствовать выявленным опасностям и виду работ, "
            "а поврежденные или неподходящие средства нельзя применять."
        ),
    ),
    PublicSource(
        source_id="public_rospotrebnadzor_labor_conditions",
        title="Роспотребнадзор. Требования к условиям труда и производственной среде",
        url="https://www.rospotrebnadzor.ru/",
        authority="Роспотребнадзор",
        document_type="Официальный справочный ресурс",
        keywords=("условия", "труда", "производственная", "среда", "санитарные", "гигиена", "шум", "освещение"),
        instruction_types=("general", "workplace_preparation", "inspection", "training"),
        excerpt=(
            "Использовать как ориентир для гигиенических факторов рабочего места: чистота, освещение, шум, "
            "вибрация, микроклимат и необходимость передачи замечаний ответственному лицу."
        ),
    ),
)


def retrieve_public_sources(request: ContextGenerationRequest, max_sources: int) -> list[RetrievedSource]:
    if max_sources <= 0:
        return []
    query_tokens = _tokens(_request_query(request))
    ranked = []
    for source in PUBLIC_SOURCE_CATALOG:
        score = _score_source(source, request.instruction_type, request.industry_profile, query_tokens)
        if score > 0:
            ranked.append((source, score))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return [
        RetrievedSource(
            source_id=source.source_id,
            title=source.title,
            path=source.url,
            chunk_index=1,
            score=round(score, 4),
            excerpt=_public_excerpt(source),
            source_type="public",
            url=source.url,
            influence_score=_influence_score(score),
            matched_terms=sorted(_tokens(_request_query(request)) & _source_tokens(source))[:8],
            authority=source.authority,
            document_type=source.document_type,
            applicable_profiles=list(_source_profiles(source)),
            contribution_reason=_contribution_reason(source, request, query_tokens),
        )
        for source, score in ranked[:max_sources]
    ]


def _request_query(request: ContextGenerationRequest) -> str:
    return " ".join(
        part
        for part in [
            request.task,
            request.operation_name or "",
            request.industry_profile,
            request.department or "",
            request.equipment or "",
            request.technical_context or "",
            request.instruction_type,
        ]
        if part
    )


def _score_source(
    source: PublicSource,
    instruction_type: str,
    industry_profile: str,
    query_tokens: set[str],
) -> float:
    source_tokens = _source_tokens(source)
    overlap = query_tokens & source_tokens
    lexical = len(overlap) / math.sqrt(max(len(source_tokens), 1))
    type_boost = 0.45 if instruction_type in source.instruction_types else 0.0
    profile_boost = 0.55 if industry_profile in _source_profiles(source) else 0.0
    broad_safety_boost = 0.18 if {"безопасн", "охран", "риск", "опасн"} & query_tokens else 0.0
    return lexical + type_boost + profile_boost + broad_safety_boost


def _source_tokens(source: PublicSource) -> set[str]:
    source_tokens = set()
    for text in (source.title, source.authority, source.document_type, source.excerpt, " ".join(source.keywords)):
        source_tokens.update(_tokens(text))
    return source_tokens


def _source_profiles(source: PublicSource) -> tuple[IndustryProfile, ...]:
    explicit = set(source.profiles)
    text = " ".join([source.title, source.document_type, source.excerpt, " ".join(source.keywords)]).lower()
    if any(word in text for word in ["машин", "оборудован", "производствен", "технологическ", "станок"]):
        explicit.add("manufacturing")
    if any(word in text for word in ["монтаж", "строител", "высот", "огнев"]):
        explicit.add("construction")
    if any(word in text for word in ["охрана труда", "охран", "суот", "инструктаж", "допуск"]):
        explicit.add("occupational_safety")
    if any(word in text for word in ["пожар", "эвакуац", "авар"]):
        explicit.add("emergency_response")
    if any(word in text for word in ["санитар", "гигиен", "микроклимат", "условия труда"]):
        explicit.add("healthcare")
        explicit.add("food_production")
    if any(word in text for word in ["транспорт", "путев", "предрейс"]):
        explicit.add("transport")
    if any(word in text for word in ["обучен", "инструктаж", "стажиров", "наставник", "проверка знаний"]):
        explicit.add("education")
    if any(word in text for word in ["норматив", "правительств", "министерств", "административ", "процедур"]):
        explicit.add("public_service")
    if any(word in text for word in ["коммуналь", "жкх", "помещение", "эксплуатация здан", "эвакуацион"]):
        explicit.add("housing_utilities")
    if any(word in text for word in ["информацион", "персональн", "доступ", "ссылка", "учетн"]):
        explicit.add("information_security")
    explicit.add("general")
    ordered_profiles: tuple[IndustryProfile, ...] = (
        "manufacturing",
        "construction",
        "occupational_safety",
        "emergency_response",
        "public_service",
        "housing_utilities",
        "healthcare",
        "education",
        "food_production",
        "transport",
        "information_security",
        "general",
    )
    return tuple(profile for profile in ordered_profiles if profile in explicit)


def _contribution_reason(source: PublicSource, request: ContextGenerationRequest, query_tokens: set[str]) -> str:
    reasons = []
    if request.industry_profile in _source_profiles(source):
        reasons.append("совпадает с выбранным отраслевым профилем")
    if request.instruction_type in source.instruction_types:
        reasons.append("подходит к выбранному типу инструкции")
    matched_terms = sorted(query_tokens & _source_tokens(source))[:5]
    if matched_terms:
        reasons.append(f"совпали термины: {', '.join(matched_terms)}")
    if not reasons:
        reasons.append("используется как общий справочный источник для экспертной проверки")
    return f"Источник выбран, потому что {', '.join(reasons)}."


def _influence_score(score: float) -> float:
    if score <= 0:
        return 0.0
    return round(min(1.0, score / (score + 0.5)), 3)


def _public_excerpt(source: PublicSource) -> str:
    return (
        f"Открытый источник. Тип: {source.document_type}. Орган/площадка: {source.authority}. "
        f"{source.excerpt} Нормативный статус, редакцию и применимость нужно подтвердить перед внедрением."
    )


def _tokens(text: str) -> set[str]:
    return {
        _normalize(token)
        for token in TOKEN_RE.findall(text.lower().replace("ё", "е"))
        if len(_normalize(token)) >= 4
    }


def _normalize(token: str) -> str:
    replacements = {
        "безопасность": "безопасн",
        "безопасности": "безопасн",
        "безопасный": "безопасн",
        "опасность": "опасн",
        "опасные": "опасн",
        "опасных": "опасн",
        "охрана": "охран",
        "охране": "охран",
        "труда": "труд",
        "труд": "труд",
        "оборудование": "оборудован",
        "оборудования": "оборудован",
        "оборудованием": "оборудован",
        "обслуживание": "обслуживан",
        "обслуживания": "обслуживан",
        "ремонт": "ремонт",
        "ремонте": "ремонт",
        "запуск": "запуск",
        "запуска": "запуск",
        "остановка": "останов",
        "остановить": "останов",
        "подготовка": "подготовк",
        "подготовить": "подготовк",
        "инструктаж": "инструктаж",
        "обучение": "обучен",
        "обучения": "обучен",
    }
    if token in replacements:
        return replacements[token]
    endings = ("иями", "ями", "ами", "ого", "ему", "ыми", "ими", "ить", "ать", "ией", "ия", "ий", "ый", "ой", "ые", "ая", "ое", "ов", "ев", "ам", "ям", "ах", "ях", "ом", "ем", "а", "я", "ы", "и", "у", "ю", "е")
    for ending in endings:
        if token.endswith(ending) and len(token) - len(ending) >= 4:
            return token[: -len(ending)]
    return token
