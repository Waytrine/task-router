"""Rebuild the v1 synthetic splits from data/source/*.json. No model, network or training is used.

The split search is seeded, so the output must match data/manifest.json byte for byte.
"""
import argparse
import hashlib
import json
import random
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'data'
DEFAULTS = dict(task_type='conversation', difficulty='simple', web_search='no',
                input_modality='text', document_read='no', media_output='none',
                project_access='none', run_commands='no', browser_use='no', executor_intent='none')
INTENTS = dict(none='none', invoke='assign', avoid='exclude', discuss='mention_only',
               reassign='reassign', unclear='unclear')
TARGETS = dict(train=120, validation=30, calibration=20, test=30)

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def normalize(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())

def load_sources():
    questions = read_json(DATA / 'questions.json')
    records = []
    for name, count in [('coding', 70), ('general', 70), ('media', 60)]:
        part = read_json(DATA / 'source' / (name + '.json'))
        if len(part) != count:
            raise ValueError(f'{name}: expected {count}, got {len(part)}')
        records.extend(part)
    ids = set()
    for rec in records:
        assert rec['group_id'] not in ids, rec['group_id']
        ids.add(rec['group_id'])
        for field in ('zh', 'en', 'reason_zh', 'topic'):
            assert isinstance(rec[field], str) and rec[field].strip(), (rec['group_id'], field)
        for prefix in ('context', 'reference'):
            assert bool(rec.get(prefix + '_zh')) == bool(rec.get(prefix + '_en')), rec['group_id']
        raw = dict(rec['labels'])
        if 'named_agent' in raw:
            raw['executor_intent'] = INTENTS[raw.pop('named_agent')]
        assert not set(raw) - set(DEFAULTS), (rec['group_id'], raw)
        labels = DEFAULTS | raw
        for head, value in labels.items():
            assert value in questions[head]['criteria'], (rec['group_id'], head, value)
        rec['expanded_labels'] = labels
        rec['family_id'] = rec.get('family_id') or rec['group_id']
        assert isinstance(rec['tags'], list), rec['group_id']
        for att in rec.get('attachments', []):
            assert set(att) == {'kind', 'name'} and att['kind'] in ['image','audio','video','document'], att
    return records, questions

def pick_subset(families, target, rng):
    order = list(families)
    rng.shuffle(order)
    reachable = {0: []}
    for key in order:
        size = len(families[key])
        for total, selected in list(reachable.items())[::-1]:
            nxt = total + size
            if nxt <= target and nxt not in reachable:
                reachable[nxt] = selected + [key]
        if target in reachable:
            return reachable[target]
    raise ValueError('Cannot split whole families to requested size')

def split_records(records):
    families = defaultdict(list)
    for row in records:
        families[row['family_id']].append(row)
    total_labels = Counter((k, v) for row in records for k, v in row['expanded_labels'].items())
    best = None
    for trial in range(600):
        rng = random.Random(20261026 + trial)
        remaining = dict(families)
        allocation = {}
        for split, target in TARGETS.items():
            keys = pick_subset(remaining, target, rng)
            allocation[split] = [r for key in keys for r in remaining.pop(key)]
        score = 0
        for split, rows in allocation.items():
            counts = Counter((k,v) for r in rows for k,v in r['expanded_labels'].items())
            for label, n in total_labels.items():
                expected = n * len(rows) / len(records)
                score += (counts[label] - expected)**2 / (expected + 1)
                if split == 'train' and counts[label] == 0:
                    score += 10000
                if split in ('validation', 'test') and n >= 3 and counts[label] == 0:
                    score += 100
        if best is None or score < best[0]:
            best = (score, allocation)
    # Improve rare-class coverage without ever splitting a family. Random splits
    # alone can keep all three scarce positive families in training.
    def quality(allocation):
        result = 0
        for split, rows in allocation.items():
            counts = Counter((k,v) for r in rows for k,v in r['expanded_labels'].items())
            for label, n in total_labels.items():
                expected = n * len(rows) / len(records)
                result += (counts[label] - expected)**2 / (expected + 1)
                if split == 'train' and counts[label] == 0:
                    result += 10000
                if split in ('validation', 'test') and n >= 3 and counts[label] == 0:
                    result += 100
        return result
    owners = {r['family_id']:s for s,rs in best[1].items() for r in rs}
    keys = list(families)
    rng = random.Random(48261026)
    current_score = quality(best[1])
    for _ in range(12000):
        a,b = rng.sample(keys,2)
        if owners[a] == owners[b] or len(families[a]) != len(families[b]):
            continue
        owners[a],owners[b] = owners[b],owners[a]
        proposal = {s:[r for f,rs in families.items() if owners[f]==s for r in rs] for s in TARGETS}
        candidate_score = quality(proposal)
        if candidate_score <= current_score:
            best = (candidate_score,proposal)
            current_score = candidate_score
        else:
            owners[a],owners[b] = owners[b],owners[a]
    return best[1]

