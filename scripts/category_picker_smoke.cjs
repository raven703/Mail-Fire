const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {execFileSync}=require('child_process');
(async()=>{
 const password=execFileSync('/home/user/Mail-Fire/.venv/bin/python',['-c','from app.config import settings; print(settings().admin_password)'],{cwd:'/home/user/Mail-Fire'}).toString().trim();
 const browser=await chromium.launch({headless:true});const context=await browser.newContext({permissions:['clipboard-read','clipboard-write']});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://localhost:8080');await page.getByLabel('Имя пользователя').fill('admin');await page.getByLabel('Пароль',{exact:true}).fill(password);await page.getByRole('button',{name:'Войти',exact:true}).click();await page.getByRole('heading',{name:'Обзор безопасности',exact:true}).waitFor();
 await page.locator('aside').getByRole('button',{name:'ML-модели и обучение',exact:true}).click();await page.getByRole('button',{name:'Разметка',exact:true}).click();
 const picker=page.locator('.category-picker');await picker.locator('.cp-option').first().waitFor();
 await picker.getByLabel('Поиск категории',{exact:true}).fill('Паспорт');await picker.locator('.cp-option input').first().check();if(!JSON.parse(await picker.locator('.cp-preview').innerText()).categories.length)throw Error('Selection missing');
 await picker.getByRole('button',{name:'Скопировать JSON'}).click();await picker.getByText('JSON скопирован',{exact:true}).waitFor();
 await picker.getByRole('button',{name:'Применить',exact:true}).click();await picker.getByText('Выбор применён. Сохраните обучающий пример.',{exact:true}).waitFor();
 await picker.getByRole('button',{name:'Очистить поиск'}).click();await picker.getByRole('button',{name:'＋ Создать категорию',exact:true}).click();
 const dialog=page.getByRole('dialog');await dialog.waitFor();await dialog.getByLabel('Название категории',{exact:true}).fill('UI unsaved test');
 await dialog.getByRole('button',{name:'＋ Добавить правило'}).click();await dialog.getByRole('button',{name:'＋ Добавить правило'}).click();await dialog.getByRole('button',{name:'＋ Добавить правило'}).click();
 const types=dialog.locator('.category-rule select');await types.nth(1).selectOption('regex');await types.nth(2).selectOption('reference');await types.nth(3).selectOption('ml');await dialog.getByLabel('Объединение правил').selectOption('all');
 await page.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});if(!await picker.getByRole('button',{name:'＋ Создать категорию',exact:true}).evaluate(e=>e===document.activeElement))throw Error('Focus not restored');
 for(const theme of ['light','dark']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);for(const width of [1440,390]){await page.setViewportSize({width,height:900});await page.screenshot({path:`/tmp/picker-${theme}-${width}.png`,fullPage:true});const overflow=await picker.evaluate(e=>e.scrollWidth>e.clientWidth+1);if(overflow)throw Error(`Picker overflow ${theme} ${width}`)}}
 await picker.getByRole('button',{name:'Сбросить выбор'}).click();if(JSON.parse(await picker.locator('.cp-preview').innerText()).categories.length)throw Error('Reset failed');
 await page.setViewportSize({width:1440,height:1000});await page.locator('aside').getByRole('button',{name:'DLP-политики',exact:true}).click();const edit=page.getByRole('button',{name:/Настроить/}).first();await edit.click();await page.locator('.category-picker').getByRole('heading',{name:'Категории обнаружения',exact:true}).waitFor();
 if(errors.length)throw Error(errors.join('\n'));console.log('PASS API catalog, search, selection, JSON clipboard, apply, reset, multi-rule dialog, Escape/focus, light/dark desktop/mobile, shared policy picker, no JS errors');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
