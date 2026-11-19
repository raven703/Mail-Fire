import {useEffect,useId,useRef,type FormEvent,type ReactNode} from 'react';
import {createPortal} from 'react-dom';

/** Shared, accessible modal shell for CREATE and EDIT flows.
 * The dialog has one scrollable body, a pinned action footer, Escape/X/Cancel,
 * native form submission and no outside-click-to-close behavior.
 * Secondary modal dialogs (e.g. nested category picker) are supported.
 */
export function EditorDialog({
 title,subtitle,children,onClose,onSubmit,submitLabel='Сохранить',busy=false,
 submitDisabled=false,footerNote,wide=false
}:{
 title:string;subtitle?:string;children:ReactNode;onClose:()=>void;
 onSubmit?:(event:FormEvent<HTMLFormElement>)=>void;submitLabel?:string;
 busy?:boolean;submitDisabled?:boolean;footerNote?:string;wide?:boolean;
}){
 const ref=useRef<HTMLDialogElement>(null);
 const titleId=useId(),descriptionId=useId();
 useEffect(()=>{
  const dialog=ref.current;
  if(!dialog)return;
  const previous=document.activeElement as HTMLElement|null;
  const priorOverflow=document.body.style.overflow;
  document.body.style.overflow='hidden';
  dialog.showModal();
  dialog.querySelector<HTMLInputElement>('input:not([type="hidden"]):not(:disabled)')?.focus();
  return ()=>{
   document.body.style.overflow=priorOverflow;
   if(dialog.open)dialog.close();
   previous?.focus();
  };
 },[]);
 return createPortal(<dialog ref={ref}
  className={'editor-dialog'+(wide?' editor-dialog-wide':'')}
  aria-labelledby={titleId}
  aria-describedby={subtitle?descriptionId:undefined}
  onCancel={event=>{event.preventDefault();event.stopPropagation();if(!busy)onClose()}}>
  <form className="editor-dialog-layout" onSubmit={event=>{
   event.preventDefault();
   event.stopPropagation();
   if(!busy&&!submitDisabled)onSubmit?.(event);
  }}>
   <header className="editor-dialog-header">
    <div className="editor-dialog-title"><h2 id={titleId}>{title}</h2>
     {subtitle&&<p id={descriptionId}>{subtitle}</p>}</div>
    <button type="button" className="editor-dialog-close" aria-label="Закрыть окно"
     title="Закрыть (Esc)" disabled={busy} onClick={onClose}>×</button>
   </header>
   <div className="editor-dialog-body">{children}</div>
   <footer className="editor-dialog-footer">
    <span className="editor-dialog-note">{footerNote||'Esc — закрыть без сохранения'}</span>
    <div className="editor-dialog-actions">
     <button type="button" disabled={busy} onClick={onClose}>Отмена</button>
     {onSubmit&&<button type="submit" disabled={busy||submitDisabled} className="primary">
      {busy?'Сохранение…':submitLabel}
     </button>}
    </div>
   </footer>
  </form>
 </dialog>,document.body);
}
