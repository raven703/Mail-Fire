import {useEffect,useState,type FormEvent} from 'react';
import type {API,Row} from './components';

type Config={
 enabled:boolean,provider:'local'|'openai',base_url:string,model:string,
 routing:'uncertain'|'selected'|'both',categories:string[],min_confidence:number,
 timeout_seconds:number,max_chars:number,allow_external_content:boolean,api_key_env:string,
};

export function LLMSettings({api}:{api:API}){
 const [config,setConfig]=useState<Config|null>(null);
 const [categories,setCategories]=useState<Row[]>([]);
 const [error,setError]=useState(''),[saved,setSaved]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{
  void Promise.all([api('llm/settings'),api('categories')]).then(([c,d])=>{
   setConfig(c);setCategories((d.items||[]).filter((x:Row)=>x.active));
  }).catch(e=>setError(String(e)));
 },[]);
 const change=(patch:Partial<Config>)=>setConfig(old=>old?{...old,...patch}:old);
 const save=(e:FormEvent<HTMLFormElement>)=>{
  e.preventDefault();if(!config)return;
  setBusy(true);setError('');setSaved('');
  const {api_key_env,...payload}=config;
  void api('llm/settings',{method:'PUT',
   headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
   .then((v:Config)=>{setConfig(v);setSaved('Настройки сохранены')})
   .catch(e=>setError(String(e))).finally(()=>setBusy(false));
 };
 if(!config)return <p>{error||'Загрузка LLM-настроек…'}</p>;
 return <section className="settings-summary"><h3>LLM-анализ содержимого писем</h3>
  <p className="muted">Отключён по умолчанию. Локальный GGUF или внешний OpenAI-совместимый API. Разрешение на внешнюю передачу задаётся отдельно.</p>
  <form className="edit-form-grid" onSubmit={save}>
   <label><input type="checkbox" checked={config.enabled} onChange={e=>change({enabled:e.target.checked})}/>Включить LLM-анализ</label>
   <label>Провайдер<select value={config.provider} onChange={e=>change({provider:e.target.value as Config['provider'],allow_external_content:false})}>
    <option value="local">Локальная GGUF / llama.cpp</option>
    <option value="openai">Внешний OpenAI-совместимый API</option>
   </select></label>
   {config.provider==='openai'?
    <label>Base URL (HTTPS)<input type="url" value={config.base_url} required onChange={e=>change({base_url:e.target.value})} placeholder="https://llm.example.com/v1"/></label>:
    <p className="muted">Поместите веса в data/models/llm/model.gguf, затем запустите профиль compose.llm.yaml. URL: http://llm:8080/v1</p>}
   <label>Model ID<input value={config.model} maxLength={160} required onChange={e=>change({model:e.target.value})}/></label>
   {config.provider==='openai'&&<>
    <label><input type="checkbox" checked={config.allow_external_content} onChange={e=>change({allow_external_content:e.target.checked})}/>Я разрешаю передачу текста писем и вложений внешнему API (возможны ПДн и конфиденциальные данные)</label>
    <p className="muted">API-ключ не хранится в БД. Установите {config.api_key_env} в env_file worker.</p>
   </>}
   <label>Маршрутизация<select value={config.routing} onChange={e=>change({routing:e.target.value as Config['routing']})}>
    <option value="uncertain">Только неоднозначные ML-находки</option>
    <option value="selected">Всегда проверять выбранные категории</option>
    <option value="both">Неоднозначные и выбранные категории</option>
   </select></label>
   {config.routing!=='uncertain'&&<fieldset><legend>Категории для обязательной проверки</legend>
    <div className="category-options">
     {categories.map(c=><label key={c.id}><input type="checkbox" checked={config.categories.includes(c.id)}
      onChange={e=>change({categories:e.target.checked?[...config.categories,c.id]:config.categories.filter(id=>id!==c.id)})}/>{c.name}</label>)}
    </div>
   </fieldset>}
   <label>Минимальная уверенность<input type="number" min={0} max={1} step={.01} value={config.min_confidence} onChange={e=>change({min_confidence:Number(e.target.value)})}/></label>
   <label>Таймаут на письмо, секунд<input type="number" min={2} max={120} value={config.timeout_seconds} onChange={e=>change({timeout_seconds:Number(e.target.value)})}/></label>
   <label>Максимум символов на запрос<input type="number" min={200} max={20000} value={config.max_chars} onChange={e=>change({max_chars:Number(e.target.value)})}/></label>
   <button className="primary" disabled={busy}>{busy?'Сохранение…':'Сохранить настройки LLM'}</button>
  </form>
  {error&&<p className="error" role="alert">{error}</p>}
  {saved&&<p role="status">{saved}</p>}
 </section>;
}
