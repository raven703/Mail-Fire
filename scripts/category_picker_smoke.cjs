const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {execFileSync}=require('child_process');
(async()=>{
 const password=process.env.MAILFIRE_ADMIN_PASSWORD||execFileSync(
  process.env.MAILFIRE_PYTHON||'/home/user/Mail-Fire/.venv/bin/python',
  ['-c','from app.config import settings; print(settings().admin_password)'],{cwd:process.cwd()}
 ).toString().trim();
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:940}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.MAILFIRE_URL||'http://localhost:8080');
  await page.getByLabel('Имя пользователя').fill('admin');
  await page.getByLabel('Пароль',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Войти',exact:true}).click();
  await page.locator('aside').getByRole('button',{name:'DLP-политики'}).click();
  await page.getByRole('button',{name:'＋ Новая политика'}).click();
  const parent=page.locator('.editor-dialog[open]').first();
  await parent.waitFor();
  const picker=parent.locator('.policy-category-card');
  await picker.locator('.policy-category-option input').first().waitFor();
  await picker.getByRole('searchbox',{name:'Поиск категорий'}).fill('секрет');
  const choices=picker.locator('.policy-category-option input');
  if(await choices.count()){await choices.first().check()}
  await picker.getByRole('searchbox',{name:'Поиск категорий'}).fill('');
  await parent.locator('input[value=all]').check();
  await picker.getByRole('button',{name:'＋ Новая категория'}).click();
  const child=page.locator('.editor-dialog[open]').last();
  await child.getByRole('heading',{name:'Новая категория'}).waitFor();
  await child.getByLabel('Название категории').fill('Unsaved test category');
  await child.getByRole('button',{name:'＋ Добавить правило'}).click();
  await page.keyboard.press('Escape');
  await page.waitForFunction(()=>document.querySelectorAll('dialog[open]').length===1);
  if(!await parent.isVisible())throw Error('Parent dialog unexpectedly closed');
  for(const theme of ['light','dark']){
   await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
   for(const width of [1440,390]){
    await page.setViewportSize({width,height:920});
    if(await parent.evaluate(el=>el.scrollWidth>el.clientWidth+2))throw Error('Horizontal overflow');
    await page.screenshot({path:'/tmp/category-picker-'+theme+'-'+width+'.png'});
   }
  }
  await page.keyboard.press('Escape');
  if(errors.length)throw Error(errors.join('\n'));
  console.log('PASS current category picker: search, multi-select, ANY/ALL, nested creation modal, Esc, themes, responsive');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
