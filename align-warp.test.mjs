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

test('drift: audio accelerates → later notes shift earlier but preserve fractional position', () => {
    // tab thinks beats are 0.5s apart; audio actually 0.5, 0.45, 0.4 (gradually faster)
    const tabBeats = [
        { time: 0.0 }, { time: 0.5 }, { time: 1.0 }, { time: 1.5 },
    ];
    const detectedBeats = [
        { time: 0.0 }, { time: 0.5 }, { time: 0.95 }, { time: 1.35 },
    ];
    const noteMidBeat2 = 0.75; // halfway between tabBeats[1] and tabBeats[2]
    const notes = [{ time: noteMidBeat2 }];

    const r = warpTabToAudioBeats({
        tabBeats, notes, sections: [], detectedBeats, k: 0, mode: 'truncate',
    });
    // New position: halfway between 0.5 and 0.95 = 0.725
    assert.equal(+r.notes[0].time.toFixed(6), 0.725);
});

test('truncate mode: more tab beats than audio → drop extras', () => {
    const tabBeats = [
        { time: 0 }, { time: 0.5 }, { time: 1.0 }, { time: 1.5 }, { time: 2.0 },
    ];
    const detectedBeats = [
        { time: 0 }, { time: 0.5 }, { time: 1.0 },
    ];
    const r = warpTabToAudioBeats({
        tabBeats, notes: [], sections: [], detectedBeats, k: 0, mode: 'truncate',
    });
    assert.equal(r.beats.length, 3);
    assert.deepEqual(r.beats.map(b => b.time), [0, 0.5, 1.0]);
});

test('extend mode: tab outlasts audio → extrapolate at last interval', () => {
    const tabBeats = [
        { time: 0 }, { time: 0.5 }, { time: 1.0 }, { time: 1.5 }, { time: 2.0 },
    ];
    const detectedBeats = [
        { time: 0 }, { time: 0.5 }, { time: 1.0 },
    ];
    const r = warpTabToAudioBeats({
        tabBeats, notes: [], sections: [], detectedBeats, k: 0, mode: 'extend',
    });
    assert.equal(r.beats.length, 5);
    // Last detected interval is 0.5; extrapolate from 1.0.
    assert.deepEqual(r.beats.map(b => +b.time.toFixed(6)), [0, 0.5, 1.0, 1.5, 2.0]);
});

test('sustain scales with its containing segment', () => {
    const tabBeats = [{ time: 0 }, { time: 0.5 }];
    const detectedBeats = [{ time: 0 }, { time: 1.0 }]; // 2x stretch
    const notes = [{ time: 0.0, sustain: 0.25 }];
    const r = warpTabToAudioBeats({
        tabBeats, notes, sections: [], detectedBeats, k: 0, mode: 'truncate',
    });
    assert.equal(+r.notes[0].sustain.toFixed(6), 0.5); // 0.25 * 2
});

test('non-zero k shifts the correspondence', () => {
    // 'extra' audio beats before tab beat 0
    const tabBeats = [{ time: 0 }, { time: 0.5 }, { time: 1.0 }];
    const detectedBeats = [
        { time: 0.1 }, { time: 0.6 }, // intro
        { time: 1.1 }, { time: 1.6 }, { time: 2.1 }, // matched to tab
    ];
    const r = warpTabToAudioBeats({
        tabBeats, notes: [], sections: [], detectedBeats, k: 2, mode: 'truncate',
    });
    assert.deepEqual(r.beats.map(b => b.time), [1.1, 1.6, 2.1]);
});

test('section snaps to nearest tab beat then takes warped position', () => {
    const tabBeats = [{ time: 0 }, { time: 0.5 }, { time: 1.0 }];
    const detectedBeats = [{ time: 0.1 }, { time: 0.7 }, { time: 1.2 }];
    const sections = [{ start_time: 0.52 }]; // nearest tab beat = idx 1 (time 0.5)
    const r = warpTabToAudioBeats({
        tabBeats, notes: [], sections, detectedBeats, k: 0, mode: 'truncate',
    });
    assert.equal(r.sections[0].start_time, 0.7);
});
