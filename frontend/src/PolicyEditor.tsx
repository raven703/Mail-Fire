import {useEffect,useRef,useState,type FormEvent} from 'react';
import {createPortal} from 'react-dom';
import {CategoryPicker} from './CategoryPicker';
import {json,type API,type Row} from './components';

const directions:[string,string][]=[
 ['INBOUND','Входящая'],['OUTBOUND','Исходящая'],
 ['INTERNAL','Внутренняя'],['UNKNOWN','Неизвестная'],
];

export function PolicyEditor({row,api,saved,onClose}:{row?:Row,api:API,saved:()=>void,onClose:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null);
 const nameField=useRef<HTMLInputElement>(null);
 const [error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [categories,setCategories]=useState<string[]>(row?.conditions?.categories||[]);
 const [direction,setDirection]=useState<string[]>(row?.conditions?.direction||[]);
 const [categoryMatch,setCategoryMatch]=useState<'any'|'all'>(row?.conditions?.category_match==='all'?'all':'any');
 const [risk,setRisk]=useState<number>(row?.conditions?.min_risk??40);
 const [minCount,setMinCount]=useState<number>(row?.conditions?.min_count??1);
 const [shadow,setShadow]=useState<boolean>(row?.shadow??false);

 useEffect(()=>{
  const current=dialog.current;
  if(!current)return;
  current.showModal();
  const previous=document.body.style.overflow;
  document.body.style.overflow='hidden';
  nameField.current?.focus();
  return ()=>{document.body.style.overflow=previous;if(current.open)current.close()};
 },[]);

 const invalidAll=categoryMatch==='all'&&categories.length===0;
 const categoryDescription=categories.length===0?'всех доступных категорий':
  categoryMatch==='all'? `каждой из ${categories.length} выбранных категорий`:
  `любой из ${categories.length} выбранных категорий`;
 const matchSummary=invalidAll?
  'Выберите категории для режима «Все категории».':
  `Инцидент создаётся, если обнаружено не менее ${minCount} ${minCount===1?'срабатывания':'срабатываний'} с риском от ${risk} по ${categoryDescription}.`;

 const save=(e:FormEvent<HTMLFormElement>)=>{
  e.preventDefault();
  if(invalidAll){setError('Для режима «Все категории» выберите хотя бы одну категорию');return}
  const f=new FormData(e.currentTarget);
  const senders=String(f.get('senders')||'').split(',').map(s=>s.trim()).filter(Boolean);
  setBusy(true);setError('');
  void api('workspace/policies'+(row?'/'+row.id:''),
   json({name:f.get('name'),enabled:f.get('enabled')==='on',shadow,
    priority:Number(f.get('priority')),min_risk:risk,min_count:minCount,
    category_match:categoryMatch,categories,senders,direction},row?'PUT':'POST'))
   .then(saved).catch(e=>setError(String(e))).finally(()=>setBusy(false));
 };
 return createPortal(<dialog ref={dialog} className="policy-modal"
  aria-labelledby="policy-modal-title" aria-describedby="policy-modal-subtitle"
  onCancel={e=>{e.preventDefault();if(!busy)onClose()}}>
  <form className="policy-modal-layout" onSubmit={save}>
   <header className="policy-modal-header">
    <div className="policy-modal-heading">
     <h2 id="policy-modal-title">{row?'Изменить политику':'Новая политика'}</h2>
     <p id="policy-modal-subtitle">Условия создания DLP-инцидента</p>
    </div>
    <button type="button" className="policy-modal-close" onClick={onClose} disabled={busy}
     aria-label="Закрыть окно редактирования политики" title="Закрыть (Esc)">×</button>
   </header>
   <div className="policy-modal-body">
    <label className="policy-modal-name">Название политики
     <input ref={nameField} name="name" required maxLength={200}
      placeholder="Например, Контроль исходящих персональных данных" defaultValue={row?.name||''}/>
    </label>
    <div className="policy-modal-numbers">
     <label>Минимальный риск
      <input name="min_risk" type="number" min={0} max={100} required value={risk}
       onChange={e=>setRisk(Number(e.target.value))}/>
     </label>
     <label>Минимум срабатываний
      <input name="min_count" type="number" min={1} max={1000} required value={minCount}
       onChange={e=>setMinCount(Number(e.target.value))}/>
     </label>
     <label>Приоритет
      <input name="priority" type="number" min={0} max={10000} required
       defaultValue={row?.priority??10}/>
     </label>
    </div>
    <div className="policy-modal-field-help">
     Риск проверяется <strong>у каждого отдельного срабатывания</strong>.
     Минимум — это <strong>общее число срабатываний</strong>, а не число категорий.
     Приоритет задаёт порядок проверки политик, но не останавливает остальные.
    </div>
    <CategoryPicker api={api} value={categories} onChange={setCategories} canCreate usage="policy"/>
    <fieldset className="policy-category-match">
     <legend>Как объединять выбранные категории?</legend>
     <label><input type="radio" name="category_match" value="any"
      checked={categoryMatch==='any'} onChange={()=>setCategoryMatch('any')}/>
      <span><strong>Любая категория (ИЛИ)</strong><small>Хватит срабатываний в одной из выбранных категорий</small></span>
     </label>
     <label><input type="radio" name="category_match" value="all"
      checked={categoryMatch==='all'} onChange={()=>setCategoryMatch('all')}/>
      <span><strong>Все категории (И)</strong><small>В каждой выбранной категории должно быть хотя бы одно подходящее срабатывание</small></span>
     </label>
    </fieldset>
    <div className={'policy-modal-summary'+(invalidAll?' is-invalid':'')} role="status" aria-live="polite">
     <strong>Когда сработает политика?</strong>
     <p>{matchSummary}</p>
     {categories.length>0&&categoryMatch==='all'&&<p>Даже при минимуме 1 требуется минимум по одному совпадению в каждой из {categories.length} категорий.</p>}
     <small>{shadow?'Теневой режим: инциденты не создаются.':'При выполнении условий создаётся инцидент, почта не блокируется.'}</small>
    </div>
    <details className="policy-modal-advanced">
     <summary>Дополнительные условия и настройки</summary>
     <fieldset className="policy-modal-directions">
      <legend>Направления доставки (пусто — все)</legend>
      <div>{directions.map(([id,name])=><label key={id}>
       <input type="checkbox" checked={direction.includes(id)}
        onChange={e=>setDirection(e.target.checked?[...direction,id]:direction.filter(v=>v!==id))}/>{name}
      </label>)}</div>
     </fieldset>
     <label>Отправители (точные email через запятую)
      <input name="senders" defaultValue={row?.conditions?.senders?.join(', ')||''}
       placeholder="user@company.ru, analyst@company.ru"/>
     </label>
     <label><input type="checkbox" name="enabled" defaultChecked={row?.enabled??true}/> Политика включена</label>
     <label><input type="checkbox" checked={shadow} onChange={e=>setShadow(e.target.checked)}/> Теневой режим (без создания инцидентов)</label>
    </details>
    {error&&<p role="alert" className="error">{error}</p>}
   </div>
   <footer className="policy-modal-footer">
    <span>Esc — закрыть без сохранения</span>
    <div>
     <button type="button" onClick={onClose} disabled={busy}>Отмена</button>
     <button type="submit" className="primary" disabled={busy||invalidAll}>
      {busy?'Сохранение…':'Сохранить политику'}
     </button>
    </div>
   </footer>
  </form>
 </dialog>,document.body);
}