def make_rows(records, questions, allocation):
    owners = {r['group_id']: split for split, rows in allocation.items() for r in rows}
    rows = []
    for r in records:
        for lang in ['zh','en']:
            # Only these five fields reach the model. No gold labels, tags or rationales.
            state = dict(message=r[lang], recent_context=r.get('context_'+lang,''),
                         reference_text=r.get('reference_'+lang,''),
                         attachments=r.get('attachments',[]),
                         candidate_executors=r.get('candidate_executors',[]))
            rows.append(dict(id=r['group_id']+'-'+lang, group_id=r['group_id'],
                             family_id=r['family_id'], language=lang, tags=r['tags'],
                             split=owners[r['group_id']], state=state, questions=questions,
                             expected=r['expanded_labels']))
    return rows

def validate_rows(rows):
    owners = {}
    ids = set()
    for row in rows:
        assert row['id'] not in ids, row['id']
        ids.add(row['id'])
        assert set(row['state']) == {'message','recent_context','reference_text','attachments','candidate_executors'}
        # Same wording is allowed only if the remaining context genuinely differs.
        state_key = normalize(json.dumps(row['state'], ensure_ascii=False))
        for key in [('group',row['group_id']), ('family',row['family_id']), ('input',state_key)]:
            if key in owners and owners[key] != row['split']:
                raise ValueError(f'Cross-split overlap: {key}')
            owners[key] = row['split']
    groups = Counter(r['group_id'] for r in rows)
    assert set(groups.values()) == {2}
    return dict(rows=len(rows), scenarios=len(groups), families=len({r['family_id'] for r in rows}),
                cross_split_group_overlap=0, cross_split_family_overlap=0, cross_split_input_overlap=0)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True,
                        help='New or empty directory for the rebuilt data/*.jsonl, manifest.json and review/*.json')
    out = Path(parser.parse_args().out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError('Use a new or empty --out directory; the committed data/ is never overwritten')
    (out / 'data').mkdir(parents=True, exist_ok=True)
    (out / 'review').mkdir(exist_ok=True)
    records, questions = load_sources()
    allocation = split_records(records)
    rows = make_rows(records, questions, allocation)
    audit = validate_rows(rows)
    for split in ['all', *TARGETS]:
        subset = rows if split == 'all' else [r for r in rows if r['split'] == split]
        # The published splits (and the hashes in data/manifest.json) use CRLF line endings.
        with (out/'data'/f'{split}.jsonl').open('w', encoding='utf-8', newline='\r\n') as f:
            for row in subset:
                f.write(json.dumps(row, ensure_ascii=False, separators=(',',':'))+'\n')
    distribution = {}
    for split in TARGETS:
        subset = [r for r in rows if r['split']==split]
        distribution[split] = dict(rows=len(subset), languages=dict(Counter(r['language'] for r in subset)),
            heads={h:dict(Counter(r['expected'][h] for r in subset)) for h in DEFAULTS})
    write_json(out/'review'/'validation.json', audit | dict(distribution=distribution,
        note='Offline schema/split checks only. No tokenizer, model inference or GPU run.'))
    write_json(out/'review'/'coverage-gaps.json', [dict(split=s,head=h,label=v)
        for s,d in distribution.items() for h,q in questions.items() for v in q['criteria']
        if not d['heads'][h].get(v)])
    write_json(out/'manifest.json', dict(dataset_version='pugport-routing-synthetic-v1', **audit,
        split_rows={s:distribution[s]['rows'] for s in TARGETS},
        sha256={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((out/'data').glob('*.jsonl'))}))
    print(json.dumps(audit | dict(split_rows={s:distribution[s]['rows'] for s in TARGETS}), indent=2))

if __name__ == '__main__':
    main()
