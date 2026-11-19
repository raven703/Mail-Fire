import {useState,type FormEvent} from 'react';
import {EditorDialog} from './EditorDialog';
import {json,labels,type API,type Row} from './components';

const states=['NEW','ASSIGNED','REVIEW','CONFIRMED','FALSE_POSITIVE','CLOSED','REOPENED'];

export function IncidentActions({incident,analysts,api,onSaved}:{
 incident:Row;analysts:Row[];api:API;onSaved:()=>void;
}){
 const [editor,setEditor]=useState<'assignee'|'decision'|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const open=(mode:'assignee'|'decision')=>{setError('');setEditor(mode)};
 const save=async(event:FormEvent<HTMLFormElement>)=>{
  const form=new FormData(event.currentTarget);
  setBusy(true);setError('');
  try{
   if(editor==='assignee'){
    await api('workspace/incidents/'+incident.id+'/assignee',
     json({assignee:form.get('assignee')||null},'PUT'));
   }else{
    await api('incidents/'+incident.id,
     json({status:form.get('status'),comment:form.get('comment')||''},'PATCH'));
   }
   setEditor(null);
   onSaved();
  }catch(e){setError(String(e))}
  finally{setBusy(false)}
 };
 return <section className="incident-actions-panel">
  <header><div><h3>Решение аналитика</h3>
   <p className="muted">Статус: {labels[incident.status]||incident.status} · Аналитик: {incident.analyst||'Не назначен'}</p></div>
   <div className="actions">
    <button type="button" onClick={()=>open('assignee')}>Назначить аналитика</button>
    <button type="button" className="primary" onClick={()=>open('decision')}>Изменить решение</button>
   </div>
  </header>
  {editor&&<EditorDialog title={editor==='assignee'?'Назначить аналитика':'Изменить решение по инциденту'}
    subtitle={incident.subject||incident.category||'Инцидент'}
    busy={busy} onClose={()=>setEditor(null)} onSubmit={save}
    submitLabel={editor==='assignee'?'Сохранить назначение':'Сохранить решение'}>
   {editor==='assignee'?
    <label>Ответственный аналитик
     <select name="assignee" defaultValue={incident.assignee||''}>
      <option value="">Не назначен</option>
      {analysts.map(a=><option key={a.id} value={a.id}>{a.username}</option>)}
     </select>
    </label>:
    <>
     <label>Статус расследования
      <select name="status" defaultValue={incident.status}>
       {states.map(state=><option key={state} value={state}>{labels[state]}</option>)}
      </select>
     </label>
     <label>Комментарий
      <textarea name="comment" maxLength={10000} placeholder="Обоснование решения (необязательно)"/>
     </label>
    </>}
   {error&&<p role="alert" className="error edit-error">{error}</p>}
  </EditorDialog>}
 </section>;
}
