import type {ReactNode} from 'react';
import {Badge,date,type Row} from './components';

type Navigate = (page:string, extra?:Record<string,string>)=>void;
type OverviewProps = {data:Row,onNavigate:Navigate};

const safeCount = (value:unknown):string => value===null||value===undefined?'—':Number(value).toLocaleString('ru-RU');
const levelNames:Record<string,string> = {HIGH:'Высокая',MEDIUM:'Средняя',LOW:'Низкая'};

function SectionHeading({title,subtitle,action}:{title:string,subtitle?:string,action?:ReactNode}){
 return <header className="so-section-heading">
  <div><h2>{title}</h2>{subtitle&&<p>{subtitle}</p>}</div>{action}
 </header>;
}

export function SecurityOverview({data,onNavigate}:OverviewProps){
 const go=onNavigate;
 const levels=data.levels||{};
 const series:Row[]=(data.timeline||[]).slice().sort((a:Row,b:Row)=>String(a.time).localeCompare(String(b.time))).slice(-18);
 const maxBucket=Math.max(1,...series.map(b=>Number(b.HIGH||0)+Number(b.MEDIUM||0)+Number(b.LOW||0)));
 const policies:Row[]=(data.categories||[]).slice(0,6);
 const most=Math.max(1,...policies.map(p=>Number(p.count||0)));
 // The backend intentionally returns the top-eight incidents by RISK, then date;
 // calling this panel "latest" would incorrectly imply time ordering.
 const priority:Row[]=(data.recent||[]).slice(0,6);
 const healthEntries=Object.entries(data.health||{}) as [string,string][];
 const queue=data.queues||{};
 const dead=Number(queue.DEAD||0);
 const open=Number(data.review||0);

 const metrics=[
  {key:'review',title:'Требуют проверки',value:data.review,note:'Открытые инциденты за период',target:'incidents',extra:{status:'open'},tone:'attention'},
  {key:'incidents',title:'Всего инцидентов',value:data.incidents,note:'За выбранный период',target:'incidents',extra:{status:''},tone:''},
  {key:'analyzed',title:'Писем проанализировано',value:data.analyzed,note:'За выбранный период',target:'messages',extra:{status:'ANALYZED'},tone:''},
  {key:'active_jobs',title:'Заданий в работе',value:data.active_jobs,note:'Текущее состояние очереди',target:'jobs',extra:{status:'active'},tone:''},
 ];
 return <div className="security-overview" aria-label="Обзор безопасности">
  <div className="so-summary-bar">
   <div><h2>Сводка безопасности</h2><p>Инциденты и сообщения — за выбранный период. Очереди — текущее состояние.</p></div>
   <button className="so-subtle-link" onClick={()=>go('incidents',{status:'open'})}>К расследованиям <span aria-hidden="true">→</span></button>
  </div>

  <div className="so-metrics" aria-label="Ключевые показатели">
   {metrics.map(m=><button type="button" key={m.key} className={'so-metric '+(m.tone?'so-metric-attention':'')}
    onClick={()=>go(m.target,m.extra)} aria-label={m.title+': '+safeCount(m.value)+'. Открыть список'}>
    <span className="so-metric-label">{m.title}</span>
    <strong className="so-metric-value">{safeCount(m.value)}</strong>
    <span className="so-metric-note">{m.note}<span aria-hidden="true"> ↗</span></span>
   </button>)}
  </div>

  <div className="so-insights">
   <section className="so-panel so-risk">
    <SectionHeading title="Уровни риска" subtitle="Распределение инцидентов за период"
     action={<button className="so-subtle-link" onClick={()=>go('incidents',{status:''})}>Все инциденты →</button>}/>
    <div className="so-risk-list">
     {(['HIGH','MEDIUM','LOW'] as const).map(level=><button type="button" key={level}
      className={'so-risk-line so-level-'+level} onClick={()=>go('incidents',{severity:level,status:''})}
      aria-label={levelNames[level]+': '+safeCount(levels[level])+'. Показать инциденты'}>
      <span className="so-risk-label"><i aria-hidden="true"/>{levelNames[level]}</span>
      <span className="so-risk-track"><span style={{width:(Number(levels[level]||0)/Math.max(1,Number(data.incidents||0))*100)+'%'}}/></span>
      <strong>{safeCount(levels[level])}</strong>
     </button>)}
    </div>
    <p className="so-panel-footnote">Уровень определяется риском инцидента; один инцидент учитывается в одной группе.</p>
   </section>

   <section className="so-panel so-trend">
    <SectionHeading title="Динамика инцидентов" subtitle="Почасовая или дневная группировка по выбранному периоду"
     action={<button className="so-subtle-link" onClick={()=>go('analytics')}>Аналитика →</button>}/>
    {series.length?<div className="so-trend-body">
     <div className="so-spark" role="img" aria-label={'График: '+series.map(b=>date(b.time)+', '+(Number(b.HIGH||0)+Number(b.MEDIUM||0)+Number(b.LOW||0))+' инцидентов').join('; ')}>
      {series.map(b=>{
       const total=Number(b.HIGH||0)+Number(b.MEDIUM||0)+Number(b.LOW||0);
       return <div className="so-spark-column" key={b.time} title={date(b.time)+': '+total}>
        <div className="so-spark-bar" style={{height:Math.max(total?9:2,total/maxBucket*100)+'%'}}>
         {(['LOW','MEDIUM','HIGH'] as const).map(level=>
          <span key={level} className={'so-spark-segment so-level-'+level}
           style={{flexGrow:Number(b[level]||0)}}/>)}
        </div>
       </div>;
      })}
     </div>
     <div className="so-trend-axis"><span>{date(series[0].time)}</span><span>{date(series[series.length-1].time)}</span></div>
    </div>:<p className="so-compact-empty">За выбранный период инцидентов нет</p>}
   </section>
  </div>

  <div className="so-detail-grid">
   <section className="so-panel so-priority">
    <SectionHeading title="Приоритетные инциденты" subtitle="Сначала самые высокие риски, затем новые"
     action={<button className="so-subtle-link" onClick={()=>go('incidents',{status:''})}>К списку →</button>}/>
    {priority.length?<div className="so-priority-list">
     {priority.map(r=><button type="button" className="so-incident-line" key={r.id}
      onClick={()=>go('incidents',{id:r.id})} aria-label={'Открыть инцидент: '+(r.subject||r.category||'Без темы')}>
      <span className="so-incident-main">
       <span className="so-incident-title">{r.subject||'Без темы'}</span>
       <span className="so-incident-meta">{r.category||'Политика не указана'} · {date(r.created_at)}</span>
      </span>
      <span className="so-incident-side"><Badge value={r.severity}/><span className="so-risk-number">{r.risk??'—'}/100</span></span>
      <span className="so-incident-state"><Badge value={r.status}/></span>
     </button>)}
    </div>:<p className="so-compact-empty">За выбранный период инцидентов нет</p>}
   </section>

   <section className="so-panel so-policies">
    <SectionHeading title="Политики со срабатываниями" subtitle="Число инцидентов по DLP-политикам"
     action={<button className="so-subtle-link" onClick={()=>go('policies')}>Политики →</button>}/>
    {policies.length?<div className="so-policy-list">
     {policies.map(p=><button type="button" key={p.name} className="so-policy-line"
      onClick={()=>go('incidents',{category:String(p.name),status:''})}
      aria-label={'Инциденты по политике '+p.name+': '+safeCount(p.count)}>
      <span className="so-policy-head"><span title={p.name}>{p.name}</span><strong>{safeCount(p.count)}</strong></span>
      <span className="so-policy-track"><span style={{width:(Number(p.count||0)/most*100)+'%'}}/></span>
     </button>)}
    </div>:<p className="so-compact-empty">Нет срабатываний политик за период</p>}
   </section>
  </div>

  <section className="so-panel so-services">
   <SectionHeading title="Состояние обработки" subtitle="Технические признаки, доступные системе мониторинга"
    action={<button className="so-subtle-link" onClick={()=>go('system')}>Диагностика →</button>}/>
   <div className="so-status-grid">
    {healthEntries.map(([name,value])=><button type="button" className="so-status" key={name}
     onClick={()=>go('system')} aria-label={name+': '+value}>
     <span>{name}</span><Badge value={value}/>
    </button>)}
    <button type="button" className="so-status so-status-queue" onClick={()=>go('jobs')}
     aria-label={'Неуспешные задания: '+safeCount(dead)}>
     <span>Ошибки заданий</span><strong>{safeCount(dead)}</strong>
    </button>
   </div>
   <p className="so-panel-footnote">
    UNKNOWN — телеметрия не подтверждена, не обязательно сбой. {open>0?'Открытые инциденты требуют внимания аналитика.':'Открытых инцидентов за период нет.'}
   </p>
  </section>
 </div>;
}
