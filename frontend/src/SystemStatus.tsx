import {useEffect,useState} from 'react';
import {Table,date,type API,type Row} from './components';
import './system-status.css';

const tabs={queues:'Очереди',flow:'Почтовый поток',resources:'История ресурсов',database:'PostgreSQL'};
type Tab=keyof typeof tabs;
const number=(v:any)=>v==null?'—':Number(v).toLocaleString('ru-RU',{maximumFractionDigits:1});
const bytes=(v:any)=>{if(v==null)return '—';let n=Number(v),i=0;const units=['Б','КБ','МБ','ГБ','ТБ'];while(n>=1024&&i<4){n/=1024;i++}return `${number(n)} ${units[i]}`};
const kindNames:Record<string,string>={analyze:'Анализ писем',evaluate:'Проверка политик',ml_train:'Обучение ML',import:'Импорт писем'};
const tableNames:Record<string,string>={messages:'Письма',contents:'Тексты и результаты анализа',blobs:'Файлы и оригиналы',attachments:'Вложения',incidents:'Инциденты',mail_events:'События доставки',semantic_chunks:'Семантический индекс',audit:'Журнал аудита',metrics:'История ресурсов',jobs:'Задания',ml_models:'ML-модели',training_examples:'Обучающие примеры',categories:'Категории',category_rules:'Правила обнаружения',policies:'DLP-политики',imports:'Импорт',references:'Эталонные документы'};

function Cards({items}:{items:[string,string,string?][]}){return <div className="system-kpis">{items.map(([label,value,hint])=><article key={label}><span>{label}</span><strong>{value}</strong>{hint&&<small>{hint}</small>}</article>)}</div>}

export function SystemStatus({api}:{api:API}){
 const [tab,setTab]=useState<Tab>('queues'),[data,setData]=useState<Row|null>(null),[mail,setMail]=useState<Row>({}),[busy,setBusy]=useState(false),[error,setError]=useState(''),[updated,setUpdated]=useState(''),[revision,setRevision]=useState(0);
 useEffect(()=>{let active=true;setData(null);setError('');setBusy(true);
  Promise.all([api('monitoring/'+tab),...(tab==='queues'?[api('monitoring/mail-queue')]:[])])
   .then(([result,queue])=>{if(active){setData(result);if(queue)setMail(queue);setUpdated(new Date().toLocaleTimeString('ru-RU'))}})
   .catch(e=>{if(active)setError(String(e))}).finally(()=>{if(active)setBusy(false)});
  return()=>{active=false};
 },[tab,revision]);
 const rows:Row[]=data?.items||[];
 const total=(status:string)=>rows.filter(r=>r.status===status).reduce((sum,r)=>sum+Number(r.count||0),0);
 const expired=rows.reduce((sum,r)=>sum+Number(r.expired_leases||0),0);
 const latest=rows[0]?.values||{};
 const memory=latest.ram_total?Number(latest.ram_used)/Number(latest.ram_total)*100:null;
 const connections:Row[]=data?.connections||[];
 const flowRows=Object.values(rows.reduce<Record<string,Row>>((groups,r)=>{const key=r.source+'|'+r.direction;const group=groups[key]||(groups[key]={source:r.source,direction:r.direction,events:0,totalBytes:0});group.events+=Number(r.events);group.totalBytes+=Number(r.average_bytes||0)*Number(r.events);return groups},{})).map(r=>({...r,average:bytes(r.events?r.totalBytes/r.events:0)}));
 return <section className="system-status">
  <header className="system-status-header"><div><h2>Диагностика обработки</h2><p className="muted">Состояние очередей, нагрузка и хранение данных — без лишних технических подробностей.</p></div><div className="system-refresh"><small className="muted">{updated?'Обновлено в '+updated:'Данные ещё не загружены'}</small><button disabled={busy} onClick={()=>setRevision(v=>v+1)}>Обновить</button></div></header>
  <nav className="system-tabs" aria-label="Разделы диагностики">{Object.entries(tabs).map(([key,label])=><button key={key} aria-pressed={tab===key} onClick={()=>setTab(key as Tab)}>{label}</button>)}</nav>
  {busy&&<p role="status" className="muted">Загружаем показатели…</p>}
  {error&&<p role="alert" className="error">Не удалось загрузить раздел. {error}</p>}
  {data&&tab==='queues'&&<>
   <div className={'system-summary '+(total('DEAD')||expired?'warning':'')}><strong>{total('DEAD')||expired?'Есть задания, требующие внимания':total('RUNNING')?'Обработка выполняется':total('PENDING')?'Есть задания в очереди':'Очередь свободна'}</strong><p>{total('DEAD')||expired?'Проверьте ошибки и зависшие задания на странице «Очереди обработки».':'Ошибки заданий и просроченные блокировки не обнаружены. Это не проверка доступности всех детекторов.'}</p></div>
   <Cards items={[["Ожидают анализа",number(mail.pending),'Уникальные письма'],['В обработке',number(mail.processing),'Уникальные письма'],['Ошибки писем',number(mail.errors)],['Неполный анализ',number(mail.partial),'Часть детекторов недоступна']]}/>
   <h3>Технические задания</h3><Table rows={Object.values(rows.reduce<Record<string,Row>>((groups,r)=>{const g=groups[r.kind]||(groups[r.kind]={name:kindNames[r.kind]||r.kind,pending:0,running:0,failed:0,expired:0});if(r.status==='PENDING')g.pending+=Number(r.count);if(r.status==='RUNNING')g.running+=Number(r.count);if(r.status==='DEAD')g.failed+=Number(r.count);g.expired+=Number(r.expired_leases||0);return groups},{}))} columns={[["name","Этап"],["pending","Ожидают"],["running","Выполняются"],["failed","Ошибки"],["expired","Зависшие"]]}/>
   <p className="muted">Завершённые задания скрыты из сводки. Одно письмо может создавать несколько технических заданий.</p>
   <a className="system-detail-link" href="?page=jobs">Открыть очереди обработки →</a>
  </>}
  {data&&tab==='flow'&&<>
   <Cards items={[["Доставок за 7 дней",number(rows.reduce((s,r)=>s+Number(r.events),0)),'Повторные доставки считаются отдельно'],['Источников',number(new Set(rows.map(r=>r.source)).size)],['Последняя доставка',rows.length?date(rows[0].hour):'Пока нет','Время округлено до часа']]}/>
   <h3>Откуда поступает почта</h3><Table rows={flowRows} columns={[["source","Источник"],["direction","Направление"],["events","Доставок"],["average","Средний размер письма"]]}/>
   <p className="muted">Отсутствие новых писем само по себе не означает сбой. Показаны события доставки за последние 7 дней, а не количество уникальных писем.</p>
   <details><summary>Почасовая статистика · последние 24 записи</summary><Table rows={rows.slice(0,24).map(r=>({...r,time:date(r.hour),size:bytes(r.average_bytes)}))} columns={[["time","Час"],["source","Источник"],["events","Доставок"],["size","Средний размер"]]}/></details>
  </>}
  {data&&tab==='resources'&&<>
   {!rows.length?<div className="empty">Показатели ресурсов ещё не поступили. Сбор выполняется примерно каждые 30 секунд.</div>:<>
    <Cards items={[["Загрузка CPU",latest.cpu_percent==null?'—':number(latest.cpu_percent)+' %'],['Использование памяти',memory==null?'—':number(memory)+' %',bytes(latest.ram_used)+' из '+bytes(latest.ram_total)],['Свободно на диске',bytes(latest.disk_free)],['Используется swap',bytes(latest.swap_used)]]}/>
    <p className="muted">Последний замер: {date(rows[0].created_at)}. Показатели видимого maintenance-процессу окружения, не отдельных контейнеров Mail-Fire.</p>
    <h3>Последние 20 замеров</h3><Table rows={rows.slice(0,20).map(r=>({id:r.id,time:date(r.created_at),cpu:r.values?.cpu_percent==null?'—':number(r.values.cpu_percent)+' %',ram:bytes(r.values?.ram_used),disk:bytes(r.values?.disk_free)}))} columns={[["time","Время"],["cpu","CPU"],["ram","Память занята"],["disk","Диск свободен"]]}/>
   </>}
  </>}
  {data&&tab==='database'&&<>
   <div className={'system-summary '+(Number(data.locks_waiting)>0?'warning':'')}><strong>{Number(data.locks_waiting)>0?'Есть ожидания блокировок':'PostgreSQL отвечает'}</strong><p>{Number(data.locks_waiting)>0?'Операции могут выполняться медленнее. Проверьте нагрузку и длительные запросы.':'Данные получены успешно. Ожидающих блокировок нет.'}</p></div>
   <Cards items={[["Размер базы",bytes(data.database_bytes)],['Подключения',number(connections.length)],['Активные запросы',number(connections.filter(r=>r.state==='active').length),'Включая текущий запрос диагностики'],['Ожидания блокировок',number(data.locks_waiting)]]}/>
   <h3>Что занимает место · 10 крупнейших таблиц</h3><Table rows={(data.tables||[]).slice(0,10).map((r:Row)=>({name:tableNames[r.relname]||r.relname,size:bytes(r.total_bytes),indexes:bytes(r.index_bytes),records:number(r.n_live_tup)}))} columns={[["name","Данные"],["size","Размер с индексами"],["indexes","Из них индексы"],["records","Примерно строк"]]}/>
   <details><summary>Обслуживание базы</summary><p className="muted">Оценки PostgreSQL, а не точные счётчики. Очистка и анализ могут выполняться автоматически или вручную.</p><Table rows={(data.tables||[]).map((r:Row)=>({name:tableNames[r.relname]||r.relname,dead:number(r.n_dead_tup),vacuum:date(r.last_autovacuum),analyze:date(r.last_autoanalyze)}))} columns={[["name","Таблица"],["dead","Устаревшие строки"],["vacuum","Автоочистка"],["analyze","Обновление статистики"]]}/></details>
  </>}
 </section>;
}