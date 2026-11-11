// Edit decision list for the Orphic Eyes demo.
// Source timestamps (seconds) were found by extracting frames + a frame-difference
// activity scan of the raw OBS recordings; idle stretches are cut out.

export const FPS = 30;

export type Clip = 'clip1.mp4' | 'clip2.mp4';

export type Segment = {
  clip: Clip;
  from: number; // source seconds
  to: number; // source seconds
  rate: number; // playbackRate
};

// Camera keyframe: zoom level + focus point as a fraction of the recording (0..1).
export type CamKey = {f: number; zoom: number; x: number; y: number};

export type Caption = {words: string[]; accent: number};

export type Scene =
  | {kind: 'intro'; duration: number}
  | {kind: 'clip'; name: string; segments: Segment[]; cam: CamKey[]; caption: Caption; tiltIn?: boolean}
  | {kind: 'card'; duration: number}
  | {kind: 'outro'; duration: number};

export const segFrames = (s: Segment) => Math.round(((s.to - s.from) * FPS) / s.rate);

// Local frame (inside a scene) at which source time `sec` of segment `i` plays.
const at = (segs: Segment[], i: number, sec: number) => {
  let off = 0;
  for (let k = 0; k < i; k++) off += segFrames(segs[k]);
  return Math.round(off + ((sec - segs[i].from) * FPS) / segs[i].rate);
};

const cap = (text: string, accent: string): Caption => {
  const words = text.split(' ');
  return {words, accent: words.indexOf(accent)};
};

// ---------- Scenes ----------

const trySample: Segment[] = [
  {clip: 'clip1.mp4', from: 13.6, to: 19.6, rate: 1}, // click "Try sample" -> boxes appear
  {clip: 'clip1.mp4', from: 22.3, to: 26.0, rate: 1}, // open the change list
];

const flip: Segment[] = [
  {clip: 'clip1.mp4', from: 47.8, to: 56.6, rate: 1.15}, // Slider drag -> Overlay -> Diff
];

const snap: Segment[] = [
  {clip: 'clip2.mp4', from: 13.4, to: 20.4, rate: 1.25}, // Move mode, drag box, snap chip
];

const move: Segment[] = [
  {clip: 'clip2.mp4', from: 20.4, to: 30.2, rate: 1.75}, // drag the selection around
  {clip: 'clip2.mp4', from: 33.4, to: 36.4, rate: 1}, // Add request
];

const copy: Segment[] = [
  {clip: 'clip2.mp4', from: 36.4, to: 42.4, rate: 1}, // Copy prompt -> generated text
];

const verify: Segment[] = [
  {clip: 'clip2.mp4', from: 48.4, to: 56.4, rate: 1.25}, // Verify fixes dialog
];

