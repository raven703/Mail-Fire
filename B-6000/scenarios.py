# -*- coding: utf-8 -*-
"""
Сценарийный каталог для корпуса B-6000.
"""

from dataclasses import dataclass
from typing import List

FIN_PLANS = "pack-ru2-financial-plans"
PRICING = "pack-ru2-pricing"

INDUSTRIES = [
    "manufacturing", "construction", "energy", "banking", "insurance",
    "logistics", "retail", "wholesale", "medicine", "pharma",
    "it", "telecom", "agriculture", "transport", "oil_gas",
    "consulting", "government_contractors", "ecommerce",
]

DIFFICULTIES = ["easy", "medium", "hard"]

TARGET_DISTRIBUTION = {
    "only_financial": 1200,
    "only_pricing": 1200,
    "both": 600,
    "safe_normal": 1500,
    "safe_hard": 1500,
}


@dataclass
class Scenario:
    group_id: str
    labels: List[str]
    industry: str
    scenario: str
    difficulty: str
    features: List[str]
    description: str
    target_length: str = "medium"
    priority: int = 1

FINANCIAL_SCENARIOS = []
PRICING_SCENARIOS = []
BOTH_SCENARIOS = []
SAFE_NORMAL_SCENARIOS = []
SAFE_HARD_SCENARIOS = []
# --- Financial plans scenarios (20 base + generated) ---
FINANCIAL_BASE = [
    ("SCN-FIN-0001", "manufacturing", "internal_budget_revision", "medium", ["implicit", "professional_jargon"],
     "Обсуждение пересмотра внутреннего бюджета производства на следующий квартал без точных сумм."),
    ("SCN-FIN-0002", "construction", "capex_equipment_purchase", "hard", ["implicit", "numbers_obfuscated"],
     "План закупки тяжелой техники для стройки, суммы замаскированы под даты."),
    ("SCN-FIN-0003", "energy", "revenue_forecast_q3", "medium", ["english_terms"],
     "Прогноз выручки энергосбытовой компании на Q3, обсуждение с директором по финансам."),
    ("SCN-FIN-0004", "banking", "liquidity_planning", "hard", ["implicit", "abbreviations"],
     "Внутренний прогноз ликвидности банка, обсуждение БДДС и БДР."),
    ("SCN-FIN-0005", "insurance", "claims_reserve_budget", "medium", ["professional_jargon"],
     "Бюджет резерва под страховые выплаты, неопубликованные показатели."),
    ("SCN-FIN-0006", "logistics", "fuel_cost_reduction_plan", "easy", ["short_form"],
     "План сокращения расходов на топливо в логистической компании."),
    ("SCN-FIN-0007", "retail", "payroll_fund_change", "medium", ["negation"],
     "Изменение фонда оплаты труда в розничной сети, обсуждение без прямых сумм."),
    ("SCN-FIN-0008", "wholesale", "project_financing_plan", "hard", ["implicit", "forwarded"],
     "План финансирования оптовой сделки, пересылка внутреннего документа."),
    ("SCN-FIN-0009", "medicine", "clinic_budget_2025", "medium", ["meeting_protocol"],
     "Протокол совещания по бюджету клиники на 2025 год."),
    ("SCN-FIN-0010", "pharma", "drug_procurement_budget", "medium", ["professional_jargon"],
     "Бюджет закупки лекарственных препаратов, внутреннее распределение."),
    ("SCN-FIN-0011", "it", "it_infrastructure_capex", "easy", ["english_terms", "typos"],
     "CAPEX на обновление ИТ-инфраструктуры, неопубликованные планы."),
    ("SCN-FIN-0012", "telecom", "network_expansion_forecast", "medium", ["abbreviations"],
     "Прогноз расширения сети связи, капитальные вложения."),
    ("SCN-FIN-0013", "agriculture", "seasonal_financing_plan", "hard", ["implicit", "transliteration"],
     "План сезонного финансирования агропредприятия, обфускация ключевых слов."),
    ("SCN-FIN-0014", "transport", "fleet_renewal_budget", "medium", ["professional_jargon"],
     "Бюджет обновления автопарка транспортной компании."),
    ("SCN-FIN-0015", "oil_gas", "drilling_program_budget", "hard", ["implicit", "document_excerpt"],
     "Бюджет буровой программы, выдержка из внутреннего документа."),
    ("SCN-FIN-0016", "consulting", "client_project_margin_forecast", "medium", ["implicit"],
     "Прогноз маржинальности консультационного проекта для клиента."),
    ("SCN-FIN-0017", "government_contractors", "government_contract_budget", "hard", ["implicit", "numbers_obfuscated"],
     "Бюджет госконтракта, неопубликованные показатели."),
    ("SCN-FIN-0018", "ecommerce", "marketing_budget_reallocation", "medium", ["english_terms"],
     "Перераспределение маркетингового бюджета интернет-магазина."),
    ("SCN-FIN-0019", "manufacturing", "ebitda_forecast_internal", "hard", ["implicit", "abbreviations"],
     "Внутренний прогноз EBITDA производственного предприятия до публикации."),
    ("SCN-FIN-0020", "banking", "credit_line_planning", "medium", ["professional_jargon"],
     "Планирование кредитной линии и заимствований банка."),
]

