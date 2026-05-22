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
