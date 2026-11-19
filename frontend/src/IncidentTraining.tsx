import {useState} from 'react';
import {CategoryPicker} from './CategoryPicker';
import {json,type API,type Row} from './components';

export function IncidentTraining({incident,api,admin}:{incident:Row,api:API,admin:boolean}){
 const [open,setOpen]=useState(false),[labels,setLabels]=useState<string[]>([]),[approved,setApproved]=useState(false),
 [status,setStatus]=useState(''),[busy,setBusy]=useState(false);
 return <section className="incident-training">
  <h3>Обучение на решении аналитика</h3>
  <p className="muted">Добавление в обучение — отдельное осознанное действие. Подтверждение инцидента не меняет модель автоматически.</p>
  {!open?<button onClick={()=>{setLabels(incident.status==='FALSE_POSITIVE'?['NORMAL']:
    [...new Set<string>((incident.findings||[]).map((f:Row)=>String(f.category)))].slice(0,20));setOpen(true)}}>＋ Добавить в обучающую выборку</button>:
  <div><CategoryPicker api={api} value={labels} onChange={setLabels} canCreate={admin} usage="ml"/>
   <label><input type="checkbox" checked={approved} onChange={e=>setApproved(e.target.checked)}/>Разметка проверена аналитиком</label>
   <p className="muted">Для ложного срабатывания выберите «Безопасный материал». Сохраняется извлечённый текст письма.</p>
   <div className="actions"><button disabled={busy||!labels.length} onClick={()=>{setBusy(true);setStatus('');
    void api('ml/incidents/'+incident.id+'/example',json({labels,approved})).then(()=>{setStatus('Пример сохранён для следующего обучения');setOpen(false)}).catch(e=>setStatus(String(e))).finally(()=>setBusy(false))}}>Сохранить пример</button>
    <button onClick={()=>setOpen(false)}>Отмена</button></div>
  </div>}
  {status&&<p role="status">{status}</p>}
 </section>;
}