export const SCENES: Scene[] = [
  {kind: 'intro', duration: 210},
  {
    kind: 'clip',
    name: 'Try sample',
    segments: trySample,
    tiltIn: true,
    caption: cap('Every change, boxed.', 'boxed.'),
    cam: [
      {f: 0, zoom: 1.5, x: 0.45, y: 0.62},
      {f: at(trySample, 0, 14.9), zoom: 1.5, x: 0.45, y: 0.62},
      {f: at(trySample, 0, 15.9), zoom: 1.0, x: 0.5, y: 0.5},
      {f: at(trySample, 0, 16.6), zoom: 1.0, x: 0.5, y: 0.5},
      {f: at(trySample, 0, 17.6), zoom: 1.45, x: 0.36, y: 0.5},
      {f: at(trySample, 0, 19.6) - 1, zoom: 1.45, x: 0.36, y: 0.5},
      {f: at(trySample, 1, 22.3), zoom: 1.0, x: 0.5, y: 0.5},
      {f: at(trySample, 1, 23.2), zoom: 1.0, x: 0.5, y: 0.5},
      {f: at(trySample, 1, 24.2), zoom: 1.4, x: 0.12, y: 0.32},
      {f: at(trySample, 1, 26.0), zoom: 1.4, x: 0.12, y: 0.32},
    ],
  },
  {
    kind: 'clip',
    name: 'Overlay slider',
    segments: flip,
    caption: cap('Flip Before and After.', 'Flip'),
    cam: [
      {f: 0, zoom: 1.0, x: 0.5, y: 0.5},
      {f: at(flip, 0, 48.8), zoom: 1.0, x: 0.5, y: 0.5},
      {f: at(flip, 0, 50.0), zoom: 1.35, x: 0.4, y: 0.45},
      {f: at(flip, 0, 52.4), zoom: 1.35, x: 0.4, y: 0.45},
      {f: at(flip, 0, 53.4), zoom: 1.5, x: 0.27, y: 0.33},
      {f: at(flip, 0, 56.6), zoom: 1.5, x: 0.27, y: 0.33},
    ],
  },
  {
    kind: 'clip',
    name: 'Snap',
    segments: snap,
    caption: cap('Drag a box. It snaps to the element.', 'snaps'),
    cam: [
      {f: 0, zoom: 1.0, x: 0.5, y: 0.5},
      {f: at(snap, 0, 14.0), zoom: 1.0, x: 0.5, y: 0.5},
      {f: at(snap, 0, 15.0), zoom: 1.55, x: 0.22, y: 0.48},
      {f: at(snap, 0, 20.4), zoom: 1.55, x: 0.22, y: 0.48},
    ],
  },
  {
    kind: 'clip',
    name: 'Move + Add request',
    segments: move,
    caption: cap('Move it. Exact to 2 px.', 'Exact'),
    cam: [
      {f: 0, zoom: 1.55, x: 0.22, y: 0.48},
      {f: at(move, 0, 22.0), zoom: 1.4, x: 0.27, y: 0.52},
      {f: at(move, 0, 30.2) - 1, zoom: 1.4, x: 0.27, y: 0.52},
      {f: at(move, 1, 33.4), zoom: 1.0, x: 0.5, y: 0.5},
      {f: at(move, 1, 33.9), zoom: 1.0, x: 0.5, y: 0.5},
      {f: at(move, 1, 34.9), zoom: 1.5, x: 0.9, y: 0.78},
      {f: at(move, 1, 36.4), zoom: 1.5, x: 0.9, y: 0.78},
    ],
  },
  {
    kind: 'clip',
    name: 'Copy prompt',
    segments: copy,
    caption: cap('One click. A precise prompt for Hermes.', 'Hermes.'),
    cam: [
      {f: 0, zoom: 1.45, x: 0.95, y: 0.05},
      {f: at(copy, 0, 37.7), zoom: 1.45, x: 0.95, y: 0.05},
      {f: at(copy, 0, 38.9), zoom: 1.6, x: 0.93, y: 0.74},
      {f: at(copy, 0, 42.4), zoom: 1.6, x: 0.93, y: 0.74},
    ],
  },
  {
    kind: 'clip',
    name: 'Verify',
    segments: verify,
    caption: cap('Verify the fix.', 'Verify'),
    cam: [
      {f: 0, zoom: 1.5, x: 0.07, y: 0.2},
      {f: at(verify, 0, 50.0), zoom: 1.5, x: 0.07, y: 0.2},
      {f: at(verify, 0, 51.0), zoom: 1.5, x: 0.5, y: 0.2},
      {f: at(verify, 0, 56.4), zoom: 1.5, x: 0.5, y: 0.2},
    ],
  },
  {kind: 'card', duration: 180},
  {kind: 'outro', duration: 210},
];

export const sceneDuration = (s: Scene) =>
  s.kind === 'clip' ? s.segments.reduce((a, g) => a + segFrames(g), 0) : s.duration;

export const SCENE_STARTS = SCENES.reduce<number[]>((acc, s, i) => {
  acc.push(i === 0 ? 0 : acc[i - 1] + sceneDuration(SCENES[i - 1]));
  return acc;
}, []);

export const TOTAL_FRAMES = SCENE_STARTS[SCENES.length - 1] + sceneDuration(SCENES[SCENES.length - 1]);
