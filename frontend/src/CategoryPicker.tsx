import {useEffect,useState} from 'react';
import {json,type API,type Row} from './components';

type Kind='keywords'|'regex'|'reference'|'ml';
type Rule={id?:string,kind:Kind,title:string,enabled:boolean,risk:number,phrases:string[],pattern:string,reference_ids:string[],min_similarity:number,min_confidence:number};
const blank=(kind:Kind='keywords'):Rule=>({kind,title:'',enabled:true,risk:70,phrases:[],pattern:'',reference_ids:[],min_similarity:.8,min_confidence:.7});
const modeNames:Record<Kind,string>={keywords:'Ключевые слова',regex:'Безопасный Regex',reference:'Эталонные документы',ml:'ML-модель'};

export function CategoryForm({api,initial,onSaved,onCancel}:{api:API,initial?:Row,onSaved:(v:Row)=>void,onCancel:()=>void}){
 const [name,setName]=useState(String(initial?.name||'')),[group,setGroup]=useState(String(initial?.group_name||'Конфиденциальные данные'));
 const [description,setDescription]=useState(String(initial?.description||'')),[matchMode,setMatchMode]=useState<'any'|'all'>(initial?.match_mode==='all'?'all':'any');
 const [active,setActive]=useState(initial?.active!==false),[error,setError]=useState(''),[busy,setBusy]=useState(false),[refs,setRefs]=useState<Row[]>([]);
 const [rules,setRules]=useState<Rule[]>(()=>initial?.rules?.map((r:Row)=>({
  kind:r.kind,title:r.title||'',enabled:r.enabled!==false,risk:r.risk??70,
  phrases:r.phrases||[],pattern:r.pattern||'',reference_ids:r.reference_ids||[],
  min_similarity:r.min_similarity??.8,min_confidence:r.min_confidence??.7,
 }))||[blank()]);
 useEffect(()=>{api('references').then(d=>setRefs(d.items||[])).catch(()=>setRefs([]))},[]);
 const edit=(index:number,patch:Partial<Rule>)=>setRules(old=>old.map((r,i)=>i===index?{...r,...patch}:r));
 const save=()=>{if(!name.trim()||!group.trim()||!rules.length){setError('Укажите имя, группу и хотя бы одно правило');return}
  setBusy(true);setError('');
  const payload={name:name.trim(),group_name:group.trim(),description,active,match_mode:matchMode,rules};
  void api('categories'+(initial?'/'+initial.id:''),json(payload,initial?'PUT':'POST')).then(onSaved).catch(e=>setError(String(e))).finally(()=>setBusy(false));
 };
 return <div className="category-create">
  <h3>{initial?'Редактирование категории':'Новая категория'}</h3>
  <label>Название категории<input required maxLength={160} value={name} onChange={e=>setName(e.target.value)}/></label>
  <label>Группа<input required maxLength={120} value={group} onChange={e=>setGroup(e.target.value)}/></label>
  <label>Описание<textarea maxLength={2000} value={description} onChange={e=>setDescription(e.target.value)}/></label>
  <label>Объединение правил<select value={matchMode} onChange={e=>setMatchMode(e.target.value as 'any'|'all')}>
   <option value="any">Любое правило (ИЛИ)</option><option value="all">Все включённые правила (И)</option>
  </select></label>
  <label><input type="checkbox" checked={active} onChange={e=>setActive(e.target.checked)}/>Категория активна</label>
  <h3>Правила обнаружения</h3>
  <p className="muted">Правила независимы. Выберите ИЛИ для любого совпадения, И — если нужны все признаки. Пустые или отключённые детекторы не считаются совпадением.</p>
  {rules.map((rule,index)=><section className="category-rule" key={index}>
   <div className="actions"><strong>Правило {index+1}</strong>
    <button type="button" aria-label={'Удалить правило '+(index+1)} onClick={()=>setRules(old=>old.filter((_,i)=>i!==index))}>Удалить</button></div>
   <label>Тип<select value={rule.kind} onChange={e=>edit(index,{...blank(e.target.value as Kind),title:rule.title,enabled:rule.enabled,risk:rule.risk})}>
    {Object.entries(modeNames).map(([id,title])=><option key={id} value={id}>{title}</option>)}
   </select></label>
   <label>Название правила<input maxLength={160} placeholder="Например, Номер договора" value={rule.title} onChange={e=>edit(index,{title:e.target.value})}/></label>
   <label>Уровень риска (0–100)<input type="number" min={0} max={100} value={rule.risk} onChange={e=>edit(index,{risk:Number(e.target.value)})}/></label>
   <label><input type="checkbox" checked={rule.enabled} onChange={e=>edit(index,{enabled:e.target.checked})}/>Включено</label>
   {rule.kind==='keywords'&&<label>Ключевые фразы, по одной на строку<textarea value={rule.phrases.join('\n')} onChange={e=>edit(index,{phrases:e.target.value.split('\n')})} placeholder="Финансовый прогноз&#10;Плановая выручка"/></label>}
   {rule.kind==='regex'&&<><label>Regex-шаблон<input value={rule.pattern} maxLength={120} onChange={e=>edit(index,{pattern:e.target.value})} placeholder="[A-Z]{2,5}-\d{3,6}"/></label><p className="muted">Ограниченный безопасный синтаксис: классы, границы и ограниченные повторы; без групп, альтернатив и .*.</p></>}
   {rule.kind==='reference'&&<><p className="muted">Выберите один или несколько загруженных эталонных документов.</p><div className="category-options">
    {refs.length===0&&<p>Нет доступных эталонов или отсутствует разрешение на просмотр.</p>}
    {refs.map(ref=><label className="category-option" key={ref.id}><input type="checkbox" checked={rule.reference_ids.includes(ref.id)} onChange={e=>edit(index,{reference_ids:e.target.checked?[...rule.reference_ids,ref.id]:rule.reference_ids.filter(id=>id!==ref.id)})}/>{ref.name}</label>)}
    </div><label>Порог сходства (0.5–1)<input type="number" min={.5} max={1} step={.01} value={rule.min_similarity} onChange={e=>edit(index,{min_similarity:Number(e.target.value)})}/></label></>}
   {rule.kind==='ml'&&<><label>Минимальная уверенность ML (0–1)<input type="number" min={0} max={1} step={.01} value={rule.min_confidence} onChange={e=>edit(index,{min_confidence:Number(e.target.value)})}/></label><p className="muted">Начнёт обнаруживать только после обучения и публикации модели с этой категорией.</p></>}
  </section>)}
  <button type="button" onClick={()=>setRules(old=>[...old,blank()])} disabled={rules.length>=30}>＋ Добавить правило</button>
  {error&&<p role="alert" className="error">{error}</p>}
  <div className="actions"><button type="button" className="primary" disabled={busy} onClick={save}>Сохранить категорию</button><button type="button" onClick={onCancel}>Отмена</button></div>
 </div>;
}

