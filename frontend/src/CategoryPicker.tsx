import {useEffect,useState} from 'react';
import {EditorDialog} from './EditorDialog';
import {json,type API,type Row} from './components';

type Kind='keywords'|'regex'|'reference'|'ml';
type Rule={id?:string,kind:Kind,title:string,enabled:boolean,risk:number,priority:number,exclude_phrases:string[],phrases:string[],match_type:string,terms:{text:string,weight:number,required:boolean}[],min_score:number,window:number,ordered:boolean,pattern:string,reference_ids:string[],min_similarity:number,min_confidence:number};
const blank=(kind:Kind='keywords'):Rule=>({kind,title:'',enabled:true,risk:70,priority:100,exclude_phrases:[],phrases:[],match_type:'substring',terms:[],min_score:1,window:12,ordered:false,pattern:'',reference_ids:[],min_similarity:.8,min_confidence:.7});
const modeNames:Record<Kind,string>={keywords:'Ключевые слова',regex:'Безопасный Regex',reference:'Эталонные документы',ml:'ML-модель'};

export function CategoryForm({api,initial,onSaved,onCancel}:{api:API,initial?:Row,onSaved:(v:Row)=>void,onCancel:()=>void}){
 const [name,setName]=useState(String(initial?.name||'')),[group,setGroup]=useState(String(initial?.group_name||'Конфиденциальные данные'));
 const [description,setDescription]=useState(String(initial?.description||'')),[matchMode,setMatchMode]=useState<'any'|'all'>(initial?.match_mode==='all'?'all':'any');
 const [active,setActive]=useState(initial?.active!==false),[error,setError]=useState(''),[busy,setBusy]=useState(false),[refs,setRefs]=useState<Row[]>([]);
 const [rules,setRules]=useState<Rule[]>(()=>initial?.rules?.map((r:Row)=>({
  kind:r.kind,title:r.title||'',enabled:r.enabled!==false,risk:r.risk??70,
  priority:r.priority??100,exclude_phrases:r.exclude_phrases||[],
  phrases:r.phrases||[],match_type:r.match_type||'substring',terms:r.terms||[],min_score:r.min_score??1,window:r.window??12,ordered:r.ordered??false,pattern:r.pattern||'',reference_ids:r.reference_ids||[],
  min_similarity:r.min_similarity??.8,min_confidence:r.min_confidence??.7,
 }))||[blank()]);
 useEffect(()=>{api('references').then(d=>setRefs(d.items||[])).catch(()=>setRefs([]))},[]);
 const edit=(index:number,patch:Partial<Rule>)=>setRules(old=>old.map((r,i)=>i===index?{...r,...patch}:r));
 const save=()=>{if(!name.trim()||!group.trim()||!rules.length){setError('Укажите имя, группу и хотя бы одно правило');return}
  setBusy(true);setError('');
  const payload={name:name.trim(),group_name:group.trim(),description,active,match_mode:matchMode,rules};
  void api('categories'+(initial?'/'+initial.id:''),json(payload,initial?'PUT':'POST')).then(onSaved).catch(e=>setError(String(e))).finally(()=>setBusy(false));
 };
 return <EditorDialog title={initial?'Редактировать категорию':'Новая категория'}
  subtitle="Основные настройки и независимые правила обнаружения"
  onClose={onCancel} onSubmit={()=>save()} submitLabel="Сохранить категорию"
  busy={busy} wide>
  <div className="category-create">
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
   <label>Тип<select value={rule.kind} onChange={e=>edit(index,{...blank(e.target.value as Kind),title:rule.title,enabled:rule.enabled,risk:rule.risk,priority:rule.priority,exclude_phrases:rule.exclude_phrases})}>
    {Object.entries(modeNames).map(([id,title])=><option key={id} value={id}>{title}</option>)}
   </select></label>
   <label>Название правила<input maxLength={160} placeholder="Например, Номер договора" value={rule.title} onChange={e=>edit(index,{title:e.target.value})}/></label>
   <label>Уровень риска (0–100)<input type="number" min={0} max={100} value={rule.risk} onChange={e=>edit(index,{risk:Number(e.target.value)})}/></label>
   <label>Приоритет (меньше — раньше)<input type="number" min={0} max={10000} value={rule.priority} onChange={e=>edit(index,{priority:Number(e.target.value)})}/></label>
   <label>Фразы исключения (по одной на строку)<textarea value={rule.exclude_phrases.join('\n')} onChange={e=>edit(index,{exclude_phrases:e.target.value.split('\n')})}/></label>
   <label><input type="checkbox" checked={rule.enabled} onChange={e=>edit(index,{enabled:e.target.checked})}/>Включено</label>
   {rule.kind==='keywords'&&<>
    <label>Режим поиска<select value={rule.match_type} onChange={e=>edit(index,{match_type:e.target.value})}>
     <option value="substring">Точная подстрока (как раньше)</option>
     <option value="word">Слово или непрерывная фраза</option>
     <option value="morphology">Морфологические формы слов</option>
     <option value="flexible">Гибкая фраза с весами</option>
    </select></label>
    {rule.match_type!=='flexible'?<label>Слова или фразы, по одной на строку<textarea value={rule.phrases.join('\n')} onChange={e=>edit(index,{phrases:e.target.value.split('\n')})} placeholder="Финансовый прогноз"/></label>:
    <>
     <label>Термины: текст | вес (1–100) | обязателен (да/нет)
      <textarea rows={5} value={rule.terms.map(t=>[t.text,t.weight,t.required?'да':'нет'].join(' | ')).join('\n')} onChange={e=>edit(index,{terms:e.target.value.split('\n').filter(Boolean).map(x=>{const [text,weight,required]=x.split('|').map(y=>y.trim());return {text,weight:Number(weight||1),required:required==='да'||required==='true'}})})}/>
     </label>
     <label>Минимальный суммарный вес<input type="number" min={1} max={1000} value={rule.min_score} onChange={e=>edit(index,{min_score:Number(e.target.value)})}/></label>
     <label>Окно между словами (токенов)<input type="number" min={1} max={80} value={rule.window} onChange={e=>edit(index,{window:Number(e.target.value)})}/></label>
     <label><input type="checkbox" checked={rule.ordered} onChange={e=>edit(index,{ordered:e.target.checked})}/>Сохранять порядок терминов</label>
    </>}
   </>}
   {rule.kind==='regex'&&<><label>Regex-шаблон<input value={rule.pattern} maxLength={120} onChange={e=>edit(index,{pattern:e.target.value})} placeholder="[A-Z]{2,5}-\d{3,6}"/></label><p className="muted">Ограниченный безопасный синтаксис: классы, границы и ограниченные повторы; без групп, альтернатив и .*.</p></>}
   {rule.kind==='reference'&&<><p className="muted">Выберите один или несколько загруженных эталонных документов.</p><div className="category-options">
    {refs.length===0&&<p>Нет доступных эталонов или отсутствует разрешение на просмотр.</p>}
    {refs.map(ref=><label className="category-option" key={ref.id}><input type="checkbox" checked={rule.reference_ids.includes(ref.id)} onChange={e=>edit(index,{reference_ids:e.target.checked?[...rule.reference_ids,ref.id]:rule.reference_ids.filter(id=>id!==ref.id)})}/>{ref.name}</label>)}
    </div><label>Порог сходства (0.5–1)<input type="number" min={.5} max={1} step={.01} value={rule.min_similarity} onChange={e=>edit(index,{min_similarity:Number(e.target.value)})}/></label></>}
   {rule.kind==='ml'&&<><label>Минимальная уверенность ML (0–1)<input type="number" min={0} max={1} step={.01} value={rule.min_confidence} onChange={e=>edit(index,{min_confidence:Number(e.target.value)})}/></label><p className="muted">Начнёт обнаруживать только после обучения и публикации модели с этой категорией.</p></>}
  </section>)}
  <button type="button" onClick={()=>setRules(old=>[...old,blank()])} disabled={busy||rules.length>=30}>＋ Добавить правило</button>
  {error&&<p role="alert" className="error edit-error">{error}</p>}
 </div>
 </EditorDialog>;
}

