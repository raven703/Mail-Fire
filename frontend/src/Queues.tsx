import {useEffect,useState} from 'react';
import {Table,type API,type Row} from './components';
export function Queues({api}:{api:API}){
 const [rows,setRows]=useState<Row[]>([]),[error,setError]=useState('');
 useEffect(()=>{api('monitoring/queues').then(d=>setRows(d.items)).catch(e=>setError(String(e)))},[]);
 const sum=(status:string)=>rows.filter(r=>r.status===status).reduce((n,r)=>n+Number(r.count),0);
 return <section><h2>Состояние очередей</h2>{error&&<p role="alert">{error}</p>}<div className="cards">{[['PENDING','Ожидают'],['RUNNING','Выполняются'],['DONE','Завершено заданий'],['DEAD','Ошибки']].map(([s,t])=><article key={s}><span>{t}</span><h2>{sum(s)}</h2></article>)}</div><Table rows={rows} columns={ [['kind','Стадия'],['status','Состояние'],['count','Заданий'],['max_attempts','Максимум попыток'],['average_total_seconds','Среднее время, с'],['p95_total_seconds','p95, с'],['oldest_age_seconds','Возраст старейшего, с'],['expired_leases','Просрочены']]}/><p className="muted">Стадии показаны в соответствии с фактическими заданиями. Парсинг, OCR и DLP выполняются внутри задания анализа и не имеют отдельных очередей. DONE означает завершение задания, а не гарантированно полный анализ письма.</p></section>
}