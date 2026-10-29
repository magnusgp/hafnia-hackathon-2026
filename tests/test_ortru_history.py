"""Append-only decision history (with the migration of the earlier one-row store) and event-level grouping."""
import sqlite3
import unittest

from ortru import events
from ortru.exceptions import GAP, Reviews, Stale, build_view
from tests.test_ortru import Base

LEGACY = dict(exception_id='b586966c61d7460c997bcc47b0a3ce38', revision=2, status='review_requested', verdict='visible',
              note='Reviewed by an AI reviewer. The footage shows a person on the platform edge.', outcome='escalate', watched=1,
              at='2026-10-29T14:42:22.162908+00:00', reviewer='claude_ai_demo')
FIELDS = ('exception_id', 'revision', 'status', 'verdict', 'note', 'outcome', 'watched', 'at', 'reviewer')
OLD_SCHEMA = ('CREATE TABLE decisions(exception_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, status TEXT NOT NULL, verdict TEXT, '
              'note TEXT, outcome TEXT, watched INTEGER NOT NULL, at TEXT NOT NULL, reviewer TEXT NOT NULL DEFAULT \'operator\')')
OLDEST_SCHEMA = OLD_SCHEMA.replace(", reviewer TEXT NOT NULL DEFAULT 'operator'", '')


class History(Base):
    def exception(self):
        eng = self.engine()
        w, job = self.run_watch(eng)
        return eng, job['id']

    def body(self, rev, **over):
        return dict(dict(expectedRevision=rev, verdict='visible', note='Person on the track bed', watchedFootage=True, outcome='escalate'), **over)

    def legacy_engine(self, row=LEGACY, schema=OLD_SCHEMA):
        eng = self.engine()
        with eng.db() as db:
            db.execute(schema)
            cols = [c[1] for c in db.execute('PRAGMA table_info(decisions)')]
            db.execute(f"INSERT INTO decisions({','.join(cols)}) VALUES ({','.join('?'*len(cols))})", tuple(row[k] for k in cols))
        return eng

    def test_every_revision_is_kept_and_cannot_be_changed_or_deleted(self):
        eng, eid = self.exception()
        r = Reviews(eng)
        view = build_view(eng, eid, r.get(eid))
        r.decide(eid, self.body(0, note='first'), view)
        r.decide(eid, self.body(1, note='second', outcome='confirm_local'), view)
        h = r.history(eid)
        self.assertEqual([(x['revision'], x['note'], x['available']) for x in h], [(1, 'first', True), (2, 'second', True)])
        self.assertEqual(r.get(eid)['note'], 'second')
        with eng.db() as db:
            with self.assertRaisesRegex(sqlite3.IntegrityError, 'append-only'):
                db.execute("UPDATE decision_revisions SET note='edited'")
            with self.assertRaisesRegex(sqlite3.IntegrityError, 'append-only'):
                db.execute('DELETE FROM decision_revisions')
            with self.assertRaises(sqlite3.IntegrityError):  # a stored revision number cannot be taken again
                db.execute("INSERT INTO decision_revisions VALUES (?,2,'dismissed',NULL,'',NULL,1,'x','operator')", (eid,))
        self.assertEqual([x['note'] for x in r.history(eid)], ['first', 'second'])

    def test_stale_revision_is_refused_and_writes_nothing(self):
        eng, eid = self.exception()
        r = Reviews(eng)
        view = build_view(eng, eid, r.get(eid))
        r.decide(eid, self.body(0), view)
        with self.assertRaises(Stale):
            r.decide(eid, self.body(0, note='late'), view)
        self.assertEqual(len(r.history(eid)), 1)

    def test_migration_preserves_revision_two_exactly_and_invents_no_revision_one(self):
        eng = self.legacy_engine()
        r = Reviews(eng)
        got = r.get(LEGACY['exception_id'])
        keys = ('revision', 'status', 'verdict', 'note', 'outcome', 'at', 'reviewer')
        self.assertEqual({k: got[k] for k in keys}, {k: LEGACY[k] for k in keys})
        with eng.db() as db:
            self.assertEqual([dict(x) for x in db.execute('SELECT * FROM decision_revisions')], [LEGACY])  # the row that was there, nothing else
        h = r.history(LEGACY['exception_id'])
        self.assertEqual([(x['revision'], x['available']) for x in h], [(1, False), (2, True)])
        self.assertEqual(h[0]['reason'], GAP)
        self.assertNotIn('note', h[0])
        Reviews(eng)  # opening again changes nothing
        with eng.db() as db:
            self.assertEqual([dict(x) for x in db.execute('SELECT * FROM decision_revisions')], [LEGACY])
            self.assertEqual(dict(db.execute('SELECT * FROM decisions').fetchone()), LEGACY)

    def test_old_store_is_frozen(self):
        eng = self.legacy_engine()
        Reviews(eng)
        with eng.db() as db:
            for sql in ("UPDATE decisions SET note='x'", 'DELETE FROM decisions',
                        "INSERT INTO decisions VALUES ('z',1,'dismissed',NULL,'',NULL,1,'x','operator')"):
                with self.assertRaisesRegex(sqlite3.IntegrityError, 'frozen'):
                    db.execute(sql)

    def test_older_store_without_a_reviewer_column_migrates_as_operator(self):
        eng = self.legacy_engine(dict(LEGACY, reviewer='operator'), OLDEST_SCHEMA)
        self.assertEqual(Reviews(eng).get(LEGACY['exception_id'])['reviewer'], 'operator')

    def test_decision_after_migration_appends_and_leaves_revision_two_untouched(self):
        eng, eid = self.exception()
        with eng.db() as db:
            db.execute(OLD_SCHEMA)
            db.execute('INSERT INTO decisions VALUES (?,2,?,?,?,?,1,?,?)',
                       (eid, LEGACY['status'], LEGACY['verdict'], LEGACY['note'], LEGACY['outcome'], LEGACY['at'], LEGACY['reviewer']))
        r = Reviews(eng)
        view = build_view(eng, eid, r.get(eid))
        self.assertTrue(view['provenance']['human'].startswith('Reviewed by Claude'))
        with self.assertRaises(Stale):
            r.decide(eid, self.body(1), view)
        r.decide(eid, self.body(2, note='operator review', reviewer='operator', outcome='dismiss', verdict='unclear'), view)
        h = r.history(eid)
        self.assertEqual([(x['revision'], x['available']) for x in h], [(1, False), (2, True), (3, True)])
        self.assertEqual((h[1]['note'], h[1]['at'], h[1]['reviewer']), (LEGACY['note'], LEGACY['at'], 'claude_ai_demo'))
        self.assertEqual(r.get(eid)['revision'], 3)


