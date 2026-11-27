#!/bin/sh
. "$(dirname "$0")/common.sh"
dc exec -T web python manage.py check
dc exec -T web python -c 'import urllib.request; assert urllib.request.urlopen("http://localhost:8000/api/health").status == 200'
dc exec -T web python manage.py shell -c 'from records.models import Message,Attachment,Incident,Audit,Category,CategoryRule; assert not any(m.objects.exists() for m in (Message,Attachment,Incident,Audit)); assert Category.objects.exists(); assert CategoryRule.objects.exists(); print("Configuration present; no messages, attachments, incidents or audit")'
dc exec -T neural python -c 'from transformers import AutoTokenizer,AutoModelForSequenceClassification; p="/opt/horizon"; t=AutoTokenizer.from_pretrained(p,local_files_only=True); m=AutoModelForSequenceClassification.from_pretrained(p,local_files_only=True); print(m(**t("проверка", "Это проверка",return_tensors="pt")).logits.detach().tolist())'
dc exec -T neural python -c 'from sentence_transformers import SentenceTransformer; m=SentenceTransformer("/opt/neural-models/base-rubert",local_files_only=True); assert len(m.encode(["проверка"])[0]) > 0; m=SentenceTransformer("/opt/neural-models/base-setfit",local_files_only=True); assert len(m.encode(["проверка"])[0]) > 0; print("RuBERT/SetFit local inference OK")'
dc exec -T ocr-parser python -c 'import urllib.request; assert urllib.request.urlopen("http://localhost:8090/health").status == 200; from rapidocr import RapidOCR; engine=RapidOCR(); print("RapidOCR local initialization OK")'
dc ps