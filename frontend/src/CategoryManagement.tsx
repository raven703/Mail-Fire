import {useEffect,useState} from 'react';
import {CategoryCreator} from './CategoryPicker';
import {json,type API,type Row} from './components';

export function CategoryManagement({api,admin}:{api:API,admin:boolean}){
 const [items,setItems]=useState<Row[]>([]),[adding,setAdding]=useState(false),[editing,setEditing]=useState<Row|null>(null),
 [error,setError]=useState(''),[search,setSearch]=useState(''),[refs,setRefs]=useState<Row[]>([]);
 const refresh=()=>api('categories').then(d=>setItems(d.items||[])).catch(e=>setError(String(e)));
 useEffect(()=>{void refresh();api('references').then(d=>setRefs(d.items||[])).catch(()=>setRefs([]))},[]);
 const filtered=items.filter(c=>(c.name+' '+c.group_name).toLowerCase().includes(search.toLowerCase()));
 return <div className="management">
 <header><p className="muted">Единый каталог для политик и ML. Системные категории защищены, пользовательские можно архивировать.</p>
 {admin&&<button className="primary" onClick={()=>{setAdding(true);setEditing(null)}}>＋ Категория</button>}</header>
 <label>Поиск<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Название или группа"/></label>
 {error&&<p className="error" role="alert">{error}</p>}
 {adding&&<CategoryCreator api={api} onCancel={()=>setAdding(false)} onCreated={()=>{setAdding(false);void refresh()}}/>}
 {editing&&<form className="category-create" onSubmit={e=>{e.preventDefault();setError('');
   void api('categories/'+editing.id,json({name:editing.name,group_name:editing.group_name,
     description:editing.description||'',mode:editing.mode,keywords:editing.mode==='keywords'?(editing.keywordText||'').split('\n').map((s:string)=>s.trim()).filter(Boolean):[],
     reference_id:editing.mode==='reference'?editing.reference_id:null,active:editing.active},'PUT'))
    .then(()=>{setEditing(null);void refresh()}).catch(e=>setError(String(e)))}}>
  <h3>Редактирование категории</h3>
  <label>Название<input required value={editing.name} onChange={e=>setEditing({...editing,name:e.target.value})}/></label>
  <label>Группа<input required value={editing.group_name} onChange={e=>setEditing({...editing,group_name:e.target.value})}/></label>
  <label>Описание<textarea value={editing.description||''} onChange={e=>setEditing({...editing,description:e.target.value})}/></label>
  <label>Способ обнаружения<select value={editing.mode} onChange={e=>setEditing({...editing,mode:e.target.value})}>
    <option value="ml">ML</option><option value="keywords">Ключевые фразы</option><option value="reference">Эталон</option>
  </select></label>
  {editing.mode==='keywords'&&<label>Фразы по одной на строку<textarea value={editing.keywordText||''} onChange={e=>setEditing({...editing,keywordText:e.target.value})}/></label>}
  {editing.mode==='reference'&&<label>Эталон<select required value={editing.reference_id||''} onChange={e=>setEditing({...editing,reference_id:e.target.value})}>
    <option value="">Выберите эталон</option>{refs.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}
  </select></label>}
  <label><input type="checkbox" checked={editing.active} onChange={e=>setEditing({...editing,active:e.target.checked})}/>Активна</label>
  <div className="actions"><button className="primary">Сохранить</button><button type="button" onClick={()=>setEditing(null)}>Отмена</button></div>
 </form>}
 <section><h2>Категории ({items.length})</h2>
 {filtered.map(c=><div key={c.id} className="policy-row">
   <div className="policy-info"><strong>{c.name}</strong><p>{c.group_name} · {c.mode==='builtin'?'Системный детектор':c.mode==='label'?'Метка для ML':c.mode==='keywords'?'Ключевые фразы':c.mode==='reference'?'Эталон':'ML'}</p></div>
   <span className="muted">{c.active?'Активна':'Архив'}</span>
   {admin&&!c.system&&<div className="actions"><button onClick={()=>{setAdding(false);setEditing({...c,keywordText:(c.keywords||[]).join('\n')})}}>Изменить</button>
   {c.active&&<button onClick={()=>{if(confirm('Архивировать категорию? Существующая история сохранится.'))void api('categories/'+c.id+'/archive',json({})).then(refresh).catch(e=>setError(String(e)))}}>Архивировать</button>}</div>}
  </div>)}</section></div>;
}
