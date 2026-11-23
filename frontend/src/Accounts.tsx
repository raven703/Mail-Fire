import {useEffect,useState,type FormEvent} from 'react';
import {Table,json,type API,type Row} from './components';
import {EditorDialog} from './EditorDialog';

export function Accounts({api}:{api:API}){
 const [rows,setRows]=useState<Row[]>([]);
 const [editing,setEditing]=useState<Row|null>(null);
 const [error,setError]=useState(''),[dialogError,setDialogError]=useState('');
 const [busy,setBusy]=useState(false);
 async function load(){
  try{setRows((await api('accounts')).items)}catch(e){setError(String(e))}
 }
 useEffect(()=>{void load()},[]);
 const open=(row:Row)=>{setDialogError('');setEditing(row)};
 const save=async(event:FormEvent<HTMLFormElement>)=>{
  const current=editing;
  if(!current)return;
  const f=new FormData(event.currentTarget);
  setBusy(true);setDialogError('');
  try{
   await api('accounts'+(current.id?'/'+current.id:''),json({
    username:f.get('username'),role:f.get('role'),
    enabled:f.get('enabled')==='on',originals:f.get('originals')==='on',
    ...(f.get('password')?{password:f.get('password')}:{})
   },current.id?'PUT':'POST'));
   setEditing(null);
   await load();
  }catch(e){setDialogError(String(e))}
  finally{setBusy(false)}
 };
 return <section>
  <header><h2>Пользователи и права</h2>
   <button className="primary" onClick={()=>open({role:'analyst',enabled:true,originals:true})}>＋ Добавить пользователя</button>
  </header>
  {error&&<p role="alert" className="error">{error}</p>}
  <p className="muted">Администратор управляет доступом. Удаление закрывает сеансы и сохраняет историю расследований. Подключение Active Directory предусмотрено отдельным провайдером аутентификации.</p>
  <Table rows={rows} columns={[
   ['username','Имя'],['role','Роль'],['enabled','Доступ'],
   ['originals','Оригиналы и содержимое']
  ]} onOpen={open}/>
  {editing?.id&&<div className="actions"><button disabled={busy} onClick={()=>{if(confirm(`Отозвать доступ пользователя ${editing.username}?`))void (async()=>{setBusy(true);try{await api('accounts/'+editing.id,{method:'DELETE'});setEditing(null);await load()}catch(e){setDialogError(String(e))}finally{setBusy(false)}})()}}>Удалить пользователя (отозвать доступ)</button></div>}
  {editing&&<EditorDialog title={editing.id?'Редактировать пользователя':'Новый пользователь'}
   subtitle="Учётная запись, роль и доступ к чувствительным данным"
   busy={busy} onClose={()=>setEditing(null)} onSubmit={save} submitLabel="Сохранить пользователя">
   <div className="edit-form-grid">
    <label>Имя пользователя
     <input name="username" required minLength={3} maxLength={100} defaultValue={editing.username||''}/>
    </label>
    <label>Роль
     <select name="role" defaultValue={editing.role}>
      <option value="observer">Наблюдатель</option>
      <option value="analyst">Аналитик</option>
      <option value="admin">Администратор</option>
     </select>
    </label>
   </div>
   <label>Новый пароль
    <input name="password" type="password" autoComplete="new-password"
     minLength={12} maxLength={128} required={!editing.id}/>
   </label>
   <label><input type="checkbox" name="enabled" defaultChecked={editing.enabled}/>Доступ включён</label>
   <label><input type="checkbox" name="originals" defaultChecked={editing.originals}/>Просмотр содержимого и скачивание оригиналов</label>
   <p className="edit-intro">При изменении пользователя его действующие сессии отзываются. Для отзыва доступа отключите пользователя.</p>
   {dialogError&&<p role="alert" className="error edit-error">{dialogError}</p>}
  </EditorDialog>}
 </section>;
}