export function CategoryCreator({api,onCreated,onCancel}:{api:API,onCreated:(c:Row)=>void,onCancel:()=>void}){
 return <CategoryForm api={api} onSaved={onCreated} onCancel={onCancel}/>;
}

export function CategoryPicker({api,value,onChange,canCreate=false,usage='ml'}:
 {api:API,value:string[],onChange:(v:string[])=>void,canCreate?:boolean,usage?:'policy'|'ml'}){
 const [items,setItems]=useState<Row[]>([]),[q,setQ]=useState(''),[adding,setAdding]=useState(false),[error,setError]=useState('');
 const refresh=()=>api('categories').then(d=>setItems(d.items||[])).catch(e=>setError(String(e)));
 useEffect(()=>{void refresh()},[]);
 const chosen=items.filter(c=>value.includes(c.id));
 const filtered=items.filter(c=>c.active&&(usage!=='policy'||c.mode!=='label') &&
   (c.name.toLocaleLowerCase('ru').includes(q.toLocaleLowerCase('ru')) ||
    c.group_name.toLocaleLowerCase('ru').includes(q.toLocaleLowerCase('ru'))));
 const groups=[...new Set(filtered.map(c=>String(c.group_name)))];
 return <div className="policy-category-card">
  <div className="policy-category-heading">
   <div><strong>Категории обнаружения</strong>
    <p>{usage==='policy'?'Выберите, какие типы данных контролировать':'Выберите подтверждённые категории для обучения'}</p>
   </div>
   <span className="policy-category-count" aria-live="polite">{value.length} выбрано</span>
  </div>
  <label className="policy-category-search">
   <span className="visually-hidden">Поиск категорий</span>
   <input type="search" value={q} onChange={e=>setQ(e.target.value)}
    placeholder="Поиск: паспорт, ИНН, секреты…" autoComplete="off"/>
  </label>
  <div className="policy-category-scroll" role="group" aria-label="Доступные категории обнаружения">
   {groups.map(group=><div className="policy-category-group" key={group}>
    <div className="policy-category-group-name">{group}</div>
    {filtered.filter(c=>c.group_name===group).map(c=><label className="policy-category-option" key={c.id}>
     <input type="checkbox" checked={value.includes(c.id)}
      onChange={e=>onChange(e.target.checked?[...value,c.id]:value.filter(id=>id!==c.id))}/>
     <span className="policy-category-option-title">{c.name}
      <small>{c.mode==='label'?'Учебная категория':c.mode==='builtin'?'Системный детектор':
       c.rules?.map((r:Row)=>modeNames[r.kind as Kind]||r.kind).join(' · ')||'Правила обнаружения'}</small>
     </span><code className="policy-category-code">{c.id}</code>
    </label>)}
   </div>)}
   {!filtered.length&&<p className="policy-category-empty">По вашему запросу ничего не найдено</p>}
  </div>
  <div className="policy-category-footer">
   <div className="policy-category-selected">
    {chosen.map(c=><button type="button" className="policy-category-chip" key={c.id}
      title={'Убрать: '+c.name} aria-label={'Убрать категорию '+c.name}
      onClick={()=>onChange(value.filter(id=>id!==c.id))}>{c.name} <span aria-hidden="true">×</span></button>)}
    {!value.length&&<span className="muted">{usage==='policy'?'Не выбрано — контроль всех категорий':'Пока ничего не выбрано'}</span>}
   </div>
   <div className="policy-category-actions">
    {canCreate&&!adding&&<button type="button" className="policy-category-add" onClick={()=>setAdding(true)}>＋ Новая категория</button>}
    {value.length>0&&<button type="button" className="policy-category-reset" onClick={()=>onChange([])}>Сбросить</button>}
   </div>
  </div>
  {error&&<p role="alert" className="error">{error}</p>}
   {adding&&<CategoryForm api={api} onCancel={()=>setAdding(false)}
   onSaved={c=>{setItems(old=>[...old,c]);onChange([...value,c.id]);setAdding(false)}}/>}
 </div>;
}
