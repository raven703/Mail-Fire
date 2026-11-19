import {useState} from 'react';
import {EditorDialog} from './EditorDialog';
import {json,type API,type Row} from './components';

export function RulepackTransfer({api,onSaved}:{api:API;onSaved:()=>void|Promise<void>}){
 const [open,setOpen]=useState(false),[pack,setPack]=useState<Row|null>(null),[plan,setPlan]=useState<Row|null>(null);
 const [update,setUpdate]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const exportJSON=async()=>{setError('');setBusy(true);try{
  const data=await api('rulepacks/export');const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='mailfire-rules.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }catch(e){setError(String(e))}finally{setBusy(false)}};
 const submit=async()=>{if(!pack)return;setBusy(true);setError('');try{
  const response=await api('rulepacks/'+(plan?'apply':'preview'),json({pack,update_existing:update}));
  if(plan){await onSaved();setOpen(false)}else setPlan(response);
 }catch(e){setError(String(e));setPlan(null)}finally{setBusy(false)}};
 return <><div className="actions"><button disabled={busy} onClick={()=>void exportJSON()}>Экспортировать JSON</button>
 <button onClick={()=>{setPack(null);setPlan(null);setUpdate(false);setError('');setOpen(true)}}>Импортировать JSON</button></div>
 {!open&&error&&<p role="alert" className="error">{error}</p>}
 {open&&<EditorDialog title="Импортировать JSON" subtitle="Категории и DLP-политики: предварительный просмотр перед применением"
 busy={busy} onClose={()=>setOpen(false)} onSubmit={()=>void submit()} submitDisabled={!pack}
 submitLabel={plan?'Применить изменения':'Предварительный просмотр'} wide>
 <label>JSON-файл<input type="file" accept=".json,application/json" disabled={busy} onChange={async e=>{
  setPlan(null);setPack(null);setError('');const file=e.target.files?.[0];if(!file)return;
  try{if(file.size>1024*1024)throw Error('Максимум 1 МиБ');setPack(JSON.parse(await file.text()))}catch(err){setError(String(err))}
 }}/></label>
 <label><input type="checkbox" checked={update} disabled={busy} onChange={e=>{setUpdate(e.target.checked);setPlan(null)}}/>Обновить существующие элементы этого набора</label>
 <p className="edit-intro">Существующие элементы по умолчанию пропускаются. Чужие и системные категории защищены. Импортируемые политики выключаются; включите их отдельно после проверки. Элементы вне набора не удаляются.</p>
 {plan&&<><h3>Предварительный просмотр изменений</h3><pre className="mail-text">{JSON.stringify(plan.changes,null,2)}</pre></>}
 {error&&<p role="alert" className="error edit-error">{error}</p>}
 </EditorDialog>}</>;
}
