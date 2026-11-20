import {useEffect,useState,type FormEvent} from 'react';
import {CategoryPicker} from './CategoryPicker';
import {EditorDialog} from './EditorDialog';
import {json,type API,type Row} from './components';

export function MLDatasets({api,admin}:{api:API,admin:boolean}){
 const [datasets,setDatasets]=useState<Row[]>([]);
 const [selected,setSelected]=useState<string>('');
 const [samples,setSamples]=useState<Row[]>([]);
 const [stats,setStats]=useState<Row|null>(null);
 const [edit,setEdit]=useState<Row|null>(null),[uploadOpen,setUploadOpen]=useState(false),[approved,setApproved]=useState(false);
 const [labels,setLabels]=useState<string[]>([]);
 const [offset,setOffset]=useState(0),[error,setError]=useState(''),[dialogError,setDialogError]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
 const reload=()=>api('ml/datasets').then(d=>setDatasets(d.items||[])).catch(e=>setError(String(e)));
 const getSamples=async(id:string,skip=0)=>{
  const [items,summary]=await Promise.all([
   api('ml/datasets/'+id+'/examples?offset='+skip+'&limit=20'),
   api('ml/datasets/'+id+'/stats'),
  ]);
  setSamples(items.items||[]);setStats(summary);setOffset(skip);
 };
 useEffect(()=>{void reload()},[]);
 const act=async(work:()=>Promise<void>)=>{setBusy(true);setError('');setMessage('');
  try{await work()}catch(e){setError(String(e))}finally{setBusy(false)}
 };
 const upload=(e:FormEvent<HTMLFormElement>)=>{
  e.preventDefault();
  const form=new FormData(e.currentTarget);
  const mapping=String(form.get('label_mapping')||'{}');
  try{JSON.parse(mapping)}catch{setDialogError('Сопоставление меток должно быть JSON-объектом');return}
  setDialogError('');
  void act(async()=>{const result=await api('ml/datasets/import',{method:'POST',body:form});
    setMessage('Датасет загружен, все примеры требуют проверки аналитика.');
    await reload();setSelected(result.id);setUploadOpen(false);await getSamples(result.id);
  });
 };
 const review=(sample:Row,approved:boolean)=>{
  void act(async()=>{
   await api('ml/datasets/'+selected+'/examples/'+sample.id,json({labels:edit?.id===sample.id?labels:sample.labels,approved},'PUT'));
   setEdit(null);await getSamples(selected,offset);
   setMessage(approved?'Метки подтверждены':'Разметка сохранена как неподтверждённая');
  });
 };
 return <div className="ml-datasets">
  <h2>Наборы данных для ML</h2>
  <p className="muted">Загружайте CSV или JSONL, предварительно размеченные вручную или внешней LLM.
   MICE не отправляет текст во внешние сервисы. Предложенные метки не используются для обучения до проверки аналитиком.</p>
  {admin&&<div className="ml-dataset-toolbar"><button type="button" className="primary" onClick={()=>{setDialogError('');setUploadOpen(true)}}>＋ Импортировать датасет</button></div>}
  {admin&&uploadOpen&&<EditorDialog title="Импортировать набор данных" subtitle="CSV/JSONL с проверяемыми метками" wide
   busy={busy} onClose={()=>setUploadOpen(false)} onSubmit={upload} submitLabel="Загрузить на проверку">
   <div className="filters">
    <label>Название<input name="name" required minLength={2} maxLength={160} placeholder="Финансовые документы"/></label>
    <label>Источник<input name="source" defaultValue="external-llm" maxLength={120}/></label>
   </div>
   <label>CSV или JSONL (UTF-8, до 12 МиБ)<input name="file" type="file" required accept=".csv,.jsonl"/></label>
   <label>Описание<input name="description" maxLength={2000} placeholder="Размечено внешней LLM, проверка вручную"/></label>
   <details><summary>Сопоставление меток внешней LLM с категориями</summary>
    <label>JSON-объект: внешнее название → код существующей категории
     <textarea name="label_mapping" defaultValue="{}" rows={3}/>
    </label>
    <small>Если названия совпадают с названиями или кодами категорий MICE, поле оставьте пустым. Для безопасных текстов передайте пустой список меток или NORMAL.</small>
   </details>
   {(dialogError||error)&&<p role="alert" className="error edit-error">{dialogError||error}</p>}
  </EditorDialog>}
  {error&&<p role="alert" className="error">{error}</p>}
  {message&&<p role="status" className="notice">{message}</p>}
  <section><header><h3>Датасеты</h3><button disabled={busy} onClick={()=>void reload()}>Обновить</button></header>
   {!datasets.length&&<p className="muted">Импортированных датасетов пока нет</p>}
   {datasets.map(d=><div className="policy-row" key={d.id}>
    <div className="policy-info"><strong>{d.name} · v{d.version}</strong>
     <p>{d.example_count} примеров · {d.source} · {d.status}</p>
    </div>
    <button disabled={busy} onClick={()=>{setSelected(d.id);setEdit(null);void act(()=>getSamples(d.id,0))}}>
     Проверить примеры
    </button>
   </div>)}
  </section>
  {selected&&<section className="ml-dataset-review">
   <header><div><h3>Проверка разметки</h3><small>{stats?.approved??0} подтверждено из {stats?.total??0}</small></div>
    <button onClick={()=>{setSelected('');setSamples([]);setStats(null)}}>Закрыть</button>
   </header>
   {samples.map(sample=><article key={sample.id} className="ml-example">
    <p className="ml-example-text">{sample.text}</p>
    <p className="muted">Метки: {(sample.labels||[]).join(', ')} · {sample.approved?'Подтверждено':'Требует проверки'}</p>
    <div className="actions">
     <button type="button" disabled={busy} onClick={()=>{setEdit(sample);setLabels(sample.labels||[]);setApproved(!!sample.approved)}}>
      Изменить и проверить разметку
     </button>
    </div>
   </article>)}
   <nav className="pagination">
    <button disabled={offset<=0||busy} onClick={()=>void act(()=>getSamples(selected,Math.max(0,offset-20)))}>Назад</button>
    <span>Примеры {offset+1}–{offset+samples.length}</span>
    <button disabled={samples.length<20||busy} onClick={()=>void act(()=>getSamples(selected,offset+20))}>Далее</button>
   </nav>
  </section>}
  {edit&&<EditorDialog title="Проверить разметку" subtitle="Проверьте текст и метки перед включением в обучение" wide
   busy={busy} onClose={()=>setEdit(null)} onSubmit={()=>review(edit,approved)}
   submitLabel={approved?'Сохранить и подтвердить':'Сохранить без подтверждения'}
   submitDisabled={labels.length===0}>
   <div className="ml-example-text">{edit.text}</div>
   <CategoryPicker api={api} value={labels} onChange={setLabels} usage="ml"/>
   <label><input type="checkbox" checked={approved} onChange={e=>setApproved(e.target.checked)}/>
    Метки проверены аналитиком</label>
   {error&&<p role="alert" className="error edit-error">{error}</p>}
  </EditorDialog>}
 </div>;
}