for gid, ind, scen, diff, feats, desc in FINANCIAL_BASE:
    FINANCIAL_SCENARIOS.append(Scenario(gid, [FIN_PLANS], ind, scen, diff, feats, desc))

for i in range(21, 241):
    industry = INDUSTRIES[(i - 1) % len(INDUSTRIES)]
    FINANCIAL_SCENARIOS.append(Scenario(
        f"SCN-FIN-{i:04d}", [FIN_PLANS], industry,
        f"financial_plan_variant_{i}",
        DIFFICULTIES[(i - 1) % 3],
        ["implicit", "professional_jargon"],
        f"Вариант финансового плана {i} для отрасли {industry}.",
        ["short", "medium", "long", "very_long"][(i - 1) % 4],
    ))

# --- Pricing scenarios (20 base + generated) ---
PRICING_BASE = [
    ("SCN-PRC-0001", "manufacturing", "individual_discount_agreement", "medium", ["implicit", "professional_jargon"],
     "Индивидуальная скидка для постоянного клиента производственной компании."),
    ("SCN-PRC-0002", "construction", "closed_price_list", "hard", ["implicit", "numbers_obfuscated"],
     "Закрытый прайс-лист на строительные материалы, не для широкой рассылки."),
    ("SCN-PRC-0003", "energy", "special_tariff_contract", "medium", ["english_terms"],
     "Специальный тариф для крупного потребителя энергии."),
    ("SCN-PRC-0004", "banking", "loan_rate_individual", "hard", ["implicit", "abbreviations"],
     "Индивидуальная процентная ставка по кредиту, закрытые условия."),
    ("SCN-PRC-0005", "insurance", "premium_coefficient_client", "medium", ["professional_jargon"],
     "Персональный коэффициент страховой премии для корпоративного клиента."),
    ("SCN-PRC-0006", "logistics", "delivery_discount_corporate", "easy", ["short_form"],
     "Корпоративная скидка на доставку для регулярного клиента."),
    ("SCN-PRC-0007", "retail", "purchase_price_supplier", "medium", ["negation"],
     "Закупочные цены от поставщика, не для публикации."),
    ("SCN-PRC-0008", "wholesale", "tender_conditions_confidential", "hard", ["implicit", "forwarded"],
     "Условия тендера, непубличные коммерческие параметры."),
    ("SCN-PRC-0009", "medicine", "medical_equipment_dealer_price", "medium", ["meeting_protocol"],
     "Дилерские цены на медицинское оборудование."),
    ("SCN-PRC-0010", "pharma", "pharmacy_retrobonus", "medium", ["professional_jargon"],
     "Ретробонусы для аптечной сети, скрытые коммерческие условия."),
    ("SCN-PRC-0011", "it", "saas_custom_tariff", "easy", ["english_terms", "typos"],
     "Индивидуальный тариф SaaS-подписки для корпоративного клиента."),
    ("SCN-PRC-0012", "telecom", "interconnect_rate_agreement", "medium", ["abbreviations"],
     "Согласование ставок интерконнекта между операторами связи."),
    ("SCN-PRC-0013", "agriculture", "fertilizer_volume_discount", "hard", ["implicit", "transliteration"],
     "Скидка по объёму закупки удобрений, обфускация терминов."),
    ("SCN-PRC-0014", "transport", "freight_contract_rate", "medium", ["professional_jargon"],
     "Ставка по грузовому договору, индивидуальные условия поставки."),
    ("SCN-PRC-0015", "oil_gas", "oil_supply_contract_price", "hard", ["implicit", "document_excerpt"],
     "Цена контракта на поставку нефтепродуктов, выдержка из документа."),
    ("SCN-PRC-0016", "consulting", "consulting_hourly_rate", "medium", ["implicit"],
     "Часовая ставка консультационных услуг, не для разглашения."),
    ("SCN-PRC-0017", "government_contractors", "government_tender_price", "hard", ["implicit", "numbers_obfuscated"],
     "Ценовое предложение по гос тендеру, закрытые параметры."),
    ("SCN-PRC-0018", "ecommerce", "marketplace_commission_agreement", "medium", ["english_terms"],
     "Соглашение о комиссии маркетплейса с продавцом."),
    ("SCN-PRC-0019", "manufacturing", "minimal_resale_price", "hard", ["implicit", "abbreviations"],
     "Минимально допустимая цена продажи партнёру, неопубликованная."),
    ("SCN-PRC-0020", "banking", "deposit_rate_premium", "medium", ["professional_jargon"],
     "Повышенная ставка по вкладу для VIP-клиента, индивидуальные условия."),
]

