import {useState} from 'react';
import './message-selection.css';
import {Badge,Value,date,type API,type Row} from './components';

export function MessageSelection({rows,columns,onOpen,api,canAnalyze}:{rows:Row[],columns:[string,string][],onOpen:(row:Row)=>void,api:API,canAnalyze:boolean}){
 const [selected,setSelected]=useState<Set<string>>(new Set()),[running,setRunning]=useState(false),[notice,setNotice]=useState(''),[progress,setProgress]=useState(0);
 const ids=rows.map(r=>String(r.id)),chosen=ids.filter(id=>selected.has(id));
 function toggle(id:string){setSelected(old=>{const next=new Set(old);if(next.has(id))next.delete(id);else next.add(id);return next})}
 async function reanalyze(){
  if(running||!chosen.length)return;
  setRunning(true);setNotice('');setProgress(0);let queued=0;const failed:string[]=[];const errors:string[]=[];
  try{
   for(const id of chosen){try{await api(`messages/${encodeURIComponent(id)}/reanalyze`,{method:'POST'});queued++}catch(error){failed.push(id);errors.push(String(error))}setProgress(queued+failed.length)}
   setSelected(new Set(failed));setNotice(`Поставлено в очередь: ${queued}. Ошибок: ${failed.length}.${errors.length?' '+errors[0]:''}`);
  }finally{setRunning(false)}
 }
 return <>
  {canAnalyze&&<div className="message-bulk-bar" aria-busy={running}><label className="message-select-all"><input type="checkbox" disabled={running||!ids.length} checked={!!ids.length&&chosen.length===ids.length} ref={node=>{if(node)node.indeterminate=chosen.length>0&&chosen.length<ids.length}} onChange={e=>{const checked=e.currentTarget.checked;setSelected(checked?new Set(ids):new Set())}}/> Выбрать страницу</label><span className="message-selection-count">Выбрано <strong>{chosen.length}</strong></span><div className="message-bulk-buttons"><button className="primary" disabled={running||!chosen.length} onClick={()=>void reanalyze()}>{running?`Отправка ${progress} / ${chosen.length}…`:'Переанализировать'}</button><button disabled={running||!selected.size} onClick={()=>setSelected(new Set())}>Снять выбор</button></div></div>}
  {notice&&<p className="message-bulk-notice" role="status">{notice}</p>}
  {!rows.length?<div className="empty">Нет данных по выбранным условиям</div>:<div className="table"><table><thead><tr>{canAnalyze&&<th>Выбор</th>}{columns.map(([k,t])=><th key={k}>{t}</th>)}</tr></thead><tbody>{rows.map(r=><tr key={r.id} className={'clickable '+(r.severity||'')+(selected.has(String(r.id))?' message-row-selected':'')} tabIndex={0} onClick={()=>onOpen(r)} onKeyDown={e=>{if(e.target===e.currentTarget&&e.key==='Enter')onOpen(r)}}>{canAnalyze&&<td onClick={e=>e.stopPropagation()}><input type="checkbox" aria-label={`Выбрать письмо ${r.subject||r.id}`} disabled={running} checked={selected.has(String(r.id))} onChange={()=>toggle(String(r.id))}/></td>}{columns.map(([k])=><td key={k}>{k==='created_at'?date(r[k]):['severity','status'].includes(k)?<Badge value={r[k]}/>:<Value value={r[k]}/>}</td>)}</tr>)}</tbody></table></div>}
 </>;
}