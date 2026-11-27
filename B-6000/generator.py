# -*- coding: utf-8 -*-
"""
Генератор синтетического корпуса B-6000.
"""

import json
import random
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from scenarios import (
    ALL_SCENARIOS, FINANCIAL_SCENARIOS, PRICING_SCENARIOS, BOTH_SCENARIOS,
    SAFE_NORMAL_SCENARIOS, SAFE_HARD_SCENARIOS,
    FIN_PLANS, PRICING, INDUSTRIES, DIFFICULTIES,
    TARGET_DISTRIBUTION,
)

random.seed(42)

FIRST_NAMES = [
    "Александр", "Дмитрий", "Сергей", "Андрей", "Алексей",
    "Елена", "Ольга", "Наталья", "Татьяна", "Марина",
    "Иван", "Михаил", "Николай", "Виктор", "Игорь",
    "Анна", "Мария", "Екатерина", "Ирина", "Светлана",
]
LAST_NAMES = [
    "Иванов", "Петров", "Смирнов", "Кузнецов", "Попов",
    "Васильев", "Соколов", "Михайлов", "Новиков", "Федоров",
    "Морозов", "Алексеев", "Лебедев", "Семёнов", "Егоров",
    "Павлова", "Козлова", "Смирнова", "Иванова", "Петрова",
]
COMPANIES = [
    "ООО «СпецМонтаж»", "ПАО «ЭнергоГрупп»", "ЗАО «МеталлИнвест»",
    "ООО «ЛогистикаПлюс»", "ИП Соколов А.В.", "ООО «МедиКом»",
    "ПАО «БанкРазвития»", "ООО «АгроПрод»", "ЗАО «СтройИндустрия»",
    "ООО «ТрейдРегион»", "ООО «ФармаСити»", "ПАО «ТелекомСеть»",
    "ООО «КонсалтингПро»", "ООО «ТорговыйДом»", "ООО «АвтоСервис»",
    "ЗАО «НефтеГазИнж»", "ООО «РозницаМаркет»", "ООО «ОптТорговля»",
    "ПАО «СтраховоеДом»", "ООО «ИТРешения»",
]
DEPARTMENTS = [
    "отдел финансов", "бухгалтерия", "коммерческий отдел",
    "отдел закупок", "отдел продаж", "юридическая служба",
    "отдел логистики", "кадровый отдел", "IT-отдел",
    "отдел маркетинга", "отдел развития", "финансовый контроль",
]
POSITIONS = [
    "финансовый директор", "коммерческий директор", "главный бухгалтер",
    "менеджер по продажам", "руководитель отдела закупок",
    "юрисконсульт", "логист", "HR-менеджер",
    "системный администратор", "маркетолог", "директор по развитию",
    "контролер", "ассистент директора",
]
CITIES = [
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург",
    "Казань", "Нижний Новгород", "Самара", "Омск", "Челябинск",
    "Ростов-на-Дону", "Уфа", "Красноярск", "Воронеж", "Пермь",
]
CURRENCIES = ["руб.", "рублей", "USD", "EUR", "тыс. руб.", "млн руб."]
MONTHS_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def rand_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def rand_company() -> str:
    return random.choice(COMPANIES)


def rand_position() -> str:
    return random.choice(POSITIONS)


def rand_department() -> str:
    return random.choice(DEPARTMENTS)


def rand_city() -> str:
    return random.choice(CITIES)


def rand_date() -> str:
    d = datetime.now() - timedelta(days=random.randint(0, 180))
    return f"{d.day} {MONTHS_RU[d.month - 1]} {d.year}"


