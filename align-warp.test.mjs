// align-warp.test.mjs — Node native test runner. Run via:
//   node --test align-warp.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { warpTabToAudioBeats } = require('./align-warp.js');

test('module loads', () => {
    assert.equal(typeof warpTabToAudioBeats, 'function');
});

test('identity: audioBeats == tabBeats, k=0 → unchanged', () => {
    const tabBeats = [{ time: 0.5, measure: 1 }, { time: 1.0, measure: 0 }, { time: 1.5, measure: 0 }];
    const detectedBeats = [{ time: 0.5 }, { time: 1.0 }, { time: 1.5 }];
    const notes = [
        { time: 0.5 }, { time: 0.75 }, { time: 1.25 },
    ];
    const sections = [{ start_time: 0.5 }];

    const result = warpTabToAudioBeats({
        tabBeats, notes, sections, detectedBeats, k: 0, mode: 'truncate',
    });

    assert.deepEqual(result.beats.map(b => b.time), [0.5, 1.0, 1.5]);
    assert.deepEqual(result.notes.map(n => n.time), [0.5, 0.75, 1.25]);
    assert.deepEqual(result.sections.map(s => s.start_time), [0.5]);
});

test('uniform 1.1x stretch: notes and beats both scale', () => {
    const tabBeats = [
        { time: 0.0 }, { time: 0.5 }, { time: 1.0 }, { time: 1.5 }, { time: 2.0 },
    ];
    const detectedBeats = [
        { time: 0.0 }, { time: 0.55 }, { time: 1.1 }, { time: 1.65 }, { time: 2.2 },
    ];
    const notes = [{ time: 0.25 }, { time: 0.75 }, { time: 1.5 }];

    const r = warpTabToAudioBeats({
        tabBeats, notes, sections: [], detectedBeats, k: 0, mode: 'truncate',
    });
    assert.deepEqual(r.beats.map(b => +b.time.toFixed(6)), [0, 0.55, 1.1, 1.65, 2.2]);
    // Each note's fractional position in its segment is preserved:
    // 0.25 is halfway between 0 and 0.5 → halfway between 0 and 0.55 → 0.275
    // 0.75 is halfway between 0.5 and 1.0 → halfway between 0.55 and 1.1 → 0.825
    // 1.5 is exactly at tabBeats[3] → snaps to detectedBeats[3] = 1.65
    assert.deepEqual(r.notes.map(n => +n.time.toFixed(6)), [0.275, 0.825, 1.65]);
});
