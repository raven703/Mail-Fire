import {useEffect,useState,type FormEvent} from 'react';
import {EditorDialog} from './EditorDialog';
import {Value,Table} from './components';
import {Accounts} from './Accounts';
import {LLMSettings} from './LLMSettings';
type API=(path:string,init?:RequestInit)=>Promise<any>;
export function Operations({page:section,api}:{page:string,api:API}){
 const [settingTab,setSettingTab]=useState('integrations');
 const page=section==='settings'?settingTab:section==='system'?'diagnostics':section;
 const [data,setData]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[result,setResult]=useState<any>(null);
 const [editor,setEditor]=useState<'retention'|'integrations'|null>(null),[editorError,setEditorError]=useState('');
 const paths:Record<string,string>={references:'references',ml:'ml/models',retention:'retention',integrations:'integrations',diagnostics:'monitoring/queues'};
 async function run(work:()=>Promise<any>){setBusy(true);setError('');try{await work()}catch(e){setError(String(e))}finally{setBusy(false)}}
  async function load(){if(page!=='accounts'&&page!=='llm')setData(await api(paths[page]))}
 useEffect(()=>{setData(null);setResult(null);setEditor(null);void run(load)},[page]);
 const json=(body:any,method='POST')=>({method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const saveSettings=async(event:FormEvent<HTMLFormElement>)=>{
  const form=new FormData(event.currentTarget);
  setBusy(true);setEditorError('');
  try{
   if(editor==='retention'){
    const payload:any={paused:form.get('paused')==='on'};
    Object.keys(data).filter(k=>k.endsWith('_days')).forEach(k=>payload[k]=Number(form.get(k)));
    setData(await api('retention',json(payload,'PUT')));
   }else if(editor==='integrations'){
    const destinations=String(form.get('urls')||'').split('\n').map(v=>v.trim()).filter(Boolean)
     .map(url=>({url,enabled:true}));
    setData(await api('integrations',json({destinations},'PUT')));
   }
   setEditor(null);
  }catch(e){setEditorError(String(e))}
  finally{setBusy(false)}
 };
 return <section>{section==='settings'&&<nav className="tabs"><button onClick={()=>setSettingTab('integrations')}>SIEM и уведомления</button><button onClick={()=>setSettingTab('retention')}>Хранение и очистка</button><button onClick={()=>setSettingTab('llm')}>LLM-анализ</button><button onClick={()=>setSettingTab('accounts')}>Пользователи</button></nav>}<header><h3>{{references:'Эталонные документы',ml:'Модели и обучение',retention:'Сроки хранения',integrations:'SIEM и уведомления',diagnostics:'Диагностика обработки',llm:'LLM-анализ'}[page]}</h3></header>{busy&&<p role="status">Загрузка…</p>}{error&&<p role="alert">{error}</p>}
 {page==='accounts'&&<Accounts api={api}/>}{page==='llm'&&<LLMSettings api={api}/>}
 {page==='references'&&<label>Загрузить эталон<input type="file" disabled={busy} onChange={e=>{const file=e.target.files?.[0];if(!file)return;const body=new FormData();body.append('file',file);void run(async()=>{setResult(await api('references',{method:'POST',body}));await load()})}}/></label>}
 {page==='ml'&&<><p>Статус классификатора: {data?.status||'Загрузка'}</p><form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void run(async()=>setResult(await api('ml/examples',json({text:f.get('text'),labels:String(f.get('labels')).split(',').map(s=>s.trim()).filter(Boolean),approved:f.get('approved')==='on'}))))}}><label>Текст примера<textarea name="text" required minLength={10}/></label><label>Категории через запятую<input name="labels" required/></label><label><input type="checkbox" name="approved"/> Проверено аналитиком</label><button disabled={busy}>Добавить пример</button></form><button disabled={busy} onClick={()=>void run(async()=>{setResult(await api('ml/train',json({name:'Модель '+new Date().toISOString(),min_f1:.7})));await load()})}>Обучить на проверенных примерах</button>{data?.items?.map((m:any)=><article key={m.id}><strong>{m.name}</strong><p>{m.active?'Опубликована':m.eligible?'Прошла контроль качества':'Не прошла контроль качества'}</p><button disabled={busy||!m.eligible||m.active} onClick={()=>{if(confirm('Опубликовать выбранную версию?'))void run(async()=>{await api(`ml/models/${m.id}/publish`,json({}));await load()})}}>Опубликовать / откатить</button></article>)}</>}
 {page==='retention'&&data&&<section className="settings-summary">
   <header><h3>Настройки сроков хранения</h3>
    <button className="primary" onClick={()=>{setEditorError('');setEditor('retention')}}>Изменить сроки</button></header>
   <dl className="facts">{Object.entries(data).filter(([key])=>key.endsWith('_days')).map(([key,value])=>
    <div key={key}><dt>{key}</dt><dd>{String(value)} дней</dd></div>)}
    <div><dt>Автоматическая очистка</dt><dd>{data.paused?'Приостановлена':'Включена'}</dd></div>
   </dl>
   <div className="actions">
    <button disabled={busy} onClick={()=>void run(async()=>setResult(await api('retention/cleanup',json({dry_run:true}))))}>Предварительный просмотр</button>
    <button disabled={busy} onClick={()=>{if(confirm('Безвозвратно удалить просроченные данные?'))void run(async()=>setResult(await api('retention/cleanup',json({dry_run:false,confirm:'DELETE_EXPIRED'}))))}}>Очистить просроченные данные</button>
   </div>
   <p className="muted">Фоновая очистка — каждый час, до 100 писем за запуск.</p>
  </section>}
 {page==='integrations'&&data&&<section className="settings-summary">
   <header><h3>SIEM и Webhook</h3>
    <button className="primary" onClick={()=>{setEditorError('');setEditor('integrations')}}>Редактировать назначения</button></header>
   <p className="muted">Настроено назначений: {data.destinations?.length||0}</p>
   <div className="actions"><button disabled={busy} onClick={()=>void run(async()=>setResult(await api('outbox')))}>История доставки</button></div>
  </section>}
 {editor==='retention'&&data&&<EditorDialog title="Изменить сроки хранения"
  subtitle="Сроки в днях и управление фоновой очисткой" busy={busy}
  onClose={()=>setEditor(null)} onSubmit={saveSettings} submitLabel="Сохранить сроки">
  <div className="edit-form-grid">
   {Object.entries(data).filter(([key])=>key.endsWith('_days')).map(([key,value])=>
    <label key={key}>{key} — дней
     <input type="number" min={1} max={36500} name={key} required defaultValue={Number(value)}/>
    </label>)}
  </div>
  <label><input type="checkbox" name="paused" defaultChecked={data.paused}/>Приостановить очистку</label>
  {editorError&&<p role="alert" className="error edit-error">{editorError}</p>}
 </EditorDialog>}
 {editor==='integrations'&&data&&<EditorDialog title="Редактировать SIEM и Webhook"
  subtitle="Разрешённые адреса назначения, по одному на строку" busy={busy}
  onClose={()=>setEditor(null)} onSubmit={saveSettings} submitLabel="Сохранить назначения">
  <label>Адреса SIEM / Webhook
   <textarea name="urls" rows={7} defaultValue={data.destinations?.map((d:any)=>d.url).join('\n')||''}/>
  </label>
  <p className="edit-intro">Поддерживаются http(s)://, syslog:// и cef://. Настройка доступна только администратору.</p>
  {editorError&&<p role="alert" className="error edit-error">{editorError}</p>}
 </EditorDialog>}
 {page==='diagnostics'&&<nav>{['queues','flow','resources','database'].map(name=><button key={name} disabled={busy} onClick={()=>void run(async()=>setData(await api('monitoring/'+name)))}>{({queues:'Очереди',flow:'Почтовый поток',resources:'История ресурсов',database:'PostgreSQL'} as Record<string,string>)[name]}</button>)}</nav>}
  {page==='references'&&<Table rows={data?.items||[]} columns={ [['name','Документ'],['created_at','Дата загрузки']]} onOpen={r=>setResult({name:r.name,text:r.text})}/>}{page==='diagnostics'&&<><p className="muted">Телеметрия maintenance-процесса; показатели отдельных Docker-контейнеров недоступны. Интерфейс не получает Docker Socket.</p><Value value={data}/></>}{result&&<article><header><h3>Результат</h3><button onClick={()=>setResult(null)}>Скрыть</button></header><Value value={result}/></article>}</section>
}