"""Generate the preregistered, manually authored hypothesis grid from category semantics."""
from common import HERE, ROOT, load, save

# English short name, Russian detailed meaning, English concrete action,
# Russian concrete action, Russian exclusion, English exclusion.
DEFINITIONS = {
    'financial-plans': (
        'Non-public financial plans',
        'Письмо содержит внутренний бюджет, непубличный прогноз выручки или план будущих расходов организации.',
        'The sender shares an internal financial forecast, budget or future spending plan not intended for the public.',
        'Отправитель сообщает или пересылает внутренние плановые финансовые показатели, не опубликованные для общего доступа.',
        'Письмо обсуждает только публичную финансовую отчётность, открытый бюджет или обычный счёт, без внутренних финансовых планов.',
        'This is only public financial information or an ordinary invoice, without non-public financial plans.'),
    'pricing': (
        'Individual commercial terms',
        'Письмо содержит индивидуальную скидку, специальную цену, закрытую себестоимость или непубличные коммерческие условия.',
        'The sender discloses a customer-specific discount, individually negotiated price, private cost or markup.',
        'В письме передают согласованные для конкретного контрагента цены и скидки либо внутреннюю себестоимость и наценку.',
        'Письмо содержит только общедоступный прайс, обычную цену или счёт без индивидуальных коммерческих условий.',
        'This is only a public price list or standard commercial offer, with no special individual terms.'),
    'internal-docs': (
        'Restricted internal documents',
        'Письмо или вложенный документ содержит явную пометку внутреннего использования или ограничения распространения.',
        'The message marks documents as internal only, confidential, restricted distribution or not for external recipients.',
        'Отправитель передаёт документ с явным ограничением доступа или запрещает его дальнейшее распространение.',
        'Письмо лишь обсуждает правила конфиденциальности или содержит общедоступные документы без действующей пометки ограничения доступа.',
        'This only discusses confidentiality policy or public documents, not an actual restricted document.'),
    'customer-data': (
        'Customer database transfer',
        'Письмо сообщает о выгрузке или передаче массива клиентских записей, базы клиентов либо списка контактов.',
        'The sender exports, sends or requests a customer database, contact list or collection of customer records.',
        'Отправитель пересылает или просит выгрузить клиентскую базу, таблицу клиентов или список контактных записей.',
        'Письмо только обсуждает защиту базы или отдельного клиента, без передачи и запроса массива клиентских записей.',
        'This is only a discussion of database protection or one customer, with no customer-record export or transfer.'),
    'pii-handling': (
        'Personal data forwarding',
        'Письмо содержит организационный контекст передачи персональных данных, паспортных копий или анкет людей.',
        'The sender sends, forwards or requests personal records, passport scans or individuals personal data.',
        'Отправитель направляет или просит переслать персональные данные людей, паспортные сканы или заполненные анкеты.',
        'Письмо лишь обсуждает законодательство и защиту персональных данных, без конкретной пересылки или запроса таких данных.',
        'This only discusses personal-data protection policy, without sending or requesting actual personal records.'),
    'data-exfil': (
        'Unauthorized external data transfer',
        'Письмо содержит действие по выводу внутренних материалов организации внешнему неуполномоченному получателю.',
        'The sender sends or requests internal company files to be copied to an unauthorized external address or personal mailbox.',
        'Внутренние файлы или коммерческие документы организации пересылают либо предлагают выгрузить на личную почту или постороннему.',
        'Письмо лишь обсуждает предотвращение утечек либо разрешённый внутренний обмен, без вывода информации посторонним.',
        'This only discusses preventing data leaks or authorized internal sharing, not actual external exfiltration.'),
    'credential-transfer': (
        'Passwords and access keys transfer',
        'Письмо содержит просьбу передать рабочий пароль, API-токен, ключ доступа или саму передачу этих секретов.',
        'The sender requests or transmits a working password, API token, private key or other access secret.',
        'Отправитель просит прислать пароль или токен либо передаёт рабочие учётные данные и приватные ключи.',
        'Письмо лишь напоминает не передавать пароли или обсуждает безопасность, без запроса и передачи действующего секрета.',
        'This is only security advice, a dummy credential example or a prohibition on sharing passwords, with no real secret transfer request.'),
    'phishing': (
        'Phishing demand',
        'Письмо требует от получателя сообщить пароль, одноразовый код или войти по ссылке под предлогом проверки или разблокировки.',
        'The recipient is urged to reveal a password or one-time code or follow a login link to verify or unblock an account.',
        'От получателя требуют подтвердить аккаунт, ввести пароль по ссылке или прислать код подтверждения.',
        'Письмо только обсуждает распознавание фишинга, цитирует учебный пример или предупреждает не вводить пароль.',
        'This is only an anti-phishing discussion, warning or training example, not a live demand for credentials or login.'),
    'extortion': (
        'Blackmail and extortion',
        'Письмо требует деньги или другие действия под угрозой раскрытия информации или причинения ущерба.',
        'The sender demands payment or compliance and threatens to leak information or cause damage if the recipient refuses.',
        'Отправитель требует выкуп или выполнение условий, иначе угрожает публикацией данных или ущербом.',
        'Письмо лишь цитирует шантаж в новости, учебном материале или обсуждении, без действующего требования под угрозой.',
        'This only discusses or quotes extortion in news or training, without a current coercive demand.'),
    'explosive-threat': (
        'Threat of explosion',
        'Письмо выражает прямую угрозу взрыва либо утверждает, что взрывное устройство заложено в здании.',
        'The sender threatens to blow up a building or asserts that an explosive device has been planted.',
        'Отправитель угрожает взорвать офис или сообщает о заложенной им бомбе как о действующей угрозе.',
        'Письмо лишь цитирует угрозу из новости, книги или учений либо описывает безопасное обучение, без действующей угрозы взрыва.',
        'This is only news, fiction, a witness discussion or a training exercise about explosions, not a live bomb threat.'),
    'violence-threat': (
        'Direct threat of physical violence',
        'Письмо содержит прямую угрозу причинить физический вред адресату или другим людям.',
        'The sender directly threatens to kill, beat, shoot or physically harm the recipient or other people.',
        'Отправитель выражает намерение убить, избить, застрелить человека или расправиться с людьми.',
        'Письмо лишь цитирует насилие в новости, художественном тексте или учебном примере, без прямой действующей угрозы.',
        'This only quotes violence in fiction, news or training, without a current direct threat to harm people.'),
    'sabotage': (
        'IT infrastructure sabotage threat',
        'Письмо выражает намерение умышленно повредить серверы, отключить инфраструктуру или уничтожить резервные копии.',
        'The sender threatens deliberate destruction of servers, intentional service disruption or deletion of backups.',
        'Отправитель угрожает вывести сервер из строя, уничтожить данные или умышленно удалить резервные копии.',
        'Письмо обсуждает штатное обслуживание, восстановление, тестирование или защиту ИТ, без намерения причинить умышленный ущерб.',
        'This is only authorized maintenance, backup testing or a quoted incident, not a deliberate sabotage threat.'),
}


def main():
    source = load(ROOT / 'config/rulepacks/ru2_morph_weighted_rules.json')
    categories = {}
    for category in source['categories']:
        cid = category['id']
        en, detail, action_en, action_ru, exclude_ru, exclude_en = DEFINITIONS[cid.removeprefix('pack-ru2-')]
        texts = [category['name'].replace('[RU2] ', ''), en, detail, action_en, action_ru,
                 'This email concerns ' + en.lower() + '.', exclude_ru, exclude_en]
        categories[cid] = dict(name=category['name'], mice_description=category['description'],
                              rule_titles=[r['title'] for r in category['rules']],
                              hypotheses=[dict(id=f'h{i}', text=t, polarity='exclude' if i >= 6 else 'positive',
                                               language='ru' if i in (0, 2, 4, 6) else 'en') for i, t in enumerate(texts)])
    save(HERE / 'hypotheses.json', dict(categories=categories,
        source='config/rulepacks/ru2_morph_weighted_rules.json',
        warning='Context labels, not legal conclusions. Exclusions are tested, not assumed superior.'))


if __name__ == '__main__':
    main()