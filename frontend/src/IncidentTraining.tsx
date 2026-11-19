import {useState} from 'react';
import {CategoryPicker} from './CategoryPicker';
import {EditorDialog} from './EditorDialog';
import {json,type API,type Row} from './components';

export function IncidentTraining({incident,api,admin}:{incident:Row,api:API,admin:boolean}){
 const [open,setOpen]=useState(false),[labels,setLabels]=useState<string[]>([]);
 const [approved,setApproved]=useState(false),[status,setStatus]=useState('');
 const [error,setError]=useState(''),[busy,setBusy]=useState(false);
 const begin=()=>{
  setLabels(incident.status==='FALSE_POSITIVE'?['NORMAL']:
   [...new Set<string>((incident.findings||[]).map((f:Row)=>String(f.category)))].slice(0,20));
  setApproved(false);setError('');setOpen(true);
 };
 const save=()=>{
  setBusy(true);setError('');
  void api('ml/incidents/'+incident.id+'/example',json({labels,approved}))
   .then(()=>{setStatus('Пример сохранён для следующего обучения');setOpen(false)})
   .catch(e=>setError(String(e)))
   .finally(()=>setBusy(false));
 };
 return <section className="incident-training">
  <h3>Обучение на решении аналитика</h3>
  <p className="muted">Добавление в обучение — отдельное осознанное действие. Подтверждение инцидента не меняет модель автоматически.</p>
  <button type="button" onClick={begin}>＋ Добавить в обучающую выборку</button>
  {status&&<p role="status">{status}</p>}
  {open&&<EditorDialog title="Добавить пример из инцидента"
   subtitle="Проверьте категории и явным образом подтвердите разметку" wide
   busy={busy} onClose={()=>setOpen(false)} onSubmit={save}
   submitDisabled={!labels.length} submitLabel="Сохранить пример">
   <CategoryPicker api={api} value={labels} onChange={setLabels} canCreate={admin} usage="ml"/>
   <label><input type="checkbox" checked={approved} onChange={e=>setApproved(e.target.checked)}/>
    Разметка проверена аналитиком</label>
   <p className="edit-intro">Для ложного срабатывания выберите категорию «Безопасный материал». Сохраняется извлечённый текст письма.</p>
   {error&&<p role="alert" className="error edit-error">{error}</p>}
  </EditorDialog>}
 </section>;
}
