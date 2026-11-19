// Read-only UI modal regression smoke (no model training or writes).
// Usage: PLAYWRIGHT_MODULE=/path/to/playwright MAILFIRE_PYTHON=/path/to/python node scripts/edit_dialogs_smoke.cjs
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {execFileSync}=require('child_process');
const python=process.env.MAILFIRE_PYTHON||'/home/user/Mail-Fire/.venv/bin/python';
const base=process.env.MAILFIRE_URL||'http://localhost:8080';
async function run(){
 const password=process.env.MAILFIRE_ADMIN_PASSWORD||
  execFileSync(python,['-c','from app.config import settings; print(settings().admin_password)'],
   {cwd:process.cwd()}).toString().trim();
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  const errors=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{
   if(/\/api\//.test(r.url())&&['POST','PUT','PATCH','DELETE'].includes(r.method())&&
    !/\/api\/login$/.test(r.url()))writes.push(r.method()+' '+r.url());
  });
  await page.goto(base);
  await page.getByLabel('Имя пользователя').fill('admin');
  await page.getByLabel('Пароль',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Войти'}).click();
  await page.getByRole('heading',{name:'Обзор безопасности',exact:true}).waitFor();

  const nav=async title=>{
   await page.locator('aside').getByRole('button',{name:title,exact:true}).click();
  };
  const modal=()=>page.locator('dialog[open]').last();
  async function checkDialog(title){
   const d=modal();
   await d.waitFor();
   if(!await d.getByRole('heading',{name:title,exact:true}).count())
    throw Error('Wrong modal title: '+title);
   const parts=await d.evaluate(el=>({
    h:!!el.querySelector('.editor-dialog-header'),
    b:!!el.querySelector('.editor-dialog-body'),
    f:!!el.querySelector('.editor-dialog-footer'),
    scroll:el.scrollWidth>el.clientWidth+2,
   }));
   if(!parts.h||!parts.b||!parts.f||parts.scroll)throw Error('Inconsistent shell '+title+JSON.stringify(parts));
   return d;
  }
  async function closeWith(method){
   const d=modal();
   if(method==='Escape')await page.keyboard.press('Escape');
   else if(method==='X')await d.getByRole('button',{name:'Закрыть окно'}).click();
   else await d.getByRole('button',{name:'Отмена'}).click();
   await d.waitFor({state:'hidden'});
  }

  await nav('Категории данных');
  await page.getByRole('button',{name:'＋ Категория'}).click();
  await checkDialog('Новая категория');
  await modal().getByLabel('Название категории').fill('unsaved user interface check');
  await page.mouse.click(2,2);
  if(!await modal().isVisible())throw Error('Backdrop click unexpectedly closed modal');
  await closeWith('Escape');
  await page.getByRole('button',{name:'＋ Категория'}).click();
  await checkDialog('Новая категория');await closeWith('X');
  const editCategory=page.getByRole('button',{name:'Правила и настройки'}).first();
  if(await editCategory.count()){
   await editCategory.click();await checkDialog('Редактировать категорию');
   await closeWith('Cancel');
  }

  await nav('DLP-политики');
  await page.getByRole('button',{name:'＋ Новая политика'}).click();
  await checkDialog('Новая политика');
  await modal().getByRole('button',{name:'＋ Новая категория'}).click();
  await checkDialog('Новая категория');
  await closeWith('Escape');
  await checkDialog('Новая политика');
  await closeWith('Cancel');

  await nav('ML-модели и обучение');
  await page.getByRole('button',{name:'Наборы данных',exact:true}).click();
  await page.getByRole('button',{name:'＋ Импортировать датасет'}).click();
  await checkDialog('Импортировать набор данных');await closeWith('Escape');
  const datasets=page.getByRole('button',{name:'Проверить примеры'});
  if(await datasets.count()){
   await datasets.first().click();
   const example=page.getByRole('button',{name:'Изменить и проверить разметку'}).first();
   if(await example.count()){await example.click();await checkDialog('Проверить разметку');await closeWith('Cancel')}
  }
  await page.getByRole('button',{name:'Разметка',exact:true}).click();
  await page.getByRole('button',{name:'＋ Добавить пример'}).click();
  await checkDialog('Добавить обучающий пример');await closeWith('X');
  await page.getByRole('button',{name:'Обучение',exact:true}).click();
  await page.getByRole('button',{name:'＋ Запустить обучение'}).click();
  await checkDialog('Запустить обучение модели');await closeWith('Cancel');

  await nav('Настройки');
  await page.getByRole('button',{name:'Редактировать назначения'}).click();
  await checkDialog('Редактировать SIEM и Webhook');await closeWith('Escape');
  await page.getByRole('button',{name:'Хранение и очистка'}).click();
  await page.getByRole('button',{name:'Изменить сроки'}).click();
  await checkDialog('Изменить сроки хранения');await closeWith('X');
  await page.getByRole('button',{name:'Пользователи',exact:true}).click();
  await page.getByRole('button',{name:'＋ Добавить пользователя'}).click();
  await checkDialog('Новый пользователь');await closeWith('Cancel');
  const accountRow=page.locator('tbody tr').first();
  if(await accountRow.count()){
   await accountRow.click();await checkDialog('Редактировать пользователя');await closeWith('Escape');
  }

  await nav('Инциденты');
  const incidentRow=page.locator('.incident-table tbody tr').first();
  if(await incidentRow.count()){
   await incidentRow.click();
   await page.getByRole('button',{name:'Назначить аналитика'}).click();
   await checkDialog('Назначить аналитика');await closeWith('Escape');
   await page.getByRole('button',{name:'Изменить решение'}).click();
   await checkDialog('Изменить решение по инциденту');await closeWith('X');
   if(await page.getByRole('button',{name:'＋ Добавить в обучающую выборку'}).count()){
    await page.getByRole('button',{name:'＋ Добавить в обучающую выборку'}).click();
    await checkDialog('Добавить пример из инцидента');await closeWith('Cancel');
   }
  }

  await nav('Категории данных');
  for(const theme of ['light','dark']){
   await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
   for(const width of [1440,375]){
    await page.setViewportSize({width,height:820});
    await page.getByRole('button',{name:'＋ Категория'}).click();
    await checkDialog('Новая категория');
    if(await modal().evaluate(d=>d.scrollWidth>d.clientWidth+2))
     throw Error('Modal overflow '+theme+' '+width);
    await page.screenshot({path:'/tmp/mailfire-edit-modal-'+theme+'-'+width+'.png'});
    await closeWith('Escape');
   }
  }
  if(writes.length)throw Error('Unsaved edits sent API writes: '+writes.join(', '));
  if(errors.length)throw Error('Browser JS exceptions: '+errors.join(', '));
  console.log('PASS unified modal creation/edit: category, policy+nesting, datasets, ML, settings, accounts, incidents; Esc/X/Cancel, no implicit saves; mobile/desktop/themes');
 }finally{await browser.close()}
}
run().catch(e=>{console.error(e);process.exitCode=1});
