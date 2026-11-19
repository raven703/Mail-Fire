// Writes synthetic data only: explicitly opt in against an isolated test stand.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{
 assert.equal(process.env.MAILFIRE_SYNTHETIC_STAND,'1','Isolated synthetic stand opt-in required');
 const base=process.env.MAILFIRE_URL;assert(base,'MAILFIRE_URL required');
 const browser=await chromium.launch();
 try{
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.getByLabel('Имя пользователя').fill('admin');await page.getByLabel('Пароль',{exact:true}).fill(process.env.MAILFIRE_ADMIN_PASSWORD);await page.getByRole('button',{name:'Войти',exact:true}).click();
 const nav=async name=>page.locator('aside').getByRole('button',{name,exact:true}).click();
 const modal=()=>page.locator('dialog[open]').last();
 const save=async name=>{const count=await page.locator('dialog[open]').count();await modal().getByRole('button',{name,exact:true}).click();await page.waitForFunction(n=>document.querySelectorAll('dialog[open]').length===n-1,count)};
 const token=Date.now();const category='Synthetic modal '+token;
 await nav('Категории данных');await page.getByRole('button',{name:'＋ Категория',exact:true}).click();await modal().getByLabel('Название категории',{exact:true}).fill(category);await modal().getByLabel('Ключевые фразы, по одной на строку').fill('синтетический прогноз');await save('Сохранить категорию');
 const row=page.locator('.category-card, .policy-row, article, section').filter({has:page.getByText(category,{exact:true})}).filter({has:page.getByRole('button',{name:'Правила и настройки',exact:true})}).last();
 await row.getByRole('button',{name:'Правила и настройки',exact:true}).click();await modal().getByLabel('Описание',{exact:true}).fill('Synthetic edited description');await save('Сохранить категорию');
 await page.waitForTimeout(300);await row.getByRole('button',{name:'Правила и настройки',exact:true}).click();assert.equal(await modal().locator('textarea').first().inputValue(),'Synthetic edited description');await page.keyboard.press('Escape');
 // Exercise every shell in every requested theme/viewport, including long forms.
 const scenarios=[
 ['Категории данных','＋ Категория'],['Категории данных','Правила и настройки'],
 ['DLP-политики','＋ Новая политика'],['Настройки','Редактировать назначения'],
 ['Настройки','Изменить сроки','Хранение и очистка'],['Настройки','＋ Добавить пользователя','Пользователи'],
 ['ML-модели и обучение','＋ Добавить пример','Разметка'],['ML-модели и обучение','＋ Запустить обучение','Обучение'],
 ['ML-модели и обучение','＋ Импортировать датасет','Наборы данных'],
 ];
 for(const theme of ['light','dark'])for(const [width,height] of [[1920,1080],[375,812]])for(const [section,button,tab] of scenarios){
 await page.setViewportSize({width,height});await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await nav(section);if(tab)await page.getByRole('button',{name:tab,exact:true}).click();await page.getByRole('button',{name:button,exact:true}).first().click();const d=modal();await d.waitFor();
 if(section==='Категории данных')for(let i=0;i<3;i++)await d.getByRole('button',{name:'＋ Добавить правило',exact:true}).click();
 const geometry=await d.evaluate(el=>{const b=el.querySelector('.editor-dialog-body');b.scrollTop=b.scrollHeight;return {overflow:el.scrollWidth>el.clientWidth+2,bottom:el.getBoundingClientRect().bottom,scroll:b.scrollTop,needsScroll:b.scrollHeight>b.clientHeight+1,header:!!el.querySelector('.editor-dialog-header'),footer:!!el.querySelector('.editor-dialog-footer')}});
 assert(!geometry.overflow,JSON.stringify({section,button,theme,width,geometry}));assert(geometry.bottom<=height+1);assert(geometry.header&&geometry.footer);if(geometry.needsScroll)assert(geometry.scroll>0);
 await page.mouse.click(1,1);assert(await d.isVisible());await page.screenshot({path:`/tmp/pr7-${theme}-${width}-${scenarios.findIndex(s=>s[1]===button)}.png`});await d.getByRole('button',{name:'Отмена',exact:true}).click();
 }
 await nav('Настройки');await page.getByRole('button',{name:'Пользователи',exact:true}).click();await page.getByRole('button',{name:'＋ Добавить пользователя',exact:true}).click();const username='synthetic'+token;await modal().getByLabel('Имя пользователя',{exact:true}).fill(username);await modal().getByLabel('Новый пароль',{exact:true}).fill('Synthetic-only-password-2026');await save('Сохранить пользователя');await page.locator('tbody tr').filter({hasText:username}).click();await modal().locator('select[name=role]').selectOption('analyst');await save('Сохранить пользователя');
 await page.getByRole('button',{name:'SIEM и уведомления',exact:true}).click();await page.getByRole('button',{name:'Редактировать назначения',exact:true}).click();await modal().locator('textarea[name=urls]').fill('');await save('Сохранить назначения');
 await nav('ML-модели и обучение');await page.getByRole('button',{name:'Разметка',exact:true}).click();await page.getByRole('button',{name:'＋ Добавить пример',exact:true}).click();await modal().getByLabel('Текст примера',{exact:true}).fill('Synthetic classification sample '+token);await modal().locator('.policy-category-option input').first().check();await save('Сохранить пример');
 await nav('Инциденты');await page.locator('.incident-table tbody tr').first().click();await page.getByRole('button',{name:'Изменить решение',exact:true}).click();await modal().getByLabel('Статус расследования').selectOption('REVIEW');await modal().getByLabel('Комментарий',{exact:true}).fill('Synthetic modal acceptance '+token);await save('Сохранить решение');
 assert.deepEqual(errors,[]);console.log('PASS real synthetic category create/edit, account create/edit, settings, ML example, incident decision; all-shell theme/viewport matrix, long-form scrolling and outside click');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
