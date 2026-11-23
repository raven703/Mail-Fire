import {useEffect,useState} from 'react';
import {EditorDialog} from './EditorDialog';
import {Evidence} from './Evidence';
import {type Row} from './components';

const textPreview = (file:Row)=>/\.(txt|csv|json|xml|eml|msg|html?|svg)$/i.test(file.name||'')||/^(text\/|application\/(json|xml)|image\/svg)/i.test(file.mime||'');
const fileSize = (size:number)=>size<1048576?`${Math.ceil(size/1024).toLocaleString('ru-RU')} КБ`:`${(size/1048576).toLocaleString('ru-RU',{maximumFractionDigits:1})} МБ`;

function Viewer({file}:{file:Row}){
 const [tab,setTab]=useState('Оригинал'),[meta,setMeta]=useState<Row>({}),[page,setPage]=useState(1),[scale,setScale]=useState(1),[highlight,setHighlight]=useState(false),[result,setResult]=useState<Row>({}),[error,setError]=useState(''),[loading,setLoading]=useState(false);
 const root=`/api/attachments/${encodeURIComponent(file.id)}`;
 useEffect(()=>{const controller=new AbortController();fetch(root+'/viewer',{signal:controller.signal,cache:'no-store'}).then(async r=>{if(!r.ok)throw new Error('Нет доступа к данным просмотра');return r.json()}).then(setMeta).catch(e=>{if(e.name!=='AbortError')setError(e.message)});return ()=>controller.abort()},[root]);
 useEffect(()=>{if(tab!=='Оригинал'||textPreview(file))return;const controller=new AbortController();setLoading(true);setError('');setResult({});fetch(`${root}/page?page=${page}&scale=${scale}&highlight=${highlight}`,{signal:controller.signal,cache:'no-store'}).then(async r=>{if(!r.ok){const e=await r.json();throw new Error(e.detail||'Просмотр недоступен')}return r.json()}).then(setResult).catch(e=>{if(e.name!=='AbortError')setError(e.message)}).finally(()=>{if(!controller.signal.aborted)setLoading(false)});return ()=>controller.abort()},[root,page,scale,highlight,tab]);
 return <div className="document-viewer"><p className="muted">{file.mime} · {result.pages?`${result.pages} стр. · `:''}{fileSize(Number(meta.size||file.size||0))}</p>
 <nav className="tabs">{['Оригинал','Распознанный текст','Результаты DLP'].map(t=><button type="button" key={t} className={tab===t?'selected':''} onClick={()=>setTab(t)}>{t}</button>)}</nav>
 {tab==='Оригинал'&&textPreview(file)?<><p className="muted">Безопасное текстовое представление. HTML, скрипты и внешние ресурсы не исполняются.</p><dl>{meta.mail&&<><dt>Тема</dt><dd>{meta.mail.subject}</dd><dt>Отправитель</dt><dd>{meta.mail.sender}</dd><dt>Получатели</dt><dd>{meta.mail.recipients?.join(', ')}</dd></>}</dl><pre className="mail-text">{meta.mail?.text||meta.text||'Сохранённый текст отсутствует'}</pre></>:tab==='Оригинал'&&<><div className="actions viewer-toolbar"><button type="button" aria-label="Предыдущая страница" disabled={page===1||loading} onClick={()=>setPage(p=>p-1)}>←</button><span>Страница {page} / {result.pages||'—'}</span><button type="button" aria-label="Следующая страница" disabled={!result.pages||page>=result.pages||loading} onClick={()=>setPage(p=>p+1)}>→</button><label>Масштаб <select value={scale} onChange={e=>setScale(Number(e.target.value))}>{[0.5,1,1.5,2].map(n=><option key={n} value={n}>{n*100}%</option>)}</select></label><label className="viewer-highlight"><input type="checkbox" checked={highlight} onChange={e=>setHighlight(e.target.checked)}/>Подсветить DLP в PDF</label></div>{loading&&<p role="status">Подготовка страницы…</p>}{error&&<p role="alert">{error}</p>}{result.image&&<div className="document-page"><img src={result.image} alt={`Страница ${page}: ${file.name}`}/></div>}<p className="muted">Пассивное изображение страницы. Скрипты, макросы и ссылки не исполняются. Подсветка PDF доступна для текстовых совпадений; координаты OCR старых сканов не сохранены.</p></>}
 {tab==='Распознанный текст'&&<><p className="muted">Сохранённый результат парсера; OCR повторно не запускается.</p><pre className="mail-text">{meta.text||'Сохранённого текста нет. Для его получения требуется отдельная повторная обработка письма.'}</pre></>}
 {tab==='Результаты DLP'&&<><p className="muted">Совпадения из сохранённого анализа, относящиеся к этому вложению.</p><Evidence rows={meta.findings||[]} allowed={true}/></>}
 </div>;
}

export function MessageAttachments({items,allowOriginals}:{items:Row[],allowOriginals:boolean}){
 const [selected,setSelected]=useState<Row|null>(null);
 return <div className="message-attachments">
  {!items.length&&<p className="muted">У письма нет вложений.</p>}
  {items.map(f=><div className="policy-row" key={f.id}>
   <div className="policy-info">
    <strong>{f.name||'Вложение'}</strong>
    <p>{f.mime||'Неизвестный формат'} · {Number(f.size||0).toLocaleString('ru-RU')} байт · {f.status||'—'}</p>
   </div>
   <div className="actions">
    {allowOriginals&&<button type="button" onClick={()=>setSelected(f)}>Просмотр</button>}
    {allowOriginals&&<a className="action-button" href={`/api/attachments/${encodeURIComponent(f.id)}/original`} download aria-label={`Скачать ${f.name}`} title="Скачать вложение">↓ Скачать</a>}
   </div>
  </div>)}
  {selected&&<EditorDialog title={selected.name||'Просмотр вложения'} subtitle="Локальный просмотр документа без автоматического скачивания." wide
   onClose={()=>setSelected(null)} footerNote="Для форматов без безопасного просмотра отображается только извлечённый текст.">
   <Viewer key={selected.id} file={selected}/>
   <div className="actions"><a className="action-button" href={`/api/attachments/${encodeURIComponent(selected.id)}/original`} download>↓ Скачать вложение</a></div>
  </EditorDialog>}
 </div>;
}
