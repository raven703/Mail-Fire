"""Preserve concurrent-run failures and recover them serially without tuning."""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'test-data/results-benchmark350-ru3-calibrated'


def main():
    while not (OUT / 'completion.json').exists():
        time.sleep(10)
    complete = json.loads((OUT / 'completion.json').read_text())
    assert complete['completed'] == 350 and not complete['pending']
    original = OUT / 'observations-first-pass.jsonl'
    if original.exists():
        raise ValueError('Recovery already started; do not overwrite history')
    original.write_bytes((OUT / 'observations.jsonl').read_bytes())
    observations = [json.loads(x) for x in original.read_text().splitlines()]
    for index, observation in enumerate(observations):
        if observation['evaluation_id']:
            continue
        destination = OUT / 'recovery' / observation['id']
        subprocess.run([sys.executable, str(ROOT / 'scripts/benchmark350_live.py'),
                        '--id', observation['id'], '--output', str(destination), '--timeout', '900'], check=True)
        recovered = [json.loads(x) for x in (destination / 'observations.jsonl').read_text().splitlines()]
        assert len(recovered) == 1 and recovered[0]['evaluation_id'], observation['id']
        recovered[0]['first_pass_failed'] = True
        recovered[0]['first_pass_seconds'] = observation['seconds']
        observations[index] = recovered[0]
        print('recovered', observation['id'], flush=True)
    temp = OUT / 'observations-recovered.jsonl'
    temp.write_text(''.join(json.dumps(o, ensure_ascii=False)+'\n' for o in observations))
    temp.replace(OUT / 'observations.jsonl')
    (OUT / 'recovery-completion.json').write_text(json.dumps({'completed': 350,
        'recovered': sum(bool(o.get('first_pass_failed')) for o in observations)}, indent=2))


if __name__ == '__main__':
    main()