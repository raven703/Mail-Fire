import {useState} from 'react';
import {CategoryPicker} from './CategoryPicker';
import {json,type API,type Row} from './components';

export function PolicyEditor({row,api,saved}:{row?:Row,api:API,saved:()=>void}){
 const [error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [categories,setCategories]=useState<string[]>(row?.conditions?.categories||[]);
 const [direction,setDirection]=useState<string[]>(row?.conditions?.direction||[]);
 const directions=[['INBOUND','Входящая'],['OUTBOUND','Исходящая'],['INTERNAL','Внутренняя'],['UNKNOWN','Неизвестная']];
 return <section><h2>{row?'Редактирование политики':'Новая политика'}</h2>
 <form onSubmit={e=>{e.preventDefault();setBusy(true);setError('');const f=new FormData(e.currentTarget);
 const split=(k:string)=>String(f.get(k)||'').split(',').map(s=>s.trim()).filter(Boolean);
 void api('workspace/policies'+(row?'/'+row.id:''),json({
 name:f.get('name'),enabled:f.get('enabled')==='on',shadow:f.get('shadow')==='on',
 priority:Number(f.get('priority')),min_risk:Number(f.get('min_risk')),
 min_count:Number(f.get('min_count')),categories,senders:split('senders'),direction
 },row?'PUT':'POST')).then(saved).catch(e=>setError(String(e))).finally(()=>setBusy(false))}}>
 <label>Название<input name="name" required maxLength={200} defaultValue={row?.name}/></label>
 <div className="filters">
  <label>Минимальный риск<input name="min_risk" type="number" min={0} max={100} defaultValue={row?.conditions?.min_risk??40}/></label>
  <label>Минимум признаков<input name="min_count" type="number" min={1} max={1000} defaultValue={row?.conditions?.min_count??1}/></label>
  <label>Приоритет<input name="priority" type="number" min={0} max={10000} defaultValue={row?.priority??10}/></label>
 </div>
 <CategoryPicker api={api} value={categories} onChange={setCategories} canCreate usage="policy"/>
 <fieldset className="category-options"><legend>Направления доставки (пустой выбор — все)</legend>
 {directions.map(([id,name])=><label key={id} className="category-option"><input type="checkbox" checked={direction.includes(id)} onChange={e=>setDirection(e.target.checked?[...direction,id]:direction.filter(v=>v!==id))}/>{name}</label>)}
 </fieldset>
 <label>Отправители (точные email через запятую)<input name="senders" defaultValue={row?.conditions?.senders?.join(', ')||''}/></label>
 <label><input type="checkbox" name="enabled" defaultChecked={row?.enabled??true}/>Включена</label>
 <label><input type="checkbox" name="shadow" defaultChecked={row?.shadow??false}/>Теневой режим — не создавать инциденты</label>
 {error&&<p role="alert" className="error">{error}</p>}
 <button disabled={busy}>Сохранить политику</button></form></section>;
}
