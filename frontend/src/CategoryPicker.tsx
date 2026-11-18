import {useEffect,useState} from 'react';
import {json,type API,type Row} from './components';

export function CategoryCreator({api,onCreated,onCancel}:{api:API,onCreated:(c:Row)=>void,onCancel:()=>void}){
 const [name,setName]=useState(''),[group,setGroup]=useState('Конфиденциальные данные'),
 [mode,setMode]=useState('ml'),[phrases,setPhrases]=useState(''),[reference,setReference]=useState(''),
 [references,setReferences]=useState<Row[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{api('references').then(d=>setReferences(d.items||[])).catch(()=>setReferences([]))},[]);
 return <form className="category-create" onSubmit={e=>{e.preventDefault();setError('');setBusy(true);
  void api('categories',json({name,group_name:group,mode,keywords:mode==='keywords'?phrases.split('\n').map(s=>s.trim()).filter(Boolean):[],reference_id:mode==='reference'?reference:null}))
   .then(onCreated).catch(e=>setError(String(e))).finally(()=>setBusy(false))}}>
  <h3>Новая категория</h3>
  <label>Название<input required minLength={2} maxLength={160} value={name} onChange={e=>setName(e.target.value)}/></label>
  <label>Группа<input required value={group} onChange={e=>setGroup(e.target.value)}/></label>
  <label>Способ обнаружения<select value={mode} onChange={e=>setMode(e.target.value)}>
   <option value="ml">ML — после обучения</option>
   <option value="keywords">Ключевые фразы</option>
   <option value="reference">По эталонному документу</option>
  </select></label>
  {mode==='keywords'&&<label>Ключевые фразы по одной на строку<textarea required value={phrases} onChange={e=>setPhrases(e.target.value)}/></label>}
  {mode==='reference'&&<label>Эталонный документ<select value={reference} required onChange={e=>setReference(e.target.value)}>
    <option value="">Выберите эталон</option>{references.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}
  </select></label>}
  <p className="muted">{mode==='ml'?'ML-категория начнёт обнаруживаться только после обучения и публикации модели.':mode==='keywords'?'Поиск выполняется по тексту и вложениям.':'Срабатывание зависит от совпадения с выбранным эталоном.'}</p>
  {error&&<p role="alert" className="error">{error}</p>}
  <div className="actions"><button disabled={busy} className="primary">Создать</button><button type="button" onClick={onCancel}>Отмена</button></div>
 </form>;
}

export function CategoryPicker({api,value,onChange,canCreate=false,usage='ml'}:
 {api:API,value:string[],onChange:(v:string[])=>void,canCreate?:boolean,usage?:'policy'|'ml'}){
 const [items,setItems]=useState<Row[]>([]),[q,setQ]=useState(''),[adding,setAdding]=useState(false),[error,setError]=useState('');
 useEffect(()=>{api('categories').then(d=>setItems(d.items||[])).catch(e=>setError(String(e)))},[]);
 const chosen=items.filter(c=>value.includes(c.id));
 const filtered=items.filter(c=>c.active&&(usage!=='policy'||c.mode!=='label') &&
   (c.name.toLowerCase().includes(q.toLowerCase())||c.group_name.toLowerCase().includes(q.toLowerCase())));
 const groups=[...new Set(filtered.map(c=>String(c.group_name)))];
 return <div className="category-picker">
  <label>Категории для {usage==='policy'?'политики':'обучения'}<input value={q} onChange={e=>setQ(e.target.value)} placeholder="Поиск: ИНН, паспорт, секреты…"/></label>
  <div className="category-options">{groups.map(group=><section key={group}><strong>{group}</strong>
    {filtered.filter(c=>c.group_name===group).map(c=><label className="category-option" key={c.id}>
       <input type="checkbox" checked={value.includes(c.id)} onChange={e=>onChange(e.target.checked?[...value,c.id]:value.filter(id=>id!==c.id))}/>
       <span>{c.name}<small>{c.mode==='ml'?'ML':c.mode==='keywords'?'Ключевые фразы':c.mode==='reference'?'Эталон':c.mode==='label'?'Учебная метка':'Системный детектор'}</small></span>
      </label>)}</section>)}
    {!filtered.length&&<p className="muted">Совпадений нет</p>}</div>
  <div className="category-chips">{chosen.map(c=><button type="button" title="Убрать категорию" key={c.id} onClick={()=>onChange(value.filter(id=>id!==c.id))}>{c.name} ×</button>)}</div>
  <p className="muted">Выбрано: {value.length}{usage==='policy'&&value.length===0?' · Пустой выбор означает все категории':''}</p>
  {error&&<p role="alert" className="error">{error}</p>}
  {canCreate&&!adding&&<button type="button" onClick={()=>setAdding(true)}>＋ Создать новую категорию</button>}
  {adding&&<CategoryCreator api={api} onCancel={()=>setAdding(false)} onCreated={c=>{setItems(old=>[...old,c]);onChange([...value,c.id]);setAdding(false)}}/>}
 </div>;
}