def rand_amount() -> str:
    return f"{random.randint(10, 999)} {random.choice(CURRENCIES)}"


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def add_typos(text: str, prob: float = 0.02) -> str:
    if random.random() > prob:
        return text
    chars = list(text)
    n_typos = max(1, len(chars) // 200)
    for _ in range(n_typos):
        idx = random.randint(0, len(chars) - 1)
        chars[idx] = random.choice("аеионст")
    return "".join(chars)


def remove_punctuation(text: str, prob: float = 0.03) -> str:
    if random.random() > prob:
        return text
    text = text.replace(",", " ").replace(".", " ").replace(":", " ")
    return re.sub(r"\s+", " ", text).strip()


def ru_en_mix(text: str, prob: float = 0.05) -> str:
    if random.random() > prob:
        return text
    replacements = {
        "бюджет": "budget", "скидка": "discount", "финанс": "finan",
        "план": "plan", "цена": "price", "договор": "contract",
        "отчёт": "report", "счёт": "invoice",
    }
    for ru, en in replacements.items():
        if random.random() < 0.3 and ru in text:
            text = text.replace(ru, en, 1)
    return text


def transliterate(text: str, prob: float = 0.03) -> str:
    if random.random() > prob:
        return text
    mapping = {
        "бюджет": "byudzhet", "скидка": "skidka", "договор": "dogovor",
        "цена": "tsena", "план": "plan", "финансы": "finansy",
    }
    for ru, tr in mapping.items():
        if random.random() < 0.3 and ru in text:
            text = text.replace(ru, tr, 1)
    return text


def obfuscate_keywords(text: str, prob: float = 0.04) -> str:
    if random.random() > prob:
        return text
    replacements = {
        "бюджет": "б·юд·жет", "скидка": "с·ки·д·ка", "договор": "до·го·вор",
        "финанс": "фи·нанс", "план": "п·лан", "конфиденциальн": "кон·фиден·циальн",
    }
    for ru, obf in replacements.items():
        if random.random() < 0.3 and ru in text:
            text = text.replace(ru, obf, 1)
    return text


def apply_noise(text: str, difficulty: str) -> str:
    probs = {
        "easy": {"typos": 0.02, "punct": 0.02, "mix": 0.02, "translit": 0.01, "obfusc": 0.01},
        "medium": {"typos": 0.05, "punct": 0.05, "mix": 0.05, "translit": 0.03, "obfusc": 0.03},
        "hard": {"typos": 0.10, "punct": 0.08, "mix": 0.08, "translit": 0.05, "obfusc": 0.05},
    }
    p = probs[difficulty]
    text = add_typos(text, p["typos"])
    text = remove_punctuation(text, p["punct"])
    text = ru_en_mix(text, p["mix"])
    text = transliterate(text, p["translit"])
    text = obfuscate_keywords(text, p["obfusc"])
    return text


def gen_subject(scenario, labels: List[str]) -> str:
    ind = scenario.industry
    if FIN_PLANS in labels and PRICING in labels:
        templates = [
            f"Вопрос по бюджету и ценам — {rand_company()}",
            f"Согласование финансовых условий проекта",
            f"Внутренняя смета и коммерческие параметры",
            f"Обсуждение бюджета и тарифов",
        ]
    elif FIN_PLANS in labels:
        templates = [
            f"Вопрос бюджета — {rand_department()}",
            f"Планирование расходов на квартал",
            f"Внутренний прогноз финансовых показателей",
            f"Бюджет подразделения — согласование",
            f"Финансовый план проекта",
            f"Вопрос по БДР и БДДС",
        ]
    elif PRICING in labels:
        templates = [
            f"Коммерческие условия поставки",
            f"Специальные цены для партнёра",
            f"Индивидуальные тарифы — согласование",
            f"Закрытый прайс-лист",
            f"Скидки по контракту",
            f"Ценовое предложение — внутреннее",
        ]
    else:
        templates = [
            f"Вопрос по работе — {rand_city()}",
            f"Организация встречи",
            f"Запрос информации",
            f"Уведомление о событии",
            f"Повторное обращение",
            f"Рабочий вопрос",
        ]
    return random.choice(templates)


def gen_body_for_scenario(scenario, idx_within: int, target_length_override: str = None) -> Tuple[str, str, List[str]]:
    labels = scenario.labels
    ind = scenario.industry
    diff = scenario.difficulty
    features = list(scenario.features)
    target_length = target_length_override or getattr(scenario, "target_length", "medium")

    subject = gen_subject(scenario, labels)
    sender = rand_name()
    recipient = rand_name()
    company = rand_company()
    dept = rand_department()
    position = rand_position()
    city = rand_city()
    date = rand_date()
    amount = rand_amount()

    if FIN_PLANS in labels and PRICING in labels:
        body = _gen_both(subject, sender, recipient, company, dept, position,
                         city, date, amount, ind, scenario, features)
    elif FIN_PLANS in labels:
        body = _gen_financial(subject, sender, recipient, company, dept, position,
                              city, date, amount, ind, scenario, features)
    elif PRICING in labels:
        body = _gen_pricing(subject, sender, recipient, company, dept, position,
                            city, date, amount, ind, scenario, features)
    else:
        body = _gen_safe(subject, sender, recipient, company, dept, position,
                         city, date, amount, ind, scenario, features)

    body = extend_body(body, target_length, scenario, ind, amount, city, company)
    body = apply_noise(body, diff)
    subject = apply_noise(subject, diff)
    return subject, body, features


def _gen_financial(subject, sender, recipient, company, dept, position,
                   city, date, amount, ind, scenario, features) -> str:
    parts = []
    parts.append(f"{recipient}, добрый день.")
    parts.append(f"Пересылаю материал по {dept} нашей компании {company}.")
    scen = scenario.scenario
    if "budget_revision" in scen:
        parts.append(
            f"Нужно пересмотреть внутренний бюджет на следующий квартал. "
            f"Предлагаю скорректировать статьи расходов, особенно по производству в {city}. "
            f"Обсудим на встрече в пятницу."
        )
    elif "capex" in scen:
        parts.append(
            f"Планируем закупку оборудования на сумму около {amount}. "
            f"Нужно утвердить капитальные вложения до конца месяца. "
            f"Прошу ознакомиться с расчётами."
        )
    elif "revenue_forecast" in scen:
        parts.append(
            f"Прогноз выручки на Q3 выглядит оптимистично. "
            f"Ожидаемый рост по сравнению с прошлым годом — примерно {amount}. "
            f"Данные пока не для широкой рассылки."
        )
    elif "liquidity" in scen:
        parts.append(
            f"Обсуждаем внутренний прогноз ликвидности. БДДС и БДР нуждаются в уточнении. "
            f"Предлагаю встречу с финансовым контролером на этой неделе."
        )
    elif "reserve" in scen:
        parts.append(
            f"Бюджет резерва под страховые выплаты требует пересмотра. "
            f"Показатели неопубликованные, обращайтесь внимательно."
        )
    elif "fuel" in scen:
        parts.append(
            f"План сокращения расходов на топливо готов к обсуждению. "
            f"Предлагаю меры по оптимизации маршрутов."
        )
    elif "payroll" in scen:
        parts.append(
            f"Вопрос изменения фонда оплаты труда в розничной сети. "
            f"Не обсуждайте это вне отдела кадров."
        )
    elif "financing" in scen:
        parts.append(
            f"План финансирования оптовой сделки прилагается к письму. "
            f"Переслано для ознакомления руководством."
        )
    elif "clinic" in scen:
        parts.append(
            f"Протокол совещания по бюджету клиники на 2025 год. "
            f"Основные цифры внутри документа."
        )
    elif "drug" in scen:
        parts.append(
            f"Бюджет закупки лекарственных препаратов распределен по кварталам. "
            f"Внутреннее распределение, не для публикации."
        )
    elif "it_infrastructure" in scen:
        parts.append(
            f"CAPEX на обновление ИТ-инфраструктуры утвержден предварительно. "
            f"План на следующий год в вложении."
        )
    elif "network" in scen:
        parts.append(
            f"Прогноз расширения сети связи требует капитальных вложений. "
            f"Обсудим на совещании в отделе развития."
        )
    elif "seasonal" in scen:
        parts.append(
            f"План сезонного финансирования агропредприятия подготовлен. "
            f"Требуется одобрение перед началом посевной кампании."
        )
    elif "fleet" in scen:
        parts.append(
            f"Бюджет обновления автопарка транспортной компании отправлен на согласование. "
            f"Требуется подпись директора."
        )
    elif "drilling" in scen:
        parts.append(
            f"Бюджет буровой программы в выдержке из внутреннего документа. "
            f"Не распространять за пределами отдела."
        )
    elif "margin" in scen:
        parts.append(
            f"Прогноз маржинальности консультационного проекта для клиента подготовлен. "
            f"Внутренняя оценка до подписания контракта."
        )
    elif "government" in scen:
        parts.append(
            f"Бюджет госконтракта требует уточнения показателей. "
            f"Неопубликованные данные требуют осторожности."
        )
    elif "marketing" in scen:
        parts.append(
            f"Перераспределение маркетингового бюджета интернет-магазина. "
            f"Предлагаем перенести средства с одной статьи на другую."
        )
    elif "ebitda" in scen:
        parts.append(
            f"Внутренний прогноз EBITDA производственного предприятия подготовлен до публикации. "
            f"Данные конфиденциальны."
        )
    elif "credit_line" in scen:
        parts.append(
            f"Планирование кредитной линии и заимствований банка на ближайшие месяцы. "
            f"Внутреннее обсуждение."
        )
    else:
        parts.append(
            f"Финансовый план для отрасли {ind}. "
            f"Обсуждение внутренних показателей и планируемых расходов. "
            f"Сумма ориентировочная — {amount}."
        )
    parts.append(f"Отправлено: {date}")
    parts.append(f"От: {sender}, {position}, {company}")
    parts.append(f"Город: {city}")
    return "\n".join(parts)


def _gen_pricing(subject, sender, recipient, company, dept, position,
                 city, date, amount, ind, scenario, features) -> str:
    parts = []
    parts.append(f"{recipient}, здравствуйте.")
    parts.append(f"Пишу от имени {company} по вопросу коммерческих условий.")
    scen = scenario.scenario
    if "discount" in scen:
        parts.append(
            f"Готовы предложить индивидуальную скидку для вашей компании. "
            f"Условия обсуждаются отдельно, не для широкой рассылки."
        )
    elif "price_list" in scen:
        parts.append(
            f"Закрытый прайс-лист на строительные материалы прилагается. "
            f"Цены не для публикации, только для постоянных партнёров."
        )
    elif "tariff" in scen:
        parts.append(
            f"Специальный тариф для крупного потребителя энергии согласован. "
            f"Индивидуальные условия прописаны в приложении."
        )
    elif "loan_rate" in scen:
        parts.append(
            f"Индивидуальная процентная ставка по кредиту утверждена. "
            f"Закрытые условия контракта — только для вас."
        )
    elif "premium" in scen:
        parts.append(
            f"Персональный коэффициент страховой премии рассчитан для корпоративного клиента. "
            f"Не разглашать условиях третьим лицам."
        )
    elif "delivery_discount" in scen:
        parts.append(
            f"Корпоративная скидка на доставку для регулярного клиента оформлена. "
            f"Действует с следующего месяца."
        )
    elif "purchase_price" in scen:
        parts.append(
            f"Закупочные цены от поставщика получены. "
            f"Не для публикации, только для отдела закупок."
        )
    elif "tender" in scen:
        parts.append(
            f"Условия тендера содержат непубличные коммерческие параметры. "
            f"Переслано для ознакомления руководством."
        )
    elif "dealer" in scen:
        parts.append(
            f"Дилерские цены на медицинское оборудование отправлены на согласование. "
            f"Внутренний документ."
        )
    elif "retrobonus" in scen:
        parts.append(
            f"Ретробонусы для аптечной сети согласованы. "
            f"Скрытые коммерческие условия не подлежат разглашению."
        )
    elif "saas" in scen:
        parts.append(
            f"Индивидуальный тариф SaaS-подписки для корпоративного клиента подготовлен. "
            f"Обсудим детали на встрече."
        )
    elif "interconnect" in scen:
        parts.append(
            f"Согласование ставок интерконнекта между операторами связи завершено. "
            f"Подписывайте приложение."
        )
    elif "fertilizer" in scen:
        parts.append(
            f"Скидка по объёму закупки удобрений предложена. "
            f"Обсуждение в закрытом режиме."
        )
    elif "freight" in scen:
        parts.append(
            f"Ставка по грузовому договору с индивидуальными условиями поставки утверждена. "
            f"Не для широкой рассылки."
        )
    elif "oil_price" in scen:
        parts.append(
            f"Цена контракта на поставку нефтепродуктов в выдержке из документа. "
            f"Закрытые коммерческие параметры."
        )
    elif "hourly" in scen:
        parts.append(
            f"Часовая ставка консультационных услуг не для разглашения. "
            f"Обсудим в個人 порядке."
        )
    elif "gov_tender" in scen:
        parts.append(
            f"Ценовое предложение по гос тендеру содержит закрытые параметры. "
            f"Требуется осторожность."
        )
    elif "commission" in scen:
        parts.append(
            f"Соглашение о комиссии маркетплейса с продавцом подготовлено. "
            f"Условия внутри документа."
        )
    elif "min_price" in scen:
        parts.append(
            f"Минимально допустимая цена продажи партнёру неопубликована. "
            f"Согласуйте перед отправкой контрагенту."
        )
    elif "deposit" in scen:
        parts.append(
            f"Повышенная ставка по вкладу для VIP-клиента утверждена. "
            f"Индивидуальные условия."
        )
    else:
        parts.append(
            f"Коммерческие условия для отрасли {ind}. "
            f"Специальные цены и тарифы, не для разглашения. "
            f"Ориентировочная сумма — {amount}."
        )
    parts.append(f"Отправлено: {date}")
    parts.append(f"От: {sender}, {position}, {company}")
    parts.append(f"Город: {city}")
    return "\n".join(parts)

def _gen_both(subject, sender, recipient, company, dept, position,
              city, date, amount, ind, scenario, features) -> str:
    parts = []
    parts.append(f"{recipient}, добрый день.")
    parts.append(f"Пишу от имени {company} по нескольким вопросам сразу.")
    parts.append(
        f"Во-первых, нужно согласовать внутренний бюджет отдела на следующий квартал. "
        f"Планируемые расходы на производство в {city} оценены в {amount}."
    )
    parts.append(
        f"Во-вторых, готовы предложить специальные коммерческие условия для вашей компании. "
        f"Индивидуальные скидки и закрытые тарифы обсуждаются отдельно."
    )
    parts.append(
        f"Оба вопроса конфиденциальны. Прошу не распространять эту переписку за пределами "
        f"отдела финансов и коммерческого отдела."
    )
    parts.append(f"Отправлено: {date}")
    parts.append(f"От: {sender}, {position}, {company}")
    return "\n".join(parts)


def _gen_safe(subject, sender, recipient, company, dept, position,
              city, date, amount, ind, scenario, features) -> str:
    parts = []
    parts.append(f"{recipient}, добрый день.")
    scen = scenario.scenario
    if "vacation" in scen:
        parts.append(f"Прошу оформить отпуск с {date} на две недели. Согласуйте, пожалуйста.")
    elif "support" in scen:
        parts.append(f"Ноутбук не включается, нужна помощь технической поддержки. Срочно.")
    elif "meeting" in scen:
        parts.append(f"Предлагаю провести еженедельное совещание отдела в четверг в 11:00.")
    elif "cargo" in scen:
        parts.append(f"Подскажите, где сейчас находится груз по номеру накладной?")
    elif "sick" in scen:
        parts.append(f"Нужно оформить больничный лист. Прикладываю справку от врача.")
    elif "maintenance" in scen:
        parts.append(f"График обслуживания строительной техники утвержден на месяц вперед.")
    elif "training" in scen:
        parts.append(f"Обучение сотрудников банка по новым правилам безопасности назначено на следующую неделю.")
    elif "stationery" in scen:
        parts.append(f"Нужно заказать канцелярские принадлежности для офиса. Составьте заявку.")
    elif "trip" in scen:
        parts.append(f"Подаю заявку на командировку на энергообъект в следующем месяце.")
    elif "incident" in scen:
        parts.append(f"Отчёт об инциденте на сетевом оборудовании направлен в службу поддержки.")
    elif "workflow" in scen:
        parts.append(f"Документ отправлен на согласование через внутренний workflow. Жду вашу подпись.")
    elif "driver" in scen:
        parts.append(f"График работы водителя изменен с начала следующей недели.")
    elif "inspection" in scen:
        parts.append(f"Проверка буровой установки назначена на среду. Готовьте документацию.")
    elif "reschedule" in scen:
        parts.append(f"Нужно перенести встречу с клиентом на другую дату. Предлагайте варианты.")
    elif "permit" in scen:
        parts.append(f"Запрос выписки из разрешительной документации направлен госзаказчику.")
    elif "congrats" in scen:
        parts.append(f"Поздравляем вас с днём рождения! Желаем успехов и процветания.")
    elif "report" in scen:
        parts.append(f"Отчёт о выполненной задаче по оптовой поставке товара направлен в отдел.")
    elif "quality" in scen:
        parts.append(f"Протокол совещания отдела контроля качества завода отправлен всем участникам.")
    elif "customs" in scen:
        parts.append(f"Уведомление о таможенном оформлении груза получено. Ожидаем растаможки.")
    elif "outage" in scen:
        parts.append(f"Плановое отключение электричества запланировано на выходные.")
    else:
        parts.append(f"Обычное деловое письмо по отрасли {ind}. Рабочий вопрос к обсуждению.")
    parts.append(f"Отправлено: {date}")
    parts.append(f"От: {sender}, {position}, {company}")
    return "\n".join(parts)


def _gen_hard_leak(subject, sender, recipient, company, dept, position,
                   city, date, amount, ind, scenario, features) -> str:
    parts = []
    parts.append(f"{recipient}, добрый день.")
    parts.append(
        f"К сожалению, мы не можем раскрыть конфиденциальную информацию по вашему запросу. "
        f"Однако прилагаю выдержку из внутреннего бюджета для справки: "
        f"планируемые расходы на следующий квартал — {amount}. "
        f"Бюджет подразделения в {city} требует согласования."
    )
    parts.append(f"Надеюсь на понимание.")
    parts.append(f"Отправлено: {date}")
    parts.append(f"От: {sender}, {position}, {company}")
    return "\n".join(parts)


def extend_body(body: str, target_length: str, scenario, ind: str, amount: str,
                city: str, company: str) -> str:
    """Добавляет дополнительные абзацы для достижения целевой длины."""
    if target_length == "short":
        return body
    if target_length == "medium":
        if random.random() < 0.5:
            body += "\n\n" + _extra_paragraph(ind, amount, city, company)
        return body
    if target_length == "long":
        for _ in range(random.randint(5, 8)):
            body += "\n\n" + _extra_paragraph(ind, amount, city, company)
        return body
    # very_long
    for _ in range(random.randint(10, 16)):
        body += "\n\n" + _extra_paragraph(ind, amount, city, company)
    return body


def _extra_paragraph(ind: str, amount: str, city: str, company: str) -> str:
    topics = [
        f"Также хотим уточнить, что все расчеты для отрасли {ind} подготовлены с учетом текущих рыночных условий. "
        f"Ожидаемый объем financing — {amount}. Данные требуют тщательной проверки перед утверждением руководством компании.",
        f"Просим обратить внимание на сроки реализации мероприятий в {city}. "
        f"Ответственный исполнитель будет назначен отдельным распоряжением директора по развитию.",
        f"К письму прилагаются дополнительные материалы из архива {company}. "
        f"Все документы заверены печатью и подписаны руководителем подразделения, имеющим на то право.",
        f"В случае возникновения вопросов просим обращаться по каналам внутренней связи. "
        f"Обратная связь будет обеспечена в кратчайшие сроки, не позднее трех рабочих дней.",
        f"Утверждение данного плана потребует согласования с директором по развитию и финансовым контролером. "
        f"Протокол совещания будет направлен отдельным сообщением в течение недели после подписания.",
        f"Все цифры носят предварительный характер и могут быть скорректированы после финального утверждения. "
        f"Окончательная версия будет распространена после подписания всеми заинтересованными сторонами.",
        f"Бюджетные ограничения для отрасли {ind} требуют внимательного отношения к каждой статье расходов. "
        f"Любое превышение лимитов должно быть согласовано дополнительно с финансовым департаментом.",
        f"Предлагаемый график реализации мероприятий согласован с производственным календарем компании на текущий год.",
    ]
    return random.choice(topics)
