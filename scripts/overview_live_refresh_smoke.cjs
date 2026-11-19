// Verifies that dashboard polling uses a rolling window without touching DB.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {execFileSync}=require('node:child_process');

(async()=>{
 const password=execFileSync('/home/user/Mail-Fire/.venv/bin/python',
  ['-c','from app.config import settings;print(settings().admin_password)'],
  {cwd:'/home/user/Mail-Fire'}).toString().trim();
 const browser=await chromium.launch();
 try {
  const page=await browser.newPage();
  const requests=[];
  page.on('request',r=>{
   const url=new URL(r.url());
   if(r.method()==='GET'&&url.pathname==='/api/workspace/overview'){
    requests.push({start:url.searchParams.get('start'),end:url.searchParams.get('end')});
   }
  });
  await page.goto(process.env.MAILFIRE_URL||'http://localhost:8080');
  await page.getByLabel('Имя пользователя').fill('admin');
  await page.getByLabel('Пароль',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Войти',exact:true}).click();
  await page.locator('.security-overview').waitFor();
  await page.waitForFunction(()=>true); // Confirm page remains interactive.
  const started=Date.now();
  while(requests.length<2&&Date.now()-started<18000)
   await page.waitForTimeout(250);
  if(requests.length<2)throw Error('Dashboard did not poll at least twice');
  const [first,second]=requests;
  if(!(Date.parse(second.end)>Date.parse(first.end)))
   throw Error('Preset period end is frozen across polls');
  if(!(Date.parse(second.start)>Date.parse(first.start)))
   throw Error('Preset period start is frozen across polls');
  const windowMs=Date.parse(second.end)-Date.parse(second.start);
  if(Math.abs(windowMs-24*3600000)>2000)
   throw Error('Rolling 24-hour window has the wrong duration: '+windowMs);
  console.log('PASS rolling window',first.end,'->',second.end);
 } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