export function CategoryCreator({api,onCreated,onCancel}:{api:API,onCreated:(c:Row)=>void,onCancel:()=>void}){
 return <CategoryForm api={api} onSaved={onCreated} onCancel={onCancel}/>;
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
  <label>Категории для {usage==='policy'?'политики':'обучения'}<input value={q} onChange={e=>setQ(e.target.value)} placeholder="Поиск: ИНН, паспорт, финансовые документы…"/></label>
  <div className="category-options">{groups.map(group=><section key={group}><strong>{group}</strong>
    {filtered.filter(c=>c.group_name===group).map(c=><label className="category-option" key={c.id}>
       <input type="checkbox" checked={value.includes(c.id)} onChange={e=>onChange(e.target.checked?[...value,c.id]:value.filter(id=>id!==c.id))}/>
       <span>{c.name}<small>{c.mode==='label'?'Учебная метка':c.mode==='builtin'?'Системный детектор':c.rules?.map((r:Row)=>modeNames[r.kind as Kind]||r.kind).join(' + ')||'Нет активных правил'}</small></span>
      </label>)}</section>)}
    {!filtered.length&&<p className="muted">Совпадений нет</p>}</div>
  <div className="category-chips">{chosen.map(c=><button type="button" title="Убрать категорию" key={c.id} onClick={()=>onChange(value.filter(id=>id!==c.id))}>{c.name} ×</button>)}</div>
  <p className="muted">Выбрано: {value.length}{usage==='policy'&&value.length===0?' · Пустой выбор означает все категории':''}</p>
  {error&&<p role="alert" className="error">{error}</p>}
  {canCreate&&!adding&&<button type="button" onClick={()=>setAdding(true)}>＋ Создать новую категорию</button>}
  {adding&&<CategoryCreator api={api} onCancel={()=>setAdding(false)} onCreated={c=>{setItems(old=>[...old,c]);onChange([...value,c.id]);setAdding(false)}}/>}
 </div>;
}