for gid, ind, scen, diff, feats, desc in PRICING_BASE:
    PRICING_SCENARIOS.append(Scenario(gid, [PRICING], ind, scen, diff, feats, desc))

for i in range(21, 241):
    industry = INDUSTRIES[(i - 1) % len(INDUSTRIES)]
    PRICING_SCENARIOS.append(Scenario(
        f"SCN-PRC-{i:04d}", [PRICING], industry,
        f"pricing_variant_{i}",
        DIFFICULTIES[(i - 1) % 3],
        ["implicit", "professional_jargon"],
        f"Вариант коммерческих условий {i} для отрасли {industry}.",
        ["short", "medium", "long", "very_long"][(i - 1) % 4],
    ))

# --- Both categories scenarios (5 base + generated) ---
BOTH_BASE = [
    ("SCN-BOTH-0001", "manufacturing", "budget_and_price_negotiation", "hard", ["implicit", "professional_jargon"],
     "Обсуждение бюджета производства и оптовых цен с дистрибьютором в одном письме."),
    ("SCN-BOTH-0002", "construction", "project_budget_and_subcontractor_rates", "medium", ["implicit"],
     "Бюджет проекта и ставки субподрядчиков, закрытая переписка."),
    ("SCN-BOTH-0003", "banking", "credit_department_budget_and_rates", "hard", ["abbreviations", "implicit"],
     "Бюджет кредитного отдела и процентные ставки по вкладам."),
    ("SCN-BOTH-0004", "retail", "marketing_budget_and_supplier_discounts", "medium", ["english_terms"],
     "Маркетинговый бюджет сети и скидки от поставщиков."),
    ("SCN-BOTH-0005", "it", "it_budget_and_saas_pricing", "easy", ["english_terms", "short_form"],
     "ИТ-бюджет и тарифы на облачные сервисы."),
]

for gid, ind, scen, diff, feats, desc in BOTH_BASE:
    BOTH_SCENARIOS.append(Scenario(gid, [FIN_PLANS, PRICING], ind, scen, diff, feats, desc))

for i in range(6, 181):
    industry = INDUSTRIES[(i - 1) % len(INDUSTRIES)]
    BOTH_SCENARIOS.append(Scenario(
        f"SCN-BOTH-{i:04d}", [FIN_PLANS, PRICING], industry,
        f"mixed_financial_pricing_{i}",
        DIFFICULTIES[(i - 1) % 3],
        ["implicit", "professional_jargon"],
        f"Смешанный сценарий финансовых планов и цен {i} для {industry}.",
        ["short", "medium", "long", "very_long"][(i - 1) % 4],
    ))