export function MLTrainingOptions({api,disabled=false}:{api:API,disabled?:boolean}){
 const [engine,setEngine]=useState('tfidf'),[dataset,setDataset]=useState(''),
 [category,setCategory]=useState(''),[datasets,setDatasets]=useState<Row[]>([]),[categories,setCategories]=useState<Row[]>([]);
 useEffect(()=>{api('ml/datasets').then(d=>setDatasets(d.items||[])).catch(()=>{});
  api('categories').then(d=>setCategories(d.items||[])).catch(()=>{})},[]);
 return <div className="ml-training-options">
  <label>Движок обучения<select name="engine" value={engine} onChange={e=>setEngine(e.target.value)} disabled={disabled}>
   <option value="tfidf">TF-IDF — лёгкий базовый классификатор</option>
   <option value="setfit">SetFit — обучение с небольшим числом примеров</option>
   <option value="rubert">RuBERT-tiny2 — нейросетевой классификатор</option>
  </select></label>
  <label>Датасет<select name="dataset_id" value={dataset} onChange={e=>setDataset(e.target.value)} disabled={disabled}>
   <option value="">Все подтверждённые примеры</option>
   {datasets.map(d=><option value={d.id} key={d.id}>{d.name} (v{d.version})</option>)}
  </select></label>
  {engine!=='tfidf'&&<label>Категория для модели<select name="category_id" required value={category}
   onChange={e=>setCategory(e.target.value)} disabled={disabled}>
   <option value="">Выберите категорию</option>
   {categories.filter(c=>c.active&&c.mode!=='label').map(c=>
    <option key={c.id} value={c.id}>{c.name}</option>)}
  </select></label>}
  <p className="muted">{engine==='tfidf'?
   'Общая многометочная модель; сохраняет существующий быстрый режим.':
   'Модель обучается распознавать одну категорию по положительным и отрицательным примерам. Нужны локально установленные зависимости и базовая модель; внешняя LLM не используется.'}</p>
 </div>;
}
