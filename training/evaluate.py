"""Explicit, offline-checkpoint inference and auditable label scoring.

Importing this file or using --help never imports Laya or loads a model.
"""
import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from time import perf_counter

def read_rows(path):
    rows = [json.loads(s) for s in Path(path).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
    if not rows or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Empty data or duplicate IDs')
    return rows

def write_json(path, value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def score(gold, predictions):
    actual = {p['id']:p for p in predictions}
    if len(actual)!=len(predictions) or set(actual)!= {r['id'] for r in gold}:
        raise ValueError('Prediction IDs must match gold exactly; missing cases are never silently dropped')
    heads = list(gold[0]['expected'])
    report = {'rows':len(gold),'heads':{}}
    for head in heads:
        labels = list(gold[0]['questions'][head]['criteria'])
        pairs = [(r['expected'][head],actual[r['id']].get('predicted',{}).get(head)) for r in gold]
        per_label = {}
        for label in labels:
            support = sum(y==label for y,p in pairs)
            tp = sum(y==label and p==label for y,p in pairs)
            fp = sum(y!=label and p==label for y,p in pairs)
            fn = support-tp
            per_label[label] = {'support':support,'recall':tp/support if support else None,
                                'precision':tp/(tp+fp) if tp+fp else None,
                                'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}
        supported = [v['f1'] or 0 for v in per_label.values() if v['support']]
        report['heads'][head] = {'accuracy':sum(y==p for y,p in pairs)/len(pairs),
            'macro_f1_supported':statistics.mean(supported), 'per_label':per_label,
            'invalid_or_abstained':sum(p not in labels for y,p in pairs)}
    report['all_heads_exact_match'] = sum(all(actual[r['id']].get('predicted',{}).get(h)==r['expected'][h]
                                              for h in heads) for r in gold)/len(gold)
    report['mean_head_accuracy'] = statistics.mean(v['accuracy'] for v in report['heads'].values())
    report['languages'] = {}
    for lang in sorted({r['language'] for r in gold}):
        subset = [r for r in gold if r['language']==lang]
        report['languages'][lang] = {h:sum(actual[r['id']].get('predicted',{}).get(h)==r['expected'][h]
                                                  for r in subset)/len(subset) for h in heads}
    report['note'] = 'Synthetic-label agreement, not production quality or calibrated confidence. Translations are correlated; inspect family-level mistakes.'
    return report

def majority_predictions(gold, train):
    heads = list(gold[0]['expected'])
    values = {h:Counter(r['expected'][h] for r in train).most_common(1)[0][0] for h in heads}
    return [dict(id=r['id'],predicted=values) for r in gold]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    run = sub.add_parser('run')
    run.add_argument('data'); run.add_argument('--model-dir',required=True)
    run.add_argument('--out',required=True); run.add_argument('--device',default='cuda')
    run.add_argument('--train-data')
    compare = sub.add_parser('compare')
    compare.add_argument('before'); compare.add_argument('after'); compare.add_argument('--out',required=True)
    args = parser.parse_args()
    if args.command=='compare':
        before,after=[json.loads(Path(p).read_text(encoding='utf-8')) for p in [args.before,args.after]]
        if before['data_sha256']!=after['data_sha256']:
            raise ValueError('Compare only the exact same dataset bytes')
        lines=['# Baseline vs fine-tuned','', '| Head | Before | After | Difference |','|---|---:|---:|---:|']
        for h in before['heads']:
            b,a=before['heads'][h]['accuracy'],after['heads'][h]['accuracy']
            lines.append(f'| {h} | {b:.3f} | {a:.3f} | {a-b:+.3f} |')
        lines += ['', 'Accuracy alone can hide rare-class regressions. Inspect macro F1, per-label recall and mistakes.csv.',
                  'These are small synthetic evaluation sets; no production superiority is established.']
        Path(args.out).write_text('\n'.join(lines)+'\n',encoding='utf-8')
        print('\n'.join(lines)); return
    rows = read_rows(args.data)
    checkpoint = Path(args.model_dir).resolve()
    if not (checkpoint/'rl_agent_config.json').is_file():
        raise ValueError('Use an already downloaded local Laya checkpoint directory')
    out = Path(args.out)
    out.mkdir(parents=True,exist_ok=True)
    if (out/'predictions.jsonl').exists():
        raise FileExistsError('Choose a fresh output directory to preserve baseline evidence')
    import laya
    start=perf_counter(); agent=laya.load(str(checkpoint),device=args.device); load_seconds=perf_counter()-start
    predictions=[]
    with (out/'predictions.jsonl').open('w',encoding='utf-8') as stream:
        for n,row in enumerate(rows,1):
            start=perf_counter()
            try:
                raw=agent.predict(row['state'],row['questions'])
                answers=raw.get('answers',{})
                predicted={}
                for h,q in row['questions'].items():
                    answer=answers.get(h,{})
                    value=answer.get('choice') if isinstance(answer,dict) else None
                    predicted[h] = value if value in q['criteria'] and answer.get('abstention')!='abstained' else None
                item=dict(id=row['id'],predicted=predicted,raw=raw,error=None)
            except Exception as exc:
                item=dict(id=row['id'],predicted={},raw=None,error=f'{type(exc).__name__}: {exc}')
            item['predict_ms']=round((perf_counter()-start)*1000,3)
            predictions.append(item)
            stream.write(json.dumps(item,ensure_ascii=False,allow_nan=False)+'\n'); stream.flush()
            print(f'{n}/{len(rows)} {row["id"]}: {item["predict_ms"]} ms'+(' ERROR' if item['error'] else ''),flush=True)
    report=score(rows,predictions)
    times=[p['predict_ms'] for p in predictions if not p['error']]
    report.update(data_sha256=hashlib.sha256(Path(args.data).read_bytes()).hexdigest(),
                  model_dir=str(checkpoint),device=args.device,load_seconds=load_seconds,
                  failures=sum(bool(p['error']) for p in predictions),
                  first_case_ms=predictions[0]['predict_ms'],
                  successful_p50_ms=statistics.median(times) if times else None,
                  successful_p95_ms=sorted(times)[max(0,math.ceil(.95*len(times))-1)] if times else None)
    if args.train_data:
        report['majority_baseline']=score(rows,majority_predictions(rows,read_rows(args.train_data)))
    write_json(out/'report.json',report)
    with (out/'mistakes.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f); writer.writerow(['id','language','head','expected','predicted','message','recent_context','error'])
        for row,p in zip(rows,predictions):
            for h,expected in row['expected'].items():
                actual=p['predicted'].get(h)
                if actual!=expected:
                    writer.writerow([row['id'],row['language'],h,expected,actual,row['state']['message'],
                                     row['state']['recent_context'],p['error']])
    print(json.dumps({k:report[k] for k in ['rows','mean_head_accuracy','all_heads_exact_match','failures']},indent=2))

if __name__=='__main__':
    main()
