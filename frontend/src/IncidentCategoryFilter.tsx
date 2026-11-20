import {useEffect,useState} from 'react';
import type {API} from './components';
import './incident-category-filter.css';

export function IncidentCategoryFilter({api,value,onChange}:{api:API,value:string,onChange:(value:string)=>void}){
 const [options,setOptions]=useState<string[]>([]),[open,setOpen]=useState(false),[error,setError]=useState('');
 useEffect(()=>{let active=true;void api('catalog/policies?include_archived=true').then(data=>{if(active)setOptions([...new Set<string>((data.items||[]).map((item:{name:string})=>item.name))].sort((a,b)=>a.localeCompare(b,'ru')))}).catch(()=>{if(active)setError('Не удалось загрузить список. Можно ввести название вручную.')});return()=>{active=false}},[]);
 const filtered=options.filter(name=>name.toLocaleLowerCase().includes(value.toLocaleLowerCase()));
 return <label className="incident-category-filter">Категория
  <div className="incident-category-input"><input value={value} placeholder="Все категории" role="combobox" aria-label="Категория инцидента" aria-expanded={open} aria-controls="incident-category-options" autoComplete="off" onFocus={()=>setOpen(true)} onClick={()=>setOpen(true)} onKeyDown={e=>{if(e.key==='Escape')setOpen(false);if(e.key==='ArrowDown'){e.preventDefault();setOpen(true);document.querySelector<HTMLButtonElement>('#incident-category-options button')?.focus()}}} onBlur={e=>{if(!e.currentTarget.parentElement?.parentElement?.contains(e.relatedTarget as Node))setOpen(false)}} onChange={e=>{onChange(e.target.value);setOpen(true)}}/><button type="button" aria-label="Показать категории" onClick={()=>setOpen(!open)}>⌄</button></div>
  {open&&<div id="incident-category-options" className="incident-category-options" role="listbox" aria-label="Категории для фильтрации" onBlur={e=>{if(!e.currentTarget.parentElement?.contains(e.relatedTarget as Node))setOpen(false)}}>
   <button type="button" role="option" aria-selected={!value} onMouseDown={e=>e.preventDefault()} onClick={()=>{onChange('');setOpen(false)}}>Все категории</button>
   {filtered.map(name=><button type="button" role="option" aria-selected={value===name} key={name} onMouseDown={e=>e.preventDefault()} onClick={()=>{onChange(name);setOpen(false)}}>{name}</button>)}
   {error&&<small>{error}</small>}{!error&&!filtered.length&&<small>Совпадений нет. Используется введённый текст.</small>}
  </div>}
 </label>;
}