// Run: node scripts/validate_benchmark_300_v2.mjs
import fs from "node:fs";
import path from "node:path";
const root="test-data/benchmark-300-v2";
const lines=fs.readFileSync(path.join(root,"manifest.jsonl"),"utf8").trim().split("\n");
if(lines.length!==300)throw Error("Manifest should contain 300 cases");
const ids=new Set(),messageIds=new Set(),groups={};
for(const line of lines){const item=JSON.parse(line);if(ids.has(item.id))throw Error("Duplicate id "+item.id);ids.add(item.id);groups[item.group]=(groups[item.group]||0)+1;
const file=path.join(root,item.file);const eml=fs.readFileSync(file,"utf8");if(!eml.includes("X-MailFire-Benchmark-ID: "+item.id))throw Error("Missing marker "+file);
const m=eml.match(/^Message-ID: (.+)$/m);if(!m||messageIds.has(m[1]))throw Error("Message-ID duplicate "+file);messageIds.add(m[1]);
if(!Array.isArray(item.expected_semantic_categories)||typeof item.expected_no_issue!=="boolean")throw Error("Invalid annotation "+item.id);
}
for(const [group,count] of [["control",60],["pii",55],["commercial",55],["safety",45],["secrets",40],["documents",25],["mixed",20]])if(groups[group]!==count)throw Error("Group "+group+" mismatch");
const files=fs.readdirSync(path.join(root,"eml")).filter(x=>x.endsWith(".eml"));if(files.length!==300)throw Error("EML count mismatch");
console.log("OK: 300 unique manifest entries, EML, Message-IDs, expected groups and markers");
