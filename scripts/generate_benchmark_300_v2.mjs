// Deterministic 300 EML benchmark, no external dependencies. Node.js >= 18.
// Usage: node scripts/generate_benchmark_300_v2.mjs [output-root]
// In a local checkout this regenerates the checked-in EML and manifest exactly.
import fs from "node:fs";
import path from "node:path";
const GROUPS=[["control",60],["pii",55],["commercial",55],["safety",45],["secrets",40],["documents",25],["mixed",20]];
const LABELS={"pii":["RU_PASSPORT","RU_SNILS","RU_INN","pack-ru2-pii-handling"],"commercial":["pack-ru2-financial-plans","pack-ru2-pricing","pack-ru2-internal-docs"],"safety":["pack-ru2-explosive-threat","pack-ru2-violence-threat","pack-ru2-extortion","pack-ru2-sabotage"],"secrets":["pack-ru2-phishing","pack-ru2-credential-transfer","SECRET"],"documents":["pack-ru2-customer-data","pack-ru2-data-exfil"],"mixed":["pack-ru2-financial-plans","pack-ru2-pricing","pack-ru2-internal-docs","pack-ru2-customer-data","pack-ru2-data-exfil","pack-ru2-credential-transfer"]};
function utf8(s){let b=[];for(let i=0;i<s.length;i++){let c=s.codePointAt(i);if(c>65535)i++;if(c<128)b.push(c);else if(c<2048)b.push(192|(c>>6),128|(c&63));else if(c<65536)b.push(224|(c>>12),128|((c>>6)&63),128|(c&63));else b.push(240|(c>>18),128|((c>>12)&63),128|((c>>6)&63),128|(c&63));}return b;}

function base64(bytes){const chars="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";let s="";for(let i=0;i<bytes.length;i+=3){const n=(bytes[i]<<16)|((bytes[i+1]||0)<<8)|(bytes[i+2]||0);s+=chars[(n>>18)&63]+chars[(n>>12)&63]+(i+1<bytes.length?chars[(n>>6)&63]:"=")+(i+2<bytes.length?chars[n&63]:"=");}return s;}

function le16(x){return[x&255,(x>>>8)&255];}

function le32(x){return[x&255,(x>>>8)&255,(x>>>16)&255,(x>>>24)&255];}

function crc32(data){let c=0xffffffff;for(let b of data){c^=b;for(let j=0;j<8;j++)c=(c>>>1)^(c&1?0xedb88320:0);}return(c^0xffffffff)>>>0;}

function zipStored(entries){const result=[],central=[];let off=0;for(const [name,content] of entries){const fn=utf8(name),data=utf8(content),crc=crc32(data);const local=[...le32(0x04034b50),...le16(20),...le16(0x800),...le16(0),...le16(0),...le16(0),...le32(crc),...le32(data.length),...le32(data.length),...le16(fn.length),...le16(0),...fn,...data];result.push(...local);central.push(...le32(0x02014b50),...le16(20),...le16(20),...le16(0x800),...le16(0),...le16(0),...le16(0),...le32(crc),...le32(data.length),...le32(data.length),...le16(fn.length),...le16(0),...le16(0),...le16(0),...le16(0),...le32(0),...le32(off),...fn);off+=local.length;}return [...result,...central,...le32(0x06054b50),...le16(0),...le16(0),...le16(entries.length),...le16(entries.length),...le32(central.length),...le32(off),...le16(0)];}

function esc(s){return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}

function makeDocx(text){const para=text.split("\n").map(x=>`<w:p><w:r><w:t xml:space="preserve">${esc(x)}</w:t></w:r></w:p>`).join("");return zipStored([
 ["[Content_Types].xml",`<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>`],
 ["_rels/.rels",`<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>`],
 ["word/document.xml",`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>${para}<w:sectPr/></w:body></w:document>`]
]);}

function makeXlsx(text){const lines=text.split("\n").filter(Boolean);const rows=lines.map((v,i)=>`<row r="${i+1}"><c r="A${i+1}" t="inlineStr"><is><t>${esc(v)}</t></is></c></row>`).join("");return zipStored([
 ["[Content_Types].xml",`<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>`],
 ["_rels/.rels",`<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`],
 ["xl/workbook.xml",`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Лист1" sheetId="1" r:id="rId1"/></sheets></workbook>`],
 ["xl/_rels/workbook.xml.rels",`<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>`],
 ["xl/worksheets/sheet1.xml",`<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${rows}</sheetData></worksheet>`]
]);}

function messageCase(i){
 const id=`MF300-${String(i+1).padStart(4,"0")}`;let group="mixed",offset=0,start=0;
 for(const [name,n] of GROUPS){if(i<start+n){group=name;offset=i-start;break;}start+=n;}
 const names=["Анна Сергеева","Павел Никитин","Мария Лебедева","Игорь Громов","Ольга Морозова","Дмитрий Орлов","Екатерина Соколова","Алексей Кузнецов"];
 const name=names[(i*5+3)%names.length],partner=["Север-Логистика","Меридиан-Трейд","Вектор-Сервис","Альтаир Консалт","Горизонт-Проект"][(i*3)%5];
 const amount=(150000+(i*7919)%8600000).toLocaleString("ru-RU").replace(/\u00a0|\u202f/g," ");
 let scenario="",labels=[],body="",subject="",difficulty=["easy","medium","hard"][i%3];
 const suffix=`\n\nС уважением,\n${name}\nОтдел ${["закупок","сопровождения","проектов","финансов","эксплуатации"][i%5]}`;
 if(group==="control"){
  const k=offset%8;scenario=["public_pricing","phishing_training","fictional_threat_quote","public_budget","policy_discussion","dummy_number","normal_invoice","fake_credential_training"][k];
  const values=[
   ["Розничные цены опубликованы","Направляю ссылку на открытый прайс-лист на нашем сайте. Индивидуальные условия и скидки здесь не обсуждаются; это общий публичный документ для всех заказчиков."],
   ["Итоги тренинга безопасности","На обучении разбирали письмо «подтвердить аккаунт и сообщить пароль». Это цитата учебного образца фишинга, никаких настоящих данных мы не запрашиваем."],
   ["Цитата из сценария фильма","В художественном сценарии герой говорит «я устрою взрыв», но это фрагмент диалога для редакторской правки, а не угроза кому-либо."],
   ["Публичные цифры годового отчета","Опубликованный бюджет муниципального проекта доступен на сайте заказчика. Пришлите, пожалуйста, только открытую ссылку; закрытых прогнозов здесь нет."],
   ["Обсуждение регламента","В инструкции сказано, что внутренний документ нельзя отправить внешнему подрядчику. Это обсуждение правил, а не фактическая пересылка материала."],
   ["Учебные реквизиты в документации","Пример поля: серия паспорта 0000, номер 000000, ИНН 0000000000 и СНИЛС 000-000-000 00. Значения заведомо учебные и не относятся к гражданину."],
   ["Согласование переговорной","Коллеги, пожалуйста, подтвердите бронь переговорной на среду, подключение проектора и время встречи с поставщиками."],
   ["Демонстрация структуры конфигурации","В примере документации показано поле api_key=EXAMPLE_NOT_A_REAL_SECRET; это шаблон, не действующий ключ, использовать его для доступа нельзя."]
  ];[subject,body]=values[k];
 }else if(group==="pii"){
   const k=offset%4;const digits=String(1000000000+((i*8723421)%8000000000));
   scenario=["passport_russian","snils_card","inn_certificate","pii_transfer"][k];
   const values=[
    [`Запрос копии паспорта сотрудника ${name}`,`Паспорт гражданина РФ. РОССИЙСКАЯ ФЕДЕРАЦИЯ. Фамилия ${name.split(" ")[1]}, имя ${name.split(" ")[0]}. Серия 45 08, номер ${String(100000+i*49).padStart(6,"0")}. Дата выдачи 12.09.2016. Код подразделения 770-002. Направляю заполненную анкету для кадрового делопроизводства.`],
    [`Карточка СНИЛС для отдела кадров`,`Страховой номер индивидуального лицевого счета (СНИЛС) сотрудника ${name}. Пожалуйста, проверьте запись: ${String(100000000+i*1327).slice(0,9)}-00. В приложении карточка кадрового учета.`],
    [`Реквизиты налогоплательщика`,`Свидетельство о постановке на учет физического лица. Идентификационный номер налогоплательщика ИНН ${digits.slice(0,10)}. ${name}. Подтвердите получение.`],
    [`Передача персональных данных сотрудников`,`Для кадровой сверки требуется переслать персональные данные: ФИО, паспорт, телефон и место регистрации. Список сотрудников должен оставаться в защищенном рабочем контуре.`]
   ];[subject,body]=values[k];
   labels=[["RU_PASSPORT"],["RU_SNILS"],["RU_INN"],["pack-ru2-pii-handling"]][k];
   if(k===1||k===2) difficulty="hard"; // some numbers intentionally checksum-invalid, diagnostic
 }else if(group==="commercial"){
   const k=offset%5;scenario=["financial_forecast","internal_budget","restricted_pricing","cost_margin","restricted_doc"][k];
   const values=[
    [`Прогноз выручки ${partner}`,`Внутренний прогноз выручки на следующий квартал: ${amount} рублей. Плановый прирост по основным клиентам 7,8%, пересмотр после закрытия периода. Не включать в публичную презентацию.`],
    [`Непубличный бюджет подразделения`,`Непубличный бюджет подразделения на декабрь: ${amount} рублей. Согласовать перенос затрат между статьями после утверждения CFO; публикация данных запрещена.`],
    [`Индивидуальная скидка для клиента`,`Для клиента ${partner} согласовать индивидуальную скидку 17% к цене поставки. Коммерческие условия рассчитаны для отдельного тендера и не должны попасть в общий прайс.`],
    [`Внутренняя себестоимость проекта`,`Себестоимость этапа ${amount} рублей, наценка 21%, расчетная маржа 14%. Финансовая модель предназначена для руководства проекта, пересылка заказчику до согласования запрещена.`],
    [`Служебная записка ограниченного доступа`,`Только для внутреннего использования. Прилагается внутренний документ с подробной оценкой контрагента ${partner}. Запрещено передавать третьим лицам.`]
   ];[subject,body]=values[k];labels=[["pack-ru2-financial-plans"],["pack-ru2-financial-plans"],["pack-ru2-pricing"],["pack-ru2-pricing"],["pack-ru2-internal-docs"]][k];
 }else if(group==="safety"){
   const k=offset%4;scenario=["explosive_threat","violence_threat","extortion","it_sabotage"][k];
   const values=[
    ["Угроза администрации офиса","Я устрою взрыв в здании офиса завтра. Это прямое угрожающее сообщение, прошу немедленно передать его службе безопасности."],
    ["Угроза сотруднику","Я тебя убью, если завтра снова появишься на объекте. Передайте эту переписку ответственному за безопасность."],
    ["Требование выкупа","Требую выкуп за данные организации. Заплатите деньги, иначе опубликую внутренние документы; отсчет начинается сегодня."],
    ["Угроза уничтожить резервные копии","Я намеренно удалю резервные копии серверов и выведу сервер из строя в конце смены. Не пытайтесь скрыть это сообщение."]
   ];[subject,body]=values[k];labels=[["pack-ru2-explosive-threat"],["pack-ru2-violence-threat"],["pack-ru2-extortion"],["pack-ru2-sabotage"]][k];
 }else if(group==="secrets"){
   const k=offset%4;scenario=["phishing_account","phishing_otp","credential_transfer","secret_leak"][k];
   const values=[
    ["Срочное подтверждение учетной записи","Для сохранения доступа нужно срочно подтвердить аккаунт по ссылке https://security-check.example.test/verify и ввести пароль. Иначе учетная запись будет заблокирована."],
    ["Запрос одноразового кода","Для завершения проверки сообщите одноразовый код подтверждения из SMS. Пришлите его ответом на это письмо, чтобы восстановить доступ."],
    ["Запрос секретного ключа сервиса","Прошу прислать токен доступа к API, отправить приватный ключ и рабочий пароль для подключения партнера. Доступ необходимо открыть сегодня."],
    ["Передача конфигурации","В переписку попала строка api_key=mf_demo_secret_2026_7f3d8e19c4b65a12. Этот ключ выглядит действующим, требуется инцидент и отзыв секрета."]
   ];[subject,body]=values[k];labels=[["pack-ru2-phishing"],["pack-ru2-phishing"],["pack-ru2-credential-transfer"],["SECRET"]][k];
 }else if(group==="documents"){
   const k=offset%2;scenario=["customer_database_export","document_exfiltration"][k];
   const values=[
    ["Выгрузка клиентской базы для сверки","Требуется выгрузка базы клиентов в CSV: ФИО, телефоны, адреса электронной почты, история заказов. Пожалуйста, отправьте список контактов в отдел сопровождения."],
    ["Копирование документа во внешний контур","Прошу отправить внутренний файл с коммерческими документами на личную почту внешнего подрядчика. Контрагенту нельзя выдавать материалы до разрешения службы безопасности."]
   ];[subject,body]=values[k];labels=[["pack-ru2-customer-data"],["pack-ru2-data-exfil"]][k];
 }else{
   const k=offset%4;scenario=["mixed_forecast_credentials","mixed_customer_price","mixed_exfil_internal","mixed_finance_pii"][k];
   const values=[
    ["Срочная сверка бюджета и доступов","Непубличный бюджет подразделения на декабрь ${amount} рублей. Пришлите рабочий пароль и токен доступа, чтобы временно открыть отчет внешнему консультанту."],
    ["Список клиентов со скидками","Выгрузка базы клиентов для индивидуальных скидок: клиент ${partner}, согласовать скидку 12% к цене, контакты и история заказов приложены."],
    ["Передача закрытого документа","Внутренний документ: строго конфиденциально. Прошу отправить внутренний файл на личную почту подрядчика, хотя не подлежит распространению без согласования."],
    ["Прогноз с кадровыми данными","Внутренний прогноз выручки на квартал ${amount} рублей; персональные данные сотрудников и сведения о начислениях прошу переслать финансовому директору."]
   ];[subject,body]=values[k];body=body.replaceAll("${amount}",amount).replaceAll("${partner}",partner);labels=[["pack-ru2-financial-plans","pack-ru2-credential-transfer"],["pack-ru2-customer-data","pack-ru2-pricing"],["pack-ru2-internal-docs","pack-ru2-data-exfil"],["pack-ru2-financial-plans","pack-ru2-pii-handling"]][k];
 }
 const letterBody=body+suffix;
 const carry=group!=="control"&&(i%5!==0 || i%10===0);
 const attachmentType=!carry?"none":(["txt","docx","xlsx","csv","html"][i%5]);
 const attachmentContent=`${subject}\n${body}\nКонтрагент: ${partner}\nОбъем: ${amount} руб.\nОтветственный: ${name}`;
 const visibleBody=carry&&i%3===0?`Добрый день, прошу рассмотреть вложенный материал по теме «${subject}». Ожидаю обратную связь до конца недели.\n${suffix}`:letterBody;
 return {id,group,scenario,subject,body:visibleBody,labels,attachment_type:attachmentType,attachment_content:attachmentContent,difficulty,seed_index:i,has_attachment:carry};
}

function generateOne(i){
 const d=messageCase(i),boundary=`mailfire-benchmark-${d.id}-boundary`;
 const fromDomain=["sever-logistics.example.test","meridian-trade.example.test","altiar-project.example.test"][i%3];
 const from=`office${i%23}@${fromDomain}`,to=`department${i%11}@mailfire.example.test`;
 const date=new Date(Date.UTC(2026,10,20,6,0,0)+(i*93000)).toUTCString();
 const subject=`=?UTF-8?B?${base64(utf8(d.subject))}?=`;
 const headers=[`From: ${from}`,`To: ${to}`,`Date: ${date}`,`Subject: ${subject}`,`Message-ID: <${d.id.toLowerCase()}@benchmark.mailfire.example.test>`,`MIME-Version: 1.0`,`X-MailFire-Benchmark: benchmark-300-v2`,`X-MailFire-Benchmark-ID: ${d.id}`];
 let eml="";
 const mailbody=d.body.replace(/\r?\n/g,"\r\n");
 if(d.attachment_type==="none"){eml=headers.concat(['Content-Type: text/plain; charset="utf-8"','Content-Transfer-Encoding: 8bit',"",mailbody,""]).join("\r\n");}
 else{
  let ext=d.attachment_type,contentType="",data="",cte="base64";
  if(ext==="docx"){contentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document";data=base64(makeDocx(d.attachment_content));}
  else if(ext==="xlsx"){contentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";data=base64(makeXlsx(d.attachment_content));}
  else if(ext==="html"){contentType="text/html";data=base64(utf8(`<html><head><meta charset="utf-8"></head><body><p>${esc(d.attachment_content).replace(/\n/g,"</p><p>")}</p></body></html>`));}
  else if(ext==="csv"){contentType="text/csv";data=base64(utf8("Наименование;Значение\n"+d.attachment_content.split("\n").map((s,j)=>`${j+1};"${s.replace(/"/g,'""')}"`).join("\n")));}
  else{contentType="text/plain";data=base64(utf8(d.attachment_content));}
  const chunks=data.match(/.{1,76}/g).join("\r\n");
  const filename=`${d.id}-attachment.${ext}`;
  eml=headers.concat([`Content-Type: multipart/mixed; boundary="${boundary}"`,"",`--${boundary}`,'Content-Type: text/plain; charset="utf-8"',"Content-Transfer-Encoding: 8bit","",mailbody,`--${boundary}`,`Content-Type: ${contentType}; name="${filename}"`,`Content-Disposition: attachment; filename="${filename}"`,`Content-Transfer-Encoding: ${cte}`,"",chunks,`--${boundary}--`,""]).join("\r\n");
 }
 const annotation={id:d.id,file:`eml/${d.id}.eml`,scenario:d.scenario,group:d.group,expected_semantic_categories:d.labels,expected_no_issue:d.labels.length===0,attachment_type:d.attachment_type,difficulty:d.difficulty,annotation_status:"synthetic_author_defined",evaluation_split:"holdout",notes:"Semantics ground truth, not exact rule/policy outputs; no production policy modified."};
 return {eml,annotation};
}
const ROOT = process.argv[2] || "test-data/benchmark-300-v2";
fs.mkdirSync(path.join(ROOT,"eml"),{recursive:true});
const annotations=[];
for(let i=0;i<300;i++){const {eml,annotation}=generateOne(i);fs.writeFileSync(path.join(ROOT,"eml",annotation.id+".eml"),eml,"utf8");annotations.push(annotation);}
fs.writeFileSync(path.join(ROOT,"manifest.jsonl"),annotations.map(x=>JSON.stringify(x)).join("\n")+"\n","utf8");
console.log("Generated 300 EML plus manifest at",ROOT);
