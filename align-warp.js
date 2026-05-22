// align-warp.js
//
// Pure functions for warping a tab beat grid onto detected audio beats.
// Loaded both by the browser (via <script src=...>) and by Node tests
// (via require/import). UMD-lite pattern — no module bundler required.
//
// See specs/002-auto-align-editor-side/spec.md for the algorithm.

(function (root, factory) {
    const __exports = factory();
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = __exports;
    } else {
        Object.assign(root, __exports);
    }
}(typeof window !== 'undefined' ? window : globalThis, function () {

    function warpTabToAudioBeats(_args) {
        throw new Error('not implemented');
    }

    function findFirstDownbeat(_detectedBeats, _offsetSec) {
        throw new Error('not implemented');
    }

    function computeDriftSummary(_oldBeats, _newBeats) {
        throw new Error('not implemented');
    }

    return { warpTabToAudioBeats, findFirstDownbeat, computeDriftSummary };
}));
