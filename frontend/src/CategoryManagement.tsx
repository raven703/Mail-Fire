import {RulepackTransfer} from './RulepackTransfer';
import {useEffect,useState} from 'react';
import {CategoryForm} from './CategoryPicker';
import {json,type API,type Row} from './components';

export function CategoryManagement({api,admin}:{api:API,admin:boolean}){
 const [items,setItems]=useState<Row[]>([]),[creating,setCreating]=useState(false),[editing,setEditing]=useState<Row|null>(null);
 const [error,setError]=useState(''),[search,setSearch]=useState('');
 const refresh=()=>api('categories').then(d=>setItems(d.items||[])).catch(e=>setError(String(e)));
 useEffect(()=>{void refresh()},[]);
 const filtered=items.filter(c=>(c.name+' '+c.group_name).toLowerCase().includes(search.toLowerCase()));
 return <div className="management">
  {admin&&<RulepackTransfer api={api} onSaved={refresh}/>}
  <header><p className="muted">У категории может быть несколько независимых правил: ключевые фразы, безопасный Regex, эталоны, ML. Системные категории не редактируются.</p>
  {admin&&<button className="primary" onClick={()=>{setCreating(true);setEditing(null)}}>＋ Категория</button>}</header>
  <label>Поиск категории<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Название или группа"/></label>
  {error&&<p className="error" role="alert">{error}</p>}
  {creating&&<CategoryForm api={api} onCancel={()=>setCreating(false)} onSaved={async()=>{await refresh();setCreating(false)}}/>}
  {editing&&<CategoryForm key={editing.id} api={api} initial={editing} onCancel={()=>setEditing(null)} onSaved={async()=>{await refresh();setEditing(null)}}/>}
  <section><h2>Категории ({items.length})</h2>
  {filtered.map(c=><div key={c.id} className="policy-row">
    <div className="policy-info">
     <strong>{c.name}</strong>
     <p>{c.group_name} · {c.system?(c.mode==='label'?'ML-метка':'Системный детектор'):((c.rules||[]).length+' правил; '+(c.match_mode==='all'?'все (И)':'любое (ИЛИ)'))}</p>
     {!c.system&&<small>{(c.rules||[]).map((r:Row)=>r.title||r.kind).join(' · ')||'Нет правил'}</small>}
    </div>
    <span className="muted">{c.active?'Активна':'Архив'}</span>
    {admin&&!c.system&&<div className="actions">
     <button onClick={()=>{setCreating(false);setEditing(c)}}>Правила и настройки</button>
     {c.active&&<button onClick={()=>{if(confirm('Архивировать категорию? История сохранится.'))void api('categories/'+c.id+'/archive',json({})).then(refresh).catch(e=>setError(String(e)))}}>Архивировать</button>}
    </div>}
   </div>)}</section>
 </div>;
}
