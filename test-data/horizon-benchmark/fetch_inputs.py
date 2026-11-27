"""Retrieve immutable historical inputs into external storage, without checkout changes."""
import subprocess

from common import INPUTS, ROOT, save

SOURCES = {
    'b400': ('origin/test/benchmark-400-v1', ['test-data/benchmark-400-v1/']),
    'b500': ('origin/test/benchmark-500-holdout', ['test-data/benchmark-500-v1/']),
    'ml': ('origin/test/ml-category-benchmark', ['test-data/results-ml-category-benchmark/']),
    'baseline': ('origin/results/benchmark500-v1', ['test-data/results-benchmark500-v1/', 'test-data/benchmark-500-v1/manifest.jsonl']),
}


def main():
    frozen = ROOT / 'test-data/horizon-benchmark/source-commits.json'
    commits = {}
    if frozen.exists():
        from common import load
        commits = load(frozen)
    INPUTS.mkdir(parents=True, exist_ok=True)
    for name, (ref, prefixes) in SOURCES.items():
        commit = commits.get(name) or subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', ref], text=True).strip()
        commits[name] = commit
        paths = subprocess.check_output(['git', '-C', str(ROOT), 'ls-tree', '-r', '--name-only', commit], text=True).splitlines()
        for path in paths:
            if any(path.startswith(prefix) for prefix in prefixes):
                target = INPUTS / name / path
                raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{commit}:{path}'])
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    assert target.read_bytes() == raw
                else:
                    target.write_bytes(raw)
    ref = commits.get('b400_observations') or subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'origin/results/benchmark400-20261126-B'], text=True).strip()
    commits['b400_observations'] = ref
    target = INPUTS / 'b400-observations.jsonl'
    raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{ref}:test-data/results-benchmark400-20261126/B/observations.jsonl'])
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    if not frozen.exists():
        save(frozen, commits)


if __name__ == '__main__':
    main()