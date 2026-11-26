"""Single fresh B-400 run through durable acceptance and live unified workers."""
import os,sys,json,time,hashlib,subprocess,threading
from pathlib import Path
from datetime import datetime
ROOT=Path('/review');sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','mice.settings')
import django
django.setup()
from django.utils import timezone
from django.db import connection
from pipeline.ingestion import accept
from pipeline.evidence import configuration
from pipeline.models import WorkItem
from pipeline.inference import enabled
from policy_engine.models import Evaluation
from records.models import Message,Attachment,Incident,Policy,Setting
from records.ocr_settings import configuration as ocr_config
OUT=ROOT/'test-data/results-benchmark400-20261126/B';CORPUS=ROOT/'test-data/benchmark-400-v1'
def save(n,v):
 p=OUT/n;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str));t.replace(p)
def main():
 assert not (OUT/'run.json').exists(),'Refusing a second run'
 rows=[json.loads(l) for l in (CORPUS/'manifest.jsonl').read_text().splitlines()];assert len(rows)==400
 hashes={r['id']:hashlib.sha256((CORPUS/r['file']).read_bytes()).hexdigest() for r in rows}
 assert len(set(hashes.values()))==400
 assert not Message.objects.filter(original_sha_ref_id__in=hashes.values()).exists(),'Existing benchmark content'
 assert not WorkItem.objects.filter(kind__in=['analysis.analyze','policy.evaluate'],status__in=['PENDING','RUNNING']).exists()
 assert not enabled('ml') and not enabled('llm')
 # Only requested runtime switches; never modify rules, categories or policies.
 normalizer=Setting.objects.get(pk='normalizer');save('normalizer-before.json',normalizer.value)
 normalizer.value={**normalizer.value,'enabled':True,'mode':'detect','sensitivity':'high'};normalizer.save(update_fields=['value'])
 cfg=configuration();ocr=ocr_config();assert ocr['enabled']
 flags=cfg['settings']['detectors'];assert all(flags.get(k) is False for k in ['ml','llm','semantic'])
 assert len([g for g in cfg['groups'] if g['category']['id'].startswith('pack-ru2-')])==12
 start=timezone.now();runid='benchmark400-B-'+start.strftime('%Y%m%dT%H%M%S')
 save('run.json',{'run_id':runid,'started_at':start,'configuration':cfg,'ocr_configuration':ocr,'policies':list(Policy.objects.values()),'dataset_commit':'7a433a3ac23fe3c8f13aa86effc95fa257623927','code_commit':'e69c2fe373a0c0fedecaee2bf547e64f5b13d529','method':'400 fresh accept calls, live analysis.analyze -> policy.evaluate; no reanalysis','antivirus_limitation':'Not configured; existing switch false retained','manifest_sha256':hashlib.sha256((CORPUS/'manifest.jsonl').read_bytes()).hexdigest()})
 save('input-hashes.json',hashes);pending={};observed=[]
 for r in rows:
  before=timezone.now();rec=accept((CORPUS/r['file']).read_bytes(),'benchmark',runid+':'+r['id'],Path(r['file']).name);assert not rec.duplicate
  pending[r['id']]={'id':r['id'],'message_id':rec.message_id,'sha256':hashes[r['id']],'accepted_at':before.isoformat()}
 save('accepted.json',pending)
 deadline=time.monotonic()+14400
 while pending:
  assert configuration()==cfg and ocr_config()==ocr,'Configuration changed during run'
  for identifier,ctx in list(pending.items()):
   jobs=list(WorkItem.objects.filter(payload__message_id=ctx['message_id'],created_at__gte=start).order_by('created_at'))
   analysisjob=next((j for j in jobs if j.kind=='analysis.analyze'),None)
   ev=Evaluation.objects.filter(job__in=jobs).select_related('analysis','job').order_by('created_at').last()
   expired=time.monotonic()>deadline
   if not ev and not any(j.status=='DEAD' for j in jobs) and not expired:continue
   m=Message.objects.select_related('content').get(pk=ctx['message_id']);analysis=ev.analysis.results['analysis'] if ev else (m.content.analysis if m.content else {})
   if ev:
    assert analysisjob and analysisjob.status=='DONE' and str(ev.job_id)==analysisjob.output['policy_job_id']
    assert analysis['configuration_snapshot']==cfg
   last=max((j.finished_at or timezone.now() for j in jobs),default=timezone.now())
   o={**ctx,'status':m.status,'error':m.error,'text':m.content.text if m.content else '', 'analysis':analysis,'attachments':list(Attachment.objects.filter(message=m).values('id','name','mime','status','text','details')),'evaluation_id':str(ev.pk) if ev else None,'policy_hits':ev.hits if ev else [],'incidents':list(Incident.objects.filter(message=m).values()),'seconds':(last-datetime.fromisoformat(ctx['accepted_at'])).total_seconds(),'pipeline_jobs':[{'id':str(j.pk),'kind':j.kind,'status':j.status,'attempts':j.attempts,'deferrals':j.deferrals,'error':j.error,'created_at':j.created_at,'started_at':j.started_at,'finished_at':j.finished_at,'output':j.output,'execution_seconds':(j.finished_at-j.started_at).total_seconds() if j.finished_at and j.started_at else None,'queue_seconds':(j.started_at-j.created_at).total_seconds() if j.started_at else None} for j in jobs]}
   with (OUT/'observations.jsonl').open('a') as f:f.write(json.dumps(o,ensure_ascii=False,default=str)+'\n')
   observed.append(identifier);del pending[identifier]
  save('progress.json',{'completed':len(observed),'pending':list(pending),'updated_at':timezone.now()});print('completed',len(observed),'pending',len(pending),flush=True)
  # DB queue depth measured independently of RabbitMQ transport.
  with connection.cursor() as c:c.execute('SELECT queue,status,count(*) FROM mice_work_items GROUP BY queue,status');qs=c.fetchall()
  with (OUT/'queues.jsonl').open('a') as f:f.write(json.dumps({'at':timezone.now().isoformat(),'database':qs})+'\n')
  if pending:time.sleep(5)
 save('completion.json',{'completed':len(observed),'finished_at':timezone.now(),'configuration_unchanged':configuration()==cfg,'ocr_unchanged':ocr_config()==ocr})
if __name__=='__main__':main()