def sig(id, start, end, position=0.99, mkv='m1', boxes=None, focus='f1'):
    return dict(id=id, focus=focus, start=start, end=end, position=position, mkv=mkv,
                boxes=boxes if boxes is not None else [[.1, .1, .2, .2]]*4+[None])


T = [f'2026-10-29T1{h}:00:00Z' for h in range(10)]


class Events(unittest.TestCase):
    def test_same_clip_replayed_at_the_same_cycle_position_is_a_recurrence(self):
        a, b = sig('a', T[0], '2026-10-29T10:00:12Z'), sig('b', T[1], '2026-10-29T11:00:12Z')
        self.assertEqual(events.relation(a, b), 'recurrence')
        (g,) = events.groups([b, a])
        self.assertEqual((g['members'], g['relations']), (['a', 'b'], dict(b='recurrence')))

    def test_overlapping_windows_of_one_focus_are_one_occurrence(self):
        a = sig('a', T[0], '2026-10-29T10:00:12Z', mkv='x')
        b = sig('b', '2026-10-29T10:00:06Z', '2026-10-29T10:00:18Z', mkv='y', position=7.0)
        self.assertEqual(events.relation(a, b), 'same_occurrence')

    def test_distinct_events_are_never_merged(self):
        base = sig('a', T[0], '2026-10-29T10:00:12Z')
        cases = {'other camera or watch focus': sig('b', T[1], '2026-10-29T11:00:12Z', focus='f2'),
                 'same cycle position, different content': sig('b', T[1], '2026-10-29T11:00:12Z', mkv='m2', boxes=[[.5, .5, .7, .9]]*4+[None]),
                 'same content, different cycle position': sig('b', T[1], '2026-10-29T11:00:12Z', position=7.5),
                 'content match but no measured cycle position': sig('b', T[1], '2026-10-29T11:00:12Z', position=None),
                 'a different person track': sig('b', T[1], '2026-10-29T11:00:12Z', mkv='m2', boxes=[[.1, .1, .2, .3]]*4+[None])}
        for label, other in cases.items():
            with self.subTest(label):
                self.assertIsNone(events.relation(base, other))
                self.assertEqual(len(events.groups([base, other])), 2)

    def test_box_match_needs_enough_samples_and_tolerates_small_differences(self):
        few = [[.1, .1, .2, .2]]*2+[None]*3
        self.assertIsNone(events.relation(sig('a', T[0], T[0], mkv='m1', boxes=few), sig('b', T[1], T[1], mkv='m2', boxes=few)))
        near = [[.105, .1, .2, .205]]*4+[None]
        self.assertEqual(events.relation(sig('a', T[0], '2026-10-29T10:00:12Z'), sig('b', T[1], '2026-10-29T11:00:12Z', mkv='m2', boxes=near)),
                         'recurrence')

    def test_chain_of_recurrences_is_one_event_and_nothing_is_dropped(self):
        sigs = [sig(c, T[i], f'2026-10-29T1{i}:00:12Z') for i, c in enumerate('abcd')]
        sigs.append(sig('z', T[5], '2026-10-29T15:00:12Z', focus='other'))
        gs = events.groups(sigs)
        self.assertEqual(sorted(len(g['members']) for g in gs), [1, 4])
        self.assertEqual(sorted(m for g in gs for m in g['members']), sorted(s['id'] for s in sigs))
        self.assertEqual(len({g['key'] for g in gs}), 2)


class EventsInApp(Base):
    def test_signature_comes_from_the_verified_assessment(self):
        eng = self.engine()
        w, job = self.run_watch(eng)
        view = build_view(eng, job['id'])
        s = events.signature(view, eng.dir(job['id']))
        self.assertEqual((s['id'], s['start']), (job['id'], view['interval'][0]))
        self.assertEqual(len(s['boxes']), len(view['vision']['samples']))
        self.assertTrue(s['mkv'])


if __name__ == '__main__':
    unittest.main()
