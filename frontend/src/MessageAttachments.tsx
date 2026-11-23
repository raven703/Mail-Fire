import {useState} from 'react';
import {EditorDialog} from './EditorDialog';
import {type Row} from './components';

const previewable = new Set(['application/pdf','image/png','image/jpeg','image/gif','image/webp']);

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
    {allowOriginals&&<a href={`/api/attachments/${encodeURIComponent(f.id)}/original`} download aria-label={`Скачать ${f.name}`} title="Скачать вложение">↓ Скачать</a>}
   </div>
  </div>)}
  {selected&&<EditorDialog title={selected.name||'Просмотр вложения'} subtitle="Только предварительный просмотр. Активное содержимое не исполняется." wide
   onClose={()=>setSelected(null)} footerNote="Для форматов без безопасного просмотра отображается только извлечённый текст.">
   {previewable.has(String(selected.mime||'').split(';')[0].toLowerCase())?
    String(selected.mime).toLowerCase().startsWith('image/')?
     <img className="attachment-preview-image" src={`/api/attachments/${encodeURIComponent(selected.id)}/preview`} alt={selected.name||'Изображение'}/>:
     <iframe className="attachment-preview-frame" title={selected.name||'PDF'} sandbox="" referrerPolicy="no-referrer"
       src={`/api/attachments/${encodeURIComponent(selected.id)}/preview`}/>:
    <pre className="mail-text">{selected.text||'Предварительный просмотр для этого формата недоступен.'}</pre>}
   <div className="actions"><a href={`/api/attachments/${encodeURIComponent(selected.id)}/original`} download>↓ Скачать вложение</a></div>
  </EditorDialog>}
 </div>;
}