# --- Safe normal scenarios (20 base + generated) ---
SAFE_NORMAL_BASE = [
    ("SCN-SAFE-0001", "manufacturing", "vacation_request", "easy", ["short_form"],
     "Запрос на отпуск сотрудника завода."),
    ("SCN-SAFE-0002", "it", "it_support_ticket", "easy", ["english_terms"],
     "Обращение в техническую поддержку по поводу нерабочего ноутбука."),
    ("SCN-SAFE-0003", "retail", "meeting_organization", "easy", ["short_form"],
     "Организация еженедельного совещания отдела продаж."),
    ("SCN-SAFE-0004", "logistics", "cargo_tracking_inquiry", "easy", ["short_form"],
     "Запрос отслеживания груза клиентом."),
    ("SCN-SAFE-0005", "medicine", "medical_leave_certificate", "easy", ["short_form"],
     "Оформление больничного листа сотруднику клиники."),
    ("SCN-SAFE-0006", "construction", "equipment_maintenance_schedule", "medium", ["professional_jargon"],
     "График обслуживания строительной техники."),
    ("SCN-SAFE-0007", "banking", "employee_training_session", "medium", ["meeting_protocol"],
     "Обучение сотрудников банка новым правилам безопасности."),
    ("SCN-SAFE-0008", "insurance", "stationery_order", "easy", ["short_form"],
     "Заказ канцелярских принадлежностей для офиса страховой компании."),
    ("SCN-SAFE-0009", "energy", "business_trip_request", "medium", ["short_form"],
     "Запрос на командировку на энергообъект."),
    ("SCN-SAFE-0010", "telecom", "network_incident_report", "medium", ["professional_jargon"],
     "Отчёт об инциденте на сетевом оборудовании."),
    ("SCN-SAFE-0011", "pharma", "document_approval_workflow", "medium", ["abbreviations"],
     "Согласование фармацевтического документа через внутренний workflow."),
    ("SCN-SAFE-0012", "transport", "driver_schedule_change", "easy", ["short_form"],
     "Изменение графика работы водителя транспортной компании."),
    ("SCN-SAFE-0013", "oil_gas", "rig_inspection_notification", "medium", ["professional_jargon"],
     "Уведомление о проверке буровой установки."),
    ("SCN-SAFE-0014", "consulting", "client_meeting_reschedule", "easy", ["short_form"],
     "Перенос встречи с клиентом консалтинговой компании."),
    ("SCN-SAFE-0015", "government_contractors", "permit_document_request", "medium", ["abbreviations"],
     "Запрос выписки из разрешительной документации у госзаказчика."),
    ("SCN-SAFE-0016", "ecommerce", "customer_congratulations", "easy", ["short_form"],
     "Поздравление клиента с днём рождения от интернет-магазина."),
    ("SCN-SAFE-0017", "wholesale", "task_completion_report", "medium", ["professional_jargon"],
     "Отчёт о выполненной задаче по оптовой поставке товара."),
    ("SCN-SAFE-0018", "manufacturing", "quality_control_meeting", "medium", ["meeting_protocol"],
     "Протокол совещания отдела контроля качества завода."),
    ("SCN-SAFE-0019", "logistics", "customs_clearance_notice", "medium", ["abbreviations"],
     "Уведомление о таможенном оформлении груза."),
    ("SCN-SAFE-0020", "energy", "power_outage_notification", "easy", ["short_form"],
     "Уведомление о плановом отключении электричества."),
]

for gid, ind, scen, diff, feats, desc in SAFE_NORMAL_BASE:
    SAFE_NORMAL_SCENARIOS.append(Scenario(gid, [], ind, scen, diff, feats, desc))

for i in range(21, 501):
    industry = INDUSTRIES[(i - 1) % len(INDUSTRIES)]
    SAFE_NORMAL_SCENARIOS.append(Scenario(
        f"SCN-SAFE-{i:04d}", [], industry,
        f"safe_business_{i}",
        DIFFICULTIES[(i - 1) % 3],
        ["short_form", "professional_jargon"],
        f"Обычное безопасное деловое письмо {i} в отрасли {industry}.",
        ["short", "medium", "long"][(i - 1) % 3],
    ))

