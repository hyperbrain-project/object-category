"""Generate BIDS events.tsv files for the dynamic object-category localizer.

Design (README.md): 10 stimulus blocks per run, 6 clips x 3 s = 18 s each.
Block categories are palindromic - blocks 6-10 reverse blocks 1-5.
Fixation blocks (18 s) occupy 0-18 s, 108-126 s and 216-234 s and are left
as the implicit baseline, matching the other localizers in this project.

Filename convention, shared by every task in this project:

    events/<sid>_run<N>_<YYYYMMDD-HHMMSS>.tsv      (all lowercase)

Only *_finish.json logs are read. A *_start.json means the run was launched
but never completed; older versions of this script globbed 'logs/*.json' and
turned those empty logs into header-only events files. Logs predating the
start/finish convention are skipped too.

Subject IDs are normalised: every main.py does `sid = file.read()` with no
.strip(), so a trailing newline in ../sid.txt lands inside the filename.
Only real participants (sid######) get events.

Usage:  python3 generate_events.py      (run from this folder)
Stdlib only - no pandas/numpy required.
"""

import csv
import json
import os
import re
from glob import glob

LOG_RE = re.compile(
    r'^(?P<sid>[\s\S]+?)_run(?P<run>\d+)_(?P<ts>\d{8}-\d{6})_finish\.json$')
PARTICIPANT_RE = re.compile(r'^sid\d{6}(-me)?$')

HEADER = ['onset', 'duration', 'trial_type']

SUPERSEDED = set()


class DesignError(Exception):
    """The log does not match the documented design."""


def clean_sid(sid):
    return re.sub(r'[^a-z0-9-]', '', sid.strip().lower())


def chunks(seq, n):
    return [seq[i:i + n] for i in range(0, len(seq), n)]


def expect(stims, n):
    if len(stims) != n:
        raise DesignError('expected %d stim_events, found %d' % (n, len(stims)))


# --------------------------------------------------------------------------
# object-category: 10 blocks x 6 clips x 3 s, 3 fixation blocks. Run 234 s.
# --------------------------------------------------------------------------
OC_CATS = {'bodies', 'faces', 'objects', 'scenes', 'scrambled_objects'}
OC_RENAME = {'scrambled_objects': 'scrambled'}


def generate_events(log, warn):
    stims = log['stim_events']
    expect(stims, 60)
    rows = []
    for blk in chunks(stims, 6):
        cats = set()
        for s in blk:
            found = [p for p in s[0].replace('\\', '/').split('/') if p in OC_CATS]
            if not found:
                raise DesignError('cannot infer category from %r' % s[0])
            cats.add(OC_RENAME.get(found[0], found[0]))
        if len(cats) != 1:
            raise DesignError('block mixes categories: %s' % sorted(cats))
        rows.append([blk[0][1], blk[-1][2] - blk[0][1], cats.pop()])
    return HEADER, rows


def main():
    os.makedirs('events', exist_ok=True)
    n_ok = n_skip = n_warn = n_other = 0

    for fn in sorted(glob(os.path.join('logs', '*_finish.json'))):
        base = os.path.basename(fn)
        m = LOG_RE.match(base)
        if m is None:
            print('  SKIP %r: unparseable filename' % base)
            n_skip += 1
            continue

        sid = clean_sid(m.group('sid'))
        if not PARTICIPANT_RE.match(sid):
            n_other += 1
            continue

        name = '%s_run%s_%s.tsv' % (sid, m.group('run'), m.group('ts'))
        if name in SUPERSEDED:
            n_other += 1
            continue

        with open(fn) as f:
            log = json.load(f)

        messages = []
        try:
            header, rows = generate_events(log, messages.append)
        except DesignError as e:
            print('  SKIP %r: %s' % (base, e))
            n_skip += 1
            continue

        if messages:
            n_warn += 1
            for msg in messages:
                print('  WARN %r: %s' % (base, msg))

        with open(os.path.join('events', name), 'w', newline='') as f:
            w = csv.writer(f, delimiter='\t')
            w.writerow(header)
            w.writerows(rows)
        n_ok += 1

    print('%d events files written, %d skipped, %d with warnings, %d excluded'
          % (n_ok, n_skip, n_warn, n_other))


if __name__ == '__main__':
    main()
