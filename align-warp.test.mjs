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
