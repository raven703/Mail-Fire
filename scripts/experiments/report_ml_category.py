"""Render the frozen three-engine B500 comparison from saved JSON artifacts."""
import argparse
import json
from pathlib import Path


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def pct(x):
    return '—' if x is None else f'{x*100:.2f}%'


def counts(x):
    return f"{x['TP']}/{x['FP']}/{x['FN']}/{x['TN']}"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,required=True)
    args=parser.parse_args()
    root=args.results
    base={k:read(root/'baselines'/f'{k}-b500.json') for k in ('ru3','ru4')}
    cohort=read(root/'baselines/cohorts-b500.json')
    ml={e:read(root/f'{e}-b500/metrics.json') for e in ('tfidf','setfit','rubert') if (root/f'{e}-b500/metrics.json').is_file()}
    categories=sorted(base['ru3']['per_category'])
    lines=['# Сравнение штатных ML-моделей на B-500','',
     'Версии данных и кода, групповой split, пороги и хеши артефактов зафиксированы в машиночитаемых файлах этого каталога. B-350 и B-400 использованы для обучения и внутренней валидации. B-500 использован только после фиксации моделей и порогов. Сценарии `корпус:scenario` и точные совпадения текстов объединены в группы без пересечения между train/validation/test. Разметка не менялась.','',
     '## Итоговые метрики','',
     '| Движок | TP/FP/FN/TN | Precision micro | Recall micro | F1 micro | Precision macro | Recall macro | F1 macro |','| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for e in ('ru3','ru4','tfidf','setfit','rubert'):
        if e in base:
            m=base[e]['micro'];macro={key:sum((v[key] or 0) for v in base[e]['per_category'].values())/12 for key in ('precision','recall','F1')}
        elif e in ml:
            m=ml[e]['ALL']['micro'];macro=ml[e]['ALL']['macro']
        else:
            lines.append(f'| {e.upper()} | не завершено | — | — | — | — | — | — |');continue
        lines.append(f"| {e.upper()} | {counts(m)} | {pct(m['precision'])} | {pct(m['recall'])} | {pct(m['F1'])} | {pct(macro['precision'])} | {pct(macro['recall'])} | {pct(macro['F1'])} |")
    lines+=['','## 12 категорий','',
      '| Категория | Движок | TP/FP/FN/TN | Precision | Recall | F1 |','| --- | --- | --- | ---: | ---: | ---: |']
    for c in categories:
        for e in ('ru3','ru4','tfidf','setfit','rubert'):
            if e in base:v=base[e]['per_category'][c]
            elif e in ml:v=ml[e]['ALL']['per_category'][c]
            else:continue
            lines.append(f"| {c.removeprefix('pack-ru2-')} | {e.upper()} | {counts(v)} | {pct(v['precision'])} | {pct(v['recall'])} | {pct(v['F1'])} |")
    lines+=['','## Типы писем и безопасные письма','',
      '| Группа | Движок | TP/FP/FN/TN | Precision | Recall | F1 | Писем с FP |','| --- | --- | --- | ---: | ---: | ---: | ---: |']
    for g in ('ordinary_positive','obfuscated','mixed','safe_ordinary','safe_hard'):
        for e in ('ru3','ru4','tfidf','setfit','rubert'):
            if e in cohort:v=cohort[e][g]; fp=v['messages_with_error'] if e in ('ru3','ru4') and g.startswith('safe') else v['micro']['FP']
            elif e in ml:v=ml[e][g];fp=v['messages_with_FP']
            else:continue
            m=v['micro'];lines.append(f"| {g} | {e.upper()} | {counts(m)} | {pct(m['precision'])} | {pct(m['recall'])} | {pct(m['F1'])} | {fp} |")
    lines+=['', 'На 260 безопасных письмах число FP: '+', '.join(f"{e.upper()}={sum((cohort[e][g]['micro']['FP'] if e in cohort else ml[e][g]['micro']['FP']) for g in ('safe_ordinary','safe_hard'))}" for e in ('ru3','ru4','tfidf','setfit','rubert') if e in cohort or e in ml)+'.','',
      '## Время, память и модель','',
      '| Движок | Обучение всех категорий | Инференс B-500 | Пиковая RAM | VRAM | Размер артефактов |','| --- | ---: | ---: | ---: | --- | ---: |']
    if 'tfidf' in ml:
        t=read(root/'tfidf-training/training.json');v=ml['tfidf'];lines.append(f"| TF-IDF | {t['seconds']:.2f} с | {v['inference_seconds']:.2f} с | {max(t['maxrss_kib'],v['maxrss_kib'])/1024:.1f} МиБ | нет GPU | {t['artifact_bytes']/1048576:.2f} МиБ |")
    for e in ('setfit','rubert'):
        if e not in ml:continue
        training=[read(p) for p in sorted((root/'neural-models'/e).glob('*/training.json'))]
        v=ml[e]
        lines.append(f"| {e.upper()} | {sum(t['seconds'] for t in training):.2f} с | {v['inference_seconds']:.2f} с | {max([v['maxrss_kib']]+[t['maxrss_kib'] for t in training])/1024:.1f} МиБ | нет GPU | {sum(t['artifact_bytes'] for t in training)/1048576:.1f} МиБ |")
    lines+=['','## Интерпретация и ограничения','',
      'Модели обучались штатными `app.ml.train` и `app.ml_engines.train_binary`; изменён только способ передачи группового split. TF-IDF остаётся глобальной многометочной моделью; SetFit и RuBERT — 12 независимых бинарных моделей, их вывод объединён по категориям. Порог каждой категории выбран штатной функцией только на validation. На B-500 дополнительных тренировок и корректировок порога не проводилось.','',
      'Разделение по `scenario` устраняет очевидные повторяющиеся шаблоны внутри набора и пересечения точных текстов, но не гарантирует отсутствия смыслового сходства между разными именами сценариев и между B-350/B-400. Это синтетические наборы, B-500 не является полностью слепой независимой разметкой. Эффективное число положительных сценарных групп в validation для некоторых категорий мало, поэтому пороги нестабильны.','',
      'Нейронные zip-артефакты (~104 МиБ каждый) сохранены локально вне git в `/home/user/Mice-ml-models`; в PR включены их SHA-256, пороги, параметры, время, RAM и полные предсказания. TF-IDF артефакт включён в виде gzip+base64; восстановление: `base64 -d tfidf.pkl.gz.b64 | gunzip > tfidf.pkl`. Для `messages.json.gz.b64` используется такая же команда с именем `messages.json`. Модели не публиковались на рабочем стенде, БД не изменялась.','']
    (root/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print('report rows',len(lines))

if __name__=='__main__':main()
