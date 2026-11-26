"""Read-only replay of frozen extraction through production detection_evidence.
No mail ingestion, OCR, static scans, policies, incidents or database writes.
"""
import argparse
import copy
import hashlib
import json
import sys
import time
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def documents(row):
    # Unified analysis concatenates body and attachments with one newline per
    # document. Refuse ambiguous/mismatched extraction rather than guess.
    attachments = row["attachments"]
    suffix = "".join("\n" + a["text"] for a in attachments)
    full = row["text"]
    if suffix and not full.endswith(suffix):
        raise ValueError(f"{row['id']}: attachment order or combined text mismatch")
    body = full[:-len(suffix)] if suffix else full
    return [{"id": "body", "text": body}] + [
        {"id": str(a.get("id") or f"attachment-{i}"), "text": a["text"]}
        for i, a in enumerate(attachments)
    ]


def metrics(tp, fp, fn, tn):
    return dict(TP=tp, FP=fp, FN=fn, TN=tn,
                precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None,
                F1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)


def overlay(config, pack):
    result = copy.deepcopy(config)
    categories = {c["id"]: c for c in pack["categories"]}
    groups = []
    for group in result["groups"]:
        cid = group["category"]["id"]
        if cid not in categories:
            groups.append(group)
            continue
        category = categories.pop(cid)
        if not category.get("active", True):
            continue
        group["category"]["match_mode"] = category["match_mode"]
        group["category"]["name"] = category["name"]
        group["rules"] = []
        for i, rule in enumerate(category["rules"]):
            if not rule.get("enabled", True):
                continue
            meta = {"id", "kind", "title", "risk", "priority", "enabled", "version"}
            group["rules"].append(dict(id=f"{cid}:{i}", kind=rule["kind"],
                title=rule["title"], risk=rule["risk"], version="candidate",
                config={k:v for k,v in rule.items() if k not in meta}))
        groups.append(group)
    if categories:
        raise ValueError(f"Unknown category IDs in rulepack: {sorted(categories)}")
    result["groups"] = groups
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--configuration", type=Path)
    source.add_argument("--database", action="store_true", help="Read current configuration; never write")
    parser.add_argument("--rulepack", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--category", action="append", help="Repeat to limit scoring; default all annotated RU3")
    parser.add_argument("--normalizer", choices=["keep","off","low","medium","high"], default="keep")
    parser.add_argument("--require-parity", action="store_true", help="Fail if any scoped category set differs from saved live findings")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output must be a new directory")
    if args.database:
        import os
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mice.settings")
        import django
        django.setup()
        from pipeline.evidence import configuration
        config = configuration()
    else:
        raw = read_json(args.configuration)
        config = raw.get("configuration", raw)
    config = copy.deepcopy(config)
    if args.rulepack:
        config = overlay(config, read_json(args.rulepack))
    if args.normalizer != "keep":
        config["settings"]["normalizer"] = dict(enabled=args.normalizer != "off", mode="detect",
            sensitivity="high" if args.normalizer == "off" else args.normalizer)
    # Scope is explicit. No binary/static checks are invoked by analyze().
    # Retain native textual detections because built-in context can depend on them.
    from app.detection_evidence import analyze
    manifest_path = args.corpus / "manifest.jsonl"
    rows = read_rows(manifest_path)
    obs = read_rows(args.observations)
    byid = {o["id"]: o for o in obs}
    if len(byid) != len(obs) or len({r["id"] for r in rows}) != len(rows) or set(byid) != {r["id"] for r in rows}:
        raise ValueError("Manifest and observations must cover exactly the same unique IDs")
    annotated = {c for r in rows for c in r["expected_semantic_categories"] if c.startswith("pack-ru2-")}
    scope = set(args.category or annotated)
    if not scope or not scope <= annotated:
        raise ValueError("Unknown or empty annotation scope")
    # Keep all RU3 groups during replay to preserve production ordering and limits.
    counts = {c: Counter() for c in scope}
    details, mismatches = [], []
    started = time.monotonic()
    for r in rows:
        o = byid[r["id"]]
        sha = hashlib.sha256((args.corpus/r["file"]).read_bytes()).hexdigest()
        if sha != o["sha256"] or o["status"] != "ANALYZED":
            raise ValueError(f"Input hash or extraction status mismatch: {r['id']}")
        docs = documents(o)
        result = analyze(dict(text=o["text"], documents=docs, attachments=o["attachments"], configuration=config))
        findings = [f for f in result["findings"] if f["category"] in scope]
        actual = {f["category"] for f in findings}
        expected = set(r["expected_semantic_categories"]) & scope
        live = {f["category"] for f in o["analysis"]["findings"]} & scope
        if actual != live:
            mismatches.append(dict(id=r["id"], live=sorted(live), replay=sorted(actual)))
        for c in scope:
            counts[c]["TP" if c in expected & actual else "FP" if c in actual else "FN" if c in expected else "TN"] += 1
        details.append(dict(id=r["id"], expected=sorted(expected), actual=sorted(actual),
            FP=sorted(actual-expected), FN=sorted(expected-actual), findings=findings,
            normalization=result["normalization"], engine_errors=result["engine_errors"]))
    per = {c: metrics(*(counts[c][k] for k in ("TP","FP","FN","TN"))) for c in sorted(scope)}
    micro = metrics(*(sum(counts[c][k] for c in scope) for k in ("TP","FP","FN","TN")))
    elapsed = time.monotonic()-started
    summary = dict(messages=len(rows), scope=sorted(scope), micro=micro, per_category=per,
        exact_match=sum(d["expected"]==d["actual"] for d in details)/len(rows),
        live_category_set_mismatches=len(mismatches), seconds=elapsed,
        input_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (manifest_path,args.observations)},
        configuration_sha256=hashlib.sha256(json.dumps(config,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
        caveat="Frozen text replay; not end-to-end throughput or independent validation after tuning.")
    args.output.mkdir(parents=True)
    for name,value in (("metrics.json",summary),("messages.json",details),("parity.json",mismatches)):
        (args.output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if args.require_parity and mismatches:
        raise SystemExit("Live/replay parity failed; do not calibrate until explained")


if __name__ == "__main__":
    main()
