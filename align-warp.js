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

    /**
     * Warp a tab beat grid onto detected audio beats.
     * @param {object} args
     * @param {{time:number, measure?:number}[]} args.tabBeats - current tab beats, sorted
     * @param {{time:number, sustain?:number}[]} args.notes - notes to re-time
     * @param {{start_time:number}[]} args.sections - sections to re-time
     * @param {{time:number, downbeat?:boolean}[]} args.detectedBeats - audio beats from provider
     * @param {number} args.k - first-beat correspondence (0-indexed audio beat for tab beat 0)
     * @param {'truncate'|'extend'} args.mode - what to do when audio beats run out
     * @returns {{beats:Array, notes:Array, sections:Array}}
     */
    function warpTabToAudioBeats({ tabBeats, notes, sections, detectedBeats, k, mode }) {
        const N = tabBeats.length;
        const M = detectedBeats.length;

        // Step 1 — warp tab beats by index.
        const newBeats = [];
        for (let i = 0; i < N; i++) {
            const j = k + i;
            if (j < M) {
                newBeats.push({ ...tabBeats[i], time: detectedBeats[j].time });
            } else if (mode === 'extend') {
                // Extrapolate at the last detected interval.
                const last = detectedBeats[M - 1].time;
                const prev = detectedBeats[M - 2].time;
                const step = last - prev;
                const beyond = (i - (M - 1 - k));
                newBeats.push({ ...tabBeats[i], time: last + beyond * step });
            } // truncate: drop this beat (do nothing)
        }

        // Step 2 — warp note times via segment-relative interpolation.
        const T = tabBeats.map(b => b.time);
        const Tprime = newBeats.map(b => b.time);
        const N2 = newBeats.length;

        const newNotes = notes.map(n => {
            if (N2 < 2) return { ...n };
            // Find segment i such that T[i] <= n.time < T[i+1]; if before T[0] or after T[N-1], rigid shift.
            if (n.time < T[0]) {
                return { ...n, time: n.time + (Tprime[0] - T[0]) };
            }
            // Bounds: we can only interpolate using indices that exist in BOTH T and Tprime.
            const maxIdx = Math.min(T.length, N2) - 1;
            if (n.time >= T[maxIdx]) {
                return { ...n, time: n.time + (Tprime[maxIdx] - T[maxIdx]) };
            }
            let i = 0;
            for (; i < maxIdx; i++) {
                if (T[i] <= n.time && n.time < T[i + 1]) break;
            }
            const span = T[i + 1] - T[i];
            const f = span === 0 ? 0 : (n.time - T[i]) / span;
            const newSpan = Tprime[i + 1] - Tprime[i];
            const newTime = Tprime[i] + f * newSpan;
            const out = { ...n, time: newTime };
            if (typeof n.sustain === 'number' && n.sustain > 0 && span > 0) {
                out.sustain = n.sustain * (newSpan / span);
            }
            return out;
        });

        // Step 3 — warp sections: snap to nearest tab beat, then take same-index entry from newBeats.
        const newSections = sections.map(s => {
            let nearestIdx = 0;
            let nearestDist = Math.abs(s.start_time - T[0]);
            for (let i = 1; i < T.length; i++) {
                const d = Math.abs(s.start_time - T[i]);
                if (d < nearestDist) { nearestDist = d; nearestIdx = i; }
            }
            const clampedIdx = Math.min(nearestIdx, N2 - 1);
            return { ...s, start_time: Tprime[clampedIdx] };
        });

        return { beats: newBeats, notes: newNotes, sections: newSections };
    }

    function findFirstDownbeat(_detectedBeats, _offsetSec) {
        throw new Error('not implemented');
    }

    function computeDriftSummary(_oldBeats, _newBeats) {
        throw new Error('not implemented');
    }

    return { warpTabToAudioBeats, findFirstDownbeat, computeDriftSummary };
}));