# --- Safe hard / hard negatives scenarios ---
SAFE_HARD_BASE = [
    ("SCN-HARD-0001", "manufacturing", "public_price_list_distribution", "medium", ["public_doc"],
     "Рассылка публичного прайс-листа с обычными скидками, не содержащая закрытых условий."),
    ("SCN-HARD-0002", "retail", "public_discount_promo", "easy", ["public_doc"],
     "Рекламное письмо о публичной скидке 10% для всех клиентов."),
    ("SCN-HARD-0003", "banking", "published_annual_report", "medium", ["public_doc", "abbreviations"],
     "Ссылка на опубликованную годовую финансовую отчётность банка."),
    ("SCN-HARD-0004", "it", "budgeting_tutorial_example", "medium", ["educational"],
     "Учебный пример бюджетирования с вымышленными цифрами для обучения новых сотрудников."),
    ("SCN-HARD-0005", "construction", "empty_budget_template", "easy", ["template"],
     "Пустой шаблон бюджета проекта без заполненных значений."),
    ("SCN-HARD-0006", "insurance", "rfq_no_terms_disclosed", "medium", ["negation"],
     "Запрос коммерческого предложения без раскрытия специальных условий."),
    ("SCN-HARD-0007", "logistics", "budget_request_no_disclosure", "medium", ["negation"],
     "Запрос бюджета от партнёра без передачи собственных цифр."),
    ("SCN-HARD-0008", "pharma", "refusal_to_disclose", "hard", ["negation", "implicit"],
     "Отказ передавать конфиденциальную информацию по запросу контрагента."),
    ("SCN-HARD-0009", "telecom", "document_security_instruction", "medium", ["instruction"],
     "Инструкция по защите финансовых документов и прайсов."),
    ("SCN-HARD-0010", "energy", "public_tender_conditions", "medium", ["public_doc"],
     "Публичные условия тендера без закрытых коммерческих параметров."),
    ("SCN-HARD-0011", "manufacturing", "standard_tariff_discussion", "medium", ["abbreviations"],
     "Обсуждение стандартных тарифов, опубликованных на сайте компании."),
    ("SCN-HARD-0012", "wholesale", "discount_without_individual_terms", "medium", ["negation"],
     "Упоминание скидок без раскрытия индивидуальных условий конкретной сделки."),
    ("SCN-HARD-0013", "retail", "historical_published_financials", "hard", ["public_doc"],
     "Исторические финансовые данные, официально опубликованные компанией."),
    ("SCN-HARD-0014", "banking", "personal_finance_question", "easy", ["short_form"],
     "Личный финансовый вопрос сотрудника о кредитной карте."),
    ("SCN-HARD-0015", "consulting", "false_friend_terminology", "hard", ["implicit", "negation"],
     "Обсуждение финансовой терминологии, где слова напоминают чувствительные, но не являются таковыми."),
    ("SCN-HARD-0016", "agriculture", "economic_news_discussion", "medium", ["english_terms"],
     "Обсуждение новостей экономики в отраслевой рассылке."),
    ("SCN-HARD-0017", "transport", "financial_planning_program", "medium", ["educational"],
     "Обсуждение программы финансового планирования для сотрудников."),
    ("SCN-HARD-0018", "oil_gas", "discount_approval_rules_no_params", "medium", ["instruction"],
     "Правила согласования скидок без раскрытия закрытых коммерческих параметров."),
    ("SCN-HARD-0019", "ecommerce", "quote_request_blank_template", "easy", ["template"],
     "Запрос котировок на пустом бланке без указания цен."),
    ("SCN-HARD-0020", "manufacturing", "leak_with_disclosure_in_quote", "hard", ["implicit", "leak_via_quote"],
     "Письмо отказывает в раскрытии сведений, но цитирует приложение с бюджетом — положительный по смыслу."),
]

for gid, ind, scen, diff, feats, desc in SAFE_HARD_BASE:
    SAFE_HARD_SCENARIOS.append(Scenario(gid, [], ind, scen, diff, feats, desc))

for i in range(21, 501):
    industry = INDUSTRIES[(i - 1) % len(INDUSTRIES)]
    SAFE_HARD_SCENARIOS.append(Scenario(
        f"SCN-HARD-{i:04d}",
        [],
        industry,
        f"hard_negative_variant_{i}",
        DIFFICULTIES[(i - 1) % 3],
        ["implicit", "professional_jargon"],
        f"Сложный безопасный сценарий {i} для {industry}",
        ["short", "medium", "long"][(i - 1) % 3],
    ))

# --- Unified catalog ---
ALL_SCENARIOS = (
    FINANCIAL_SCENARIOS
    + PRICING_SCENARIOS
    + BOTH_SCENARIOS
    + SAFE_NORMAL_SCENARIOS
    + SAFE_HARD_SCENARIOS
)

if __name__ == "__main__":
    print(f"Всего сценариев: {len(ALL_SCENARIOS)}")
    from collections import Counter
    label_counts = Counter()
    for s in ALL_SCENARIOS:
        key = tuple(sorted(s.labels))
        label_counts[key] += 1
    for k, v in sorted(label_counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print(f"Уникальных group_id: {len(set(s.group_id for s in ALL_SCENARIOS))}")