import {RulepackTransfer} from './RulepackTransfer';
import {useEffect,useState,type FormEvent} from 'react';
import {EditorDialog} from './EditorDialog';
import {Badge,Table,Value,date,json,type API,type Row} from './components';
import {PolicyEditor} from './PolicyEditor';
import {CategoryPicker} from './CategoryPicker';
import {MLDatasets,MLTrainingOptions} from './MLDatasets';
export function Management({page,api,role,originals}:{page:string,api:API,role:string,originals:boolean}){
 const [data,setData]=useState<Row>({}),[error,setError]=useState(''),[busy,setBusy]=useState(false),[editing,setEditing]=useState<Row|null|undefined>(undefined),[result,setResult]=useState<Row|null>(null),[q,setQ]=useState(''),[offset,setOffset]=useState(0),[tab,setTab]=useState('Модели');
 const admin=role==='admin',canEdit=role!=='observer';
 const [categoryNames,setCategoryNames]=useState<Record<string,string>>({});
 async function load(){const path=page==='ml'?'ml/models':`catalog/${page}?q=${encodeURIComponent(q)}&offset=${offset}`;
  if(page==='policies'||page==='ml'){
   const [result,categories]=await Promise.all([api(path),api('categories')]);
   setData(result);
   setCategoryNames(Object.fromEntries((categories.items||[]).map((c:Row)=>[c.id,c.name])));
  }else setData(await api(path));
 }
 async function run(work:()=>Promise<void>){setBusy(true);setError('');try{await work()}catch(e){setError(String(e))}finally{setBusy(false)}}
 useEffect(()=>{setEditing(undefined);setResult(null);setData({});setQ('');setOffset(0);setTab('Модели');setExampleEditor(false);setTrainingEditor(false);setReferenceUploadOpen(false)},[page]);
 useEffect(()=>{const timer=setTimeout(()=>void run(load),250);return()=>clearTimeout(timer)},[page,q,offset]);
 const stats=(items:[string,unknown,string][])=> <div className="cards management-stats">{items.map(([name,value,note])=><article key={name}><span className="muted">{name}</span><strong>{String(value??'—')}</strong><small>{note}</small></article>)}</div>;
 const active=data.items?.find((m:Row)=>m.active);
 const [mlLabels,setMlLabels]=useState<string[]>([]);
 const [exampleEditor,setExampleEditor]=useState(false),[trainingEditor,setTrainingEditor]=useState(false),[referenceUploadOpen,setReferenceUploadOpen]=useState(false),[dialogError,setDialogError]=useState('');
 return <div className="management">{error&&<p className="error" role="alert">{error}</p>}{busy&&<p role="status">Выполняется…</p>}
 {page==='policies'&&<>{admin&&<RulepackTransfer api={api} onSaved={load}/>}<header><p className="muted">Правила сопоставляют результаты анализа с контекстом доставки.</p><div className="actions"><button onClick={()=>void run(async()=>setResult(await api('catalog/history')))}>История версий</button>{admin&&<button className="primary" onClick={()=>setEditing(null)}>＋ Новая политика</button>}</div></header>{stats([['Активные политики',data.active,'Включённые правила'],['В Shadow mode',data.shadow,'Без создания инцидентов'],['Срабатывания за сутки',data.daily_hits,'Последние 24 часа']])}<section><header><div><h2>Правила и политики</h2><p className="muted">Порядок сверху вниз · меньший номер приоритета проверяется первым</p></div>{admin&&<button disabled={busy} onClick={()=>{if(confirm('Переоценить последние 1000 почтовых событий? Новые инциденты могут попасть в SIEM.'))void run(async()=>setResult(await api('catalog/reevaluate',json({}))))}}>Переоценить результаты</button>}</header>{data.items?.map((r:Row)=><div className="policy-row" key={r.id}><span className="policy-icon">▤</span><div className="policy-info"><strong>{r.name}</strong><p>{r.conditions.categories?.length?r.conditions.categories.map((id:string)=>categoryNames[id]||id).join(', '):'Все категории'} · {r.conditions.category_match==='all'?'Все категории (И)':'Любая категория (ИЛИ)'} · риск от {r.conditions.min_risk??0} · от {r.conditions.min_count??1} сраб. · Приоритет {r.priority}</p></div><span className="score-pill">{r.hits} сраб./7д</span><Badge value={!r.enabled?'Отключена':r.shadow?'Shadow mode':'Активна'}/><button className={'toggle '+(r.enabled?'on':'')} role="switch" aria-checked={r.enabled} aria-label={'Включить '+r.name} disabled={!admin||busy} onClick={()=>void run(async()=>{await api(`catalog/policies/${r.id}/enabled`,json({enabled:!r.enabled},'PUT'));await load()})}/><button disabled={!admin} aria-label={'Настроить '+r.name} onClick={()=>setEditing(r)}>···</button>{admin&&<button disabled={busy} onClick={()=>{if(confirm('Архивировать политику «'+r.name+'»?'))void run(async()=>{await api('workspace/policies/'+r.id+'/archive',json({}));await load()})}}>Архивировать</button>}{admin&&<button disabled={busy} onClick={()=>{if(confirm('Удалить политику «'+r.name+'» из каталога? История срабатываний и аудит сохранятся.'))void run(async()=>{await api('workspace/policies/'+r.id,{method:'DELETE'});await load()})}}>Удалить</button>}</div>)}</section><p className="info-banner">Политики не блокируют доставку. Shadow mode не создаёт инциденты. Переоценка не удаляет существующие решения.</p>{editing!==undefined&&<PolicyEditor key={editing?.id||'new'} row={editing||undefined} api={api}
  onClose={()=>setEditing(undefined)} saved={()=>{setEditing(undefined);void run(load)}}/>}</>}
 {page==='detectors'&&<><p className="muted">Реальные компоненты анализа. Переключатели управляют использованием результатов при создании новых инцидентов; извлечение признаков сохраняется.</p><section><h2>Модули анализа содержимого</h2>{data.items?.map((r:Row)=><div className="policy-row" key={r.id}><span className="policy-icon">◇</span><div className="policy-info"><strong>{r.name}</strong><p>{r.engine}</p><small>{r.categories.join(', ')}</small></div><Badge value={!r.available?'Не обучен':r.enabled?'Включён':'Отключён'}/><button role="switch" aria-checked={r.enabled} aria-label={'Включить '+r.name} className={'toggle '+(r.enabled?'on':'')} disabled={!admin||busy} onClick={()=>void run(async()=>{await api(`catalog/detectors/${r.id}`,json({enabled:!r.enabled},'PUT'));await load()})}/></div>)}</section><p className="info-banner">OCR работает в отдельном parser-сервисе. Его конфигурация не меняется этими переключателями. Статус «Включён» — настройка, не live healthcheck.</p></>}
 {page==='references'&&<>{stats([['Документов в базе',data.total,'Библиотека эталонов'],['Проиндексировано',data.indexed,'Семантический индекс'],['Объём библиотеки',data.bytes!=null?(data.bytes/1048576).toFixed(2)+' МБ':null,'Хранение PostgreSQL']])}<section><div className="filters"><label>Поиск по эталонам<input value={q} onChange={e=>{setQ(e.target.value);setOffset(0)}}/></label>{canEdit&&originals&&<button type="button" className="primary" disabled={busy}
 onClick={()=>{setDialogError('');setReferenceUploadOpen(true)}}>＋ Добавить документ</button>}</div><div className="reference-grid">{data.items?.map((r:Row)=><article className="reference-card" key={r.id}><span className="policy-icon">▤</span><h3>{r.name}</h3><p>{date(r.created_at)}</p><p>{(r.size/1024).toFixed(1)} КБ · {r.chunks} фрагментов</p><Badge value={r.status==='INDEXED'?'Проиндексирован':'Текст извлечён'}/><div className="actions"><button onClick={()=>void run(async()=>setResult(await api(`catalog/references/${r.id}`)))}>Просмотр и совпадения</button>{canEdit&&<button disabled={busy} onClick={()=>void run(async()=>{await api(`catalog/references/${r.id}/reindex`,json({}));await load()})}>Индексировать</button>}{admin&&<button disabled={busy} onClick={()=>{if(confirm('Удалить эталон и его индекс? История инцидентов сохранится.'))void run(async()=>{await api(`catalog/references/${r.id}`,{method:'DELETE'});setResult(null);await load()})}}>Удалить</button>}</div></article>)}</div>{!data.items?.length&&<p className="empty">Эталоны не найдены</p>}<nav className="pagination"><button disabled={!offset} onClick={()=>setOffset(Math.max(0,offset-50))}>Назад</button><span>{offset+1} / {data.total||0}</span><button disabled={offset+50>=(data.total||0)} onClick={()=>setOffset(offset+50)}>Далее</button></nav></section></>}
 {page==='ml'&&<><div className="model-banner"><div><h2>{data.items?.filter((m:Row)=>m.active).length?('Активных моделей: '+data.items.filter((m:Row)=>m.active).length):'Активные модели отсутствуют'}</h2><p>TF-IDF / SetFit / RuBERT-tiny2 · {active?date(active.created_at):'Нужны размеченные примеры, обучение и публикация'}</p></div><Badge value={active?'Активна':'Не обучена'}/></div><nav className="tabs">{['Модели','Наборы данных','Обучающие примеры','Разметка','Обучение','Метрики качества'].map(t=><button className={tab===t?'selected':''} key={t} onClick={()=>{setTab(t);setResult(null);if(t==='Обучающие примеры')void run(async()=>setResult(await api('catalog/examples')))}}>{t}</button>)}</nav>{tab==='Наборы данных'&&canEdit&&originals&&<MLDatasets api={api} admin={admin}/>}{tab==='Модели'&&<section><h2>История версий</h2>{!data.items?.length&&<p className="empty">Обученных моделей нет</p>}{data.items?.map((m:Row)=><div className="policy-row" key={m.id}><span className="policy-icon">◎</span><div className="policy-info"><strong>{m.name}</strong><p>{date(m.created_at)} · {m.engine||'tfidf'} · {m.category_id?categoryNames[m.category_id]||m.category_id:'Общая модель'} · {m.metrics?.labels?.join(', ')}</p></div><Badge value={m.active?'Опубликована':m.eligible?'Прошла контроль':'Не прошла контроль'}/><button onClick={()=>setResult({name:m.name,metrics:{test:m.metrics.test,validation:m.metrics.validation,split_sizes:m.metrics.split_sizes}})}>Метрики</button>{admin&&<button disabled={busy||!m.eligible||m.active} onClick={()=>{if(confirm('Опубликовать эту версию вместо текущей?'))void run(async()=>{await api(`ml/models/${m.id}/publish`,json({}));await load()})}}>Опубликовать / откатить</button>}</div>)}</section>}{tab==='Разметка'&&canEdit&&<section>
 <header><div><h2>Разметка обучающих примеров</h2><p className="muted">Добавляйте проверенные синтетические примеры для обучения моделей.</p></div>
 <button className="primary" onClick={()=>{setMlLabels([]);setDialogError('');setExampleEditor(true)}}>＋ Добавить пример</button></header>
 </section>}
 {tab==='Обучение'&&<section>
 <header><div><h2>Контролируемое обучение</h2><p className="muted">Разделение на train/validation/test. Публикация — отдельное действие администратора.</p></div>
 {admin&&<button className="primary" onClick={()=>{setDialogError('');setTrainingEditor(true)}}>＋ Запустить обучение</button>}</header>
 <p className="muted">Обучение выполняется worker в очереди PostgreSQL. Состояние задания доступно в очереди.</p>
 </section>}
 {tab==='Метрики качества'&&<section><h2>Метрики активной модели на test</h2>{active?<Table rows={Object.entries(active.metrics.test||{}).map(([category,metrics])=>({category,...metrics as Row}))} columns={ [['category','Категория'],['precision','Precision'],['recall','Recall'],['f1','F1'],['support','Примеров']]}/>:<p>Нет опубликованной модели — метрики отсутствуют.</p>}</section>}</>}
 {page==='references'&&referenceUploadOpen&&<EditorDialog title="Добавить эталонный документ"
  subtitle="Выберите файл для дальнейшего сравнения с почтовыми сообщениями"
  busy={busy} onClose={()=>setReferenceUploadOpen(false)} submitLabel="Загрузить документ"
  onSubmit={async(e:FormEvent<HTMLFormElement>)=>{
   const body=new FormData(e.currentTarget);setBusy(true);setDialogError('');
   try{
    await api('references',{method:'POST',body});
    setReferenceUploadOpen(false);await load();
   }catch(err){setDialogError(String(err))}finally{setBusy(false)}
  }}>
  <label>Файл эталона<input type="file" name="file" required/></label>
  <p className="edit-intro">Используйте только данные, разрешённые для локальной обработки. Документ будет сохранён в PostgreSQL.</p>
  {dialogError&&<p role="alert" className="error edit-error">{dialogError}</p>}
 </EditorDialog>}
 {page==='ml'&&exampleEditor&&<EditorDialog title="Добавить обучающий пример"
  subtitle="Текст, категории и статус проверки" wide
  busy={busy} onClose={()=>setExampleEditor(false)} submitDisabled={!mlLabels.length}
  onSubmit={async(e:FormEvent<HTMLFormElement>)=>{
   const f=new FormData(e.currentTarget);
   setBusy(true);setDialogError('');
   try{
    const result=await api('ml/examples',json({text:f.get('text'),labels:mlLabels,approved:f.get('approved')==='on'}));
    setResult({status:'Пример сохранён',approved:result.approved});
    setExampleEditor(false);setMlLabels([]);
   }catch(err){setDialogError(String(err))}finally{setBusy(false)}
  }} submitLabel="Сохранить пример">
  <label>Текст примера<textarea name="text" required minLength={10} maxLength={100000}/></label>
  <CategoryPicker api={api} value={mlLabels} onChange={setMlLabels} canCreate={admin} usage="ml"/>
  <label><input type="checkbox" name="approved"/>Проверено аналитиком</label>
  {dialogError&&<p role="alert" className="error edit-error">{dialogError}</p>}
 </EditorDialog>}
 {page==='ml'&&trainingEditor&&<EditorDialog title="Запустить обучение модели"
  subtitle="Выберите движок, набор данных, категорию и минимальное качество" wide
  busy={busy} onClose={()=>setTrainingEditor(false)} submitLabel="Запустить обучение"
  onSubmit={async(e:FormEvent<HTMLFormElement>)=>{
   const f=new FormData(e.currentTarget);
   setBusy(true);setDialogError('');
   try{
    const job=await api('ml/train',json({
     name:f.get('name'),min_f1:Number(f.get('min_f1')),
     engine:f.get('engine'),category_id:f.get('category_id')||null,
     dataset_id:f.get('dataset_id')||null,
    }));
    setResult({name:'Обучение поставлено в очередь',job_id:job.id,status:job.status});
    setTrainingEditor(false);await load();
   }catch(err){setDialogError(String(err))}finally{setBusy(false)}
  }}>
  <label>Название версии<input name="name" required maxLength={100}/></label>
  <MLTrainingOptions api={api} disabled={busy}/>
  <label>Минимальный F1<input type="number" name="min_f1" min={.5} max={1} step={.01} defaultValue={.7} required/></label>
  {dialogError&&<p role="alert" className="error edit-error">{dialogError}</p>}
 </EditorDialog>}
 {result&&<section><header><h2>{result.name||'Результат'}</h2><button onClick={()=>setResult(null)}>Скрыть</button></header>{page==='references'&&result.text!==undefined?<><pre className="mail-text">{result.text}</pre><h3>Совпадения в инцидентах</h3><Table rows={result.matches||[]} columns={ [['subject','Письмо'],['created_at','Дата'],['confidence','Сходство'],['excerpt','Фрагмент']]} onOpen={r=>{location.href=`?page=incidents&id=${encodeURIComponent(r.id)}`}}/></>:<Value value={result}/>}</section>}
 </div>
}
