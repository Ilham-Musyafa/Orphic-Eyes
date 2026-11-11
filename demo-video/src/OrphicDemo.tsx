import React from 'react';
import {
  AbsoluteFill,
  Easing,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  interpolateColors,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {FONT} from './fonts';
import {CamKey, Caption, SCENES, SCENE_STARTS, Scene, sceneDuration, segFrames} from './timeline';

const ORANGE = '#F97316';
const INK = '#0B0B0F';

// Window geometry: recording floats at 84% width, 16:9, below the caption band.
const WIN_W = Math.round(1920 * 0.84); // 1613
const WIN_H = Math.round((WIN_W * 9) / 16); // 907
const WIN_X = (1920 - WIN_W) / 2;
const WIN_Y = 156;
const CAPTION_Y = 78; // caption band centre (window starts at 156)

const easeInOut = Easing.bezier(0.65, 0, 0.35, 1);
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// ---------- Background ----------

const Background: React.FC<{dark?: number}> = ({dark = 0}) => (
  <AbsoluteFill>
    <AbsoluteFill
      style={{
        background: 'radial-gradient(ellipse 75% 70% at 50% 45%, #FAFAFB 0%, #EEEFF2 55%, #DFE1E6 100%)',
      }}
    />
    {dark > 0 && (
      <AbsoluteFill
        style={{
          opacity: dark,
          background: 'radial-gradient(ellipse 70% 65% at 50% 45%, #17171D 0%, #0B0B0F 70%)',
        }}
      />
    )}
  </AbsoluteFill>
);

// ---------- Caption: words spring in (scale + fade) ----------

const Words: React.FC<{
  caption: Caption;
  delay?: number;
  size: number;
  color?: string;
  stagger?: number;
}> = ({caption, delay = 0, size, color = INK, stagger = 3}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <div
      style={{
        fontFamily: FONT,
        fontWeight: 800,
        fontSize: size,
        letterSpacing: -0.02 * size,
        lineHeight: 1.1,
        color,
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        columnGap: size * 0.26,
        whiteSpace: 'nowrap',
      }}
    >
      {caption.words.map((w, i) => {
        const s = spring({frame: frame - delay - i * stagger, fps, config: {damping: 14, stiffness: 170, mass: 0.6}});
        const o = interpolate(frame - delay - i * stagger, [0, 6], [0, 1], clamp);
        return (
          <span
            key={i}
            style={{
              display: 'inline-block',
              color: i === caption.accent ? ORANGE : undefined,
              opacity: o,
              transform: `translateY(${(1 - s) * 14}px) scale(${0.86 + 0.14 * s})`,
            }}
          >
            {w}
          </span>
        );
      })}
    </div>
  );
};

const SceneCaption: React.FC<{caption: Caption; duration: number}> = ({caption, duration}) => {
  const frame = useCurrentFrame();
  const out = interpolate(frame, [duration - 9, duration - 1], [1, 0], clamp);
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        top: CAPTION_Y,
        transform: `translateY(-50%) translateY(${(1 - out) * -8}px)`,
        opacity: out,
        display: 'flex',
        justifyContent: 'center',
      }}
    >
      <Words caption={caption} delay={4} size={56} />
    </div>
  );
};

// ---------- Camera ----------

const camAt = (keys: CamKey[], f: number) => {
  if (f <= keys[0].f) return keys[0];
  for (let i = 0; i < keys.length - 1; i++) {
    const a = keys[i];
    const b = keys[i + 1];
    if (f >= a.f && f <= b.f) {
      const t = b.f === a.f ? 1 : easeInOut((f - a.f) / (b.f - a.f));
      return {f, zoom: a.zoom + (b.zoom - a.zoom) * t, x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t};
    }
  }
  return keys[keys.length - 1];
};

const cameraTransform = (keys: CamKey[], f: number) => {
  const {zoom: s, x, y} = camAt(keys, f);
  const maxX = ((s - 1) * WIN_W) / 2;
  const maxY = ((s - 1) * WIN_H) / 2;
  const tx = Math.max(-maxX, Math.min(maxX, -(x - 0.5) * WIN_W * s));
  const ty = Math.max(-maxY, Math.min(maxY, -(y - 0.5) * WIN_H * s));
  return `translate(${tx}px, ${ty}px) scale(${s})`;
};

// ---------- Floating window ----------

const Window: React.FC<{children: React.ReactNode; style?: React.CSSProperties}> = ({children, style}) => (
  <div
    style={{
      position: 'absolute',
      left: WIN_X,
      top: WIN_Y,
      width: WIN_W,
      height: WIN_H,
      borderRadius: 20,
      overflow: 'hidden',
      background: '#fff',
      boxShadow:
        '0 60px 120px -30px rgba(15, 23, 42, 0.38), 0 30px 60px -30px rgba(15, 23, 42, 0.30), 0 0 0 1px rgba(15, 23, 42, 0.06)',
      ...style,
    }}
  >
    {children}
  </div>
);

const ClipScene: React.FC<{scene: Extract<Scene, {kind: 'clip'}>}> = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const duration = sceneDuration(scene);

  let windowStyle: React.CSSProperties = {};
  if (scene.tiltIn) {
    const s = spring({frame, fps, config: {damping: 20, stiffness: 70, mass: 1}});
    windowStyle = {
      transform: `perspective(2200px) translateY(${(1 - s) * 140}px) rotateX(${(1 - s) * 22}deg) rotateY(${(1 - s) * -9}deg) scale(${0.86 + 0.14 * s})`,
      opacity: interpolate(frame, [0, 8], [0, 1], clamp),
      transformOrigin: '50% 100%',
    };
  }

  let offset = 0;
  return (
    <AbsoluteFill>
      <SceneCaption caption={scene.caption} duration={duration} />
      <Window style={windowStyle}>
        <div
          style={{
            position: 'absolute',
            inset: 0,
            transform: cameraTransform(scene.cam, frame),
            transformOrigin: '50% 50%',
            willChange: 'transform',
          }}
        >
          {scene.segments.map((seg, i) => {
            const n = segFrames(seg);
            const el = (
              <Sequence key={i} from={offset} durationInFrames={n}>
                <OffthreadVideo
                  src={staticFile(seg.clip)}
                  startFrom={Math.round(seg.from * fps)}
                  endAt={Math.round(seg.to * fps)}
                  playbackRate={seg.rate}
                  muted
                  style={{width: '100%', height: '100%'}}
                />
              </Sequence>
            );
            offset += n;
            return el;
          })}
        </div>
      </Window>
    </AbsoluteFill>
  );
};

// ---------- Intro ----------

const cardBase: React.CSSProperties = {
  position: 'absolute',
  background: '#fff',
  borderRadius: 18,
  boxShadow: '0 30px 60px -20px rgba(15,23,42,0.28), 0 0 0 1px rgba(15,23,42,0.06)',
  overflow: 'hidden',
  fontFamily: FONT,
};

const PopCard: React.FC<{
  x: number;
  y: number;
  w: number;
  h: number;
  rot: number;
  delay: number;
  exitAt: number;
  children: React.ReactNode;
}> = ({x, y, w, h, rot, delay, exitAt, children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: frame - delay, fps, config: {damping: 12, stiffness: 140, mass: 0.8}});
  const out = spring({frame: frame - exitAt, fps, config: {damping: 200, stiffness: 120}});
  const float = Math.sin((frame + delay * 7) / 28) * 6;
  const scale = s * (1 - out * 0.25);
  return (
    <div
      style={{
        ...cardBase,
        left: x - w / 2,
        top: y - h / 2,
        width: w,
        height: h,
        opacity: Math.min(1, s * 1.4) * (1 - out),
        transform: `translateY(${float + out * 30}px) rotate(${rot + (1 - s) * rot * 2.2}deg) scale(${scale})`,
      }}
    >
      {children}
    </div>
  );
};

const Label: React.FC<{children: React.ReactNode; color?: string}> = ({children, color = '#6B7280'}) => (
  <div style={{fontSize: 15, fontWeight: 600, letterSpacing: 2, color, textTransform: 'uppercase'}}>{children}</div>
);

const ShotCard: React.FC<{src: string; label: string}> = ({src, label}) => (
  <div style={{position: 'absolute', inset: 0, padding: 14, display: 'flex', flexDirection: 'column', gap: 10}}>
    <Label>{label}</Label>
    <Img src={staticFile(src)} style={{width: '100%', borderRadius: 10, border: '1px solid rgba(0,0,0,0.06)'}} />
  </div>
);

const ChangesCard: React.FC = () => {
  const rows = ['Top right', 'Top left', 'Middle right', 'Middle left'];
  return (
    <div style={{position: 'absolute', inset: 0, padding: '20px 22px'}}>
      <Label>Changes · 6</Label>
      <div style={{marginTop: 14, display: 'flex', flexDirection: 'column', gap: 12}}>
        {rows.map((r, i) => (
          <div key={r} style={{display: 'flex', alignItems: 'center', gap: 12}}>
            <div
              style={{
                width: 26,
                height: 26,
                borderRadius: 8,
                background: '#F3F4F6',
                fontSize: 14,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#374151',
              }}
            >
              {i + 1}
            </div>
            <div style={{fontSize: 19, fontWeight: 600, color: '#111827', flex: 1}}>{r}</div>
            <div
              style={{
                fontSize: 13,
                fontWeight: 600,
                color: '#C2410C',
                background: '#FFEDD5',
                padding: '4px 10px',
                borderRadius: 999,
              }}
            >
              Unexpected
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const PromptCard: React.FC = () => (
  <div style={{position: 'absolute', inset: 0, padding: '20px 22px'}}>
    <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
      <Label>Generated request</Label>
      <div
        style={{
          background: ORANGE,
          color: '#fff',
          fontWeight: 800,
          fontSize: 15,
          padding: '7px 14px',
          borderRadius: 10,
        }}
      >
        Copy prompt
      </div>
    </div>
    <div
      style={{
        marginTop: 16,
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        fontSize: 17,
        lineHeight: 1.5,
        color: '#1F2937',
        background: '#F7F7F8',
        borderRadius: 10,
        padding: '12px 14px',
      }}
    >
      PT-2 Move Selected area
      <br />
      199 px right, 88 px down.
      <br />
      Precision: Exact.
    </div>
  </div>
);

const Intro: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  const exitAt = duration - 22;
  const textOut = interpolate(frame, [exitAt, exitAt + 14], [1, 0], clamp);
  return (
    <AbsoluteFill>
      <PopCard x={370} y={250} w={520} h={360} rot={-7} delay={4} exitAt={exitAt}>
        <ShotCard src="before.png" label="Before" />
      </PopCard>
      <PopCard x={1590} y={868} w={500} h={346} rot={5} delay={10} exitAt={exitAt + 2}>
        <ShotCard src="after.png" label="After" />
      </PopCard>
      <PopCard x={1540} y={235} w={420} h={260} rot={5} delay={16} exitAt={exitAt + 1}>
        <ChangesCard />
      </PopCard>
      <PopCard x={385} y={850} w={440} h={206} rot={-5} delay={22} exitAt={exitAt + 3}>
        <PromptCard />
      </PopCard>
      <AbsoluteFill
        style={{
          justifyContent: 'center',
          alignItems: 'center',
          flexDirection: 'column',
          gap: 26,
          opacity: textOut,
          transform: `translateY(${(1 - textOut) * -16}px)`,
        }}
      >
        <Words caption={{words: ['Your', 'UI', 'changed.'], accent: 2}} delay={34} size={104} stagger={4} />
        <div style={{opacity: 0.92}}>
          <Words
            caption={{words: ['Orphic', 'Eyes', 'shows', 'exactly', 'what.'], accent: 3}}
            delay={80}
            size={60}
            stagger={4}
          />
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---------- Values card ----------

const Icon: React.FC<{kind: 'pixels' | 'code' | 'local'}> = ({kind}) => {
  const p = {fill: 'none', stroke: ORANGE, strokeWidth: 2.4, strokeLinecap: 'round', strokeLinejoin: 'round'} as const;
  return (
    <svg width={56} height={56} viewBox="0 0 24 24">
      {kind === 'pixels' && (
        <>
          <rect x="3" y="3" width="7" height="7" rx="1.5" {...p} />
          <rect x="14" y="3" width="7" height="7" rx="1.5" {...p} />
          <rect x="3" y="14" width="7" height="7" rx="1.5" {...p} />
          <rect x="14" y="14" width="7" height="7" rx="1.5" {...p} />
        </>
      )}
      {kind === 'code' && (
        <>
          <path d="M8 7l-5 5 5 5M16 7l5 5-5 5" {...p} />
          <path d="M4 20L20 4" {...p} />
        </>
      )}
      {kind === 'local' && (
        <>
          <rect x="3" y="4" width="18" height="12" rx="2" {...p} />
          <path d="M8 20h8M12 16v4" {...p} />
        </>
      )}
    </svg>
  );
};

const ValuesCard: React.FC<{duration: number}> = ({duration}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const items: {kind: 'pixels' | 'code' | 'local'; words: string[]; accent: number}[] = [
    {kind: 'pixels', words: ['Pixels', 'only.'], accent: 0},
    {kind: 'code', words: ['No', 'page', 'code.'], accent: -1},
    {kind: 'local', words: ['Runs', 'locally.'], accent: -1},
  ];
  const out = interpolate(frame, [duration - 12, duration - 1], [1, 0], clamp);
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', opacity: out}}>
      <div style={{display: 'flex', gap: 40}}>
        {items.map((it, i) => {
          const d = 6 + i * 12;
          const s = spring({frame: frame - d, fps, config: {damping: 12, stiffness: 140, mass: 0.8}});
          const rot = [-3, 2, -2][i];
          return (
            <div
              key={it.kind}
              style={{
                ...cardBase,
                position: 'relative',
                width: 520,
                height: 300,
                padding: '44px 40px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                opacity: Math.min(1, s * 1.4),
                transform: `translateY(${(1 - s) * 60}px) rotate(${(1 - s) * rot * 3}deg) scale(${0.8 + 0.2 * s})`,
              }}
            >
              <div
                style={{
                  width: 84,
                  height: 84,
                  borderRadius: 22,
                  background: '#FFF4EC',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Icon kind={it.kind} />
              </div>
              <div style={{display: 'flex', justifyContent: 'flex-start'}}>
                <Words caption={{words: it.words, accent: it.accent}} delay={d + 6} size={48} />
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ---------- Outro ----------

const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pop = (d: number) => spring({frame: frame - d, fps, config: {damping: 14, stiffness: 120, mass: 0.7}});
  const a = pop(16);
  const b = pop(30);
  const c = pop(44);
  const ring = pop(8);
  const item = (s: number): React.CSSProperties => ({
    opacity: Math.min(1, s * 1.3),
    transform: `translateY(${(1 - s) * 24}px) scale(${0.9 + 0.1 * s})`,
  });
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', flexDirection: 'column', fontFamily: FONT}}>
      <svg
        width={96}
        height={96}
        viewBox="0 0 48 48"
        style={{marginBottom: 34, opacity: ring, transform: `scale(${0.6 + 0.4 * ring}) rotate(${(1 - ring) * -40}deg)`}}
      >
        <path d="M4 24c5-9 12-14 20-14s15 5 20 14c-5 9-12 14-20 14S9 33 4 24z" fill="none" stroke="#fff" strokeWidth="3" />
        <circle cx="24" cy="24" r="7" fill={ORANGE} />
      </svg>
      <div style={{...item(a), fontWeight: 800, fontSize: 132, letterSpacing: -4, color: '#fff'}}>Orphic Eyes</div>
      <div style={{...item(b), marginTop: 18, fontWeight: 600, fontSize: 44, color: '#A1A1AA'}}>
        Visual review plugin for <span style={{color: ORANGE}}>Hermes Agent</span>
      </div>
      <div style={{...item(c), marginTop: 70, fontWeight: 500, fontSize: 30, color: '#71717A', letterSpacing: 0.5}}>
        Built by <span style={{color: '#E4E4E7', fontWeight: 600}}>Ilham Musyafa</span>
      </div>
    </AbsoluteFill>
  );
};

// ---------- Root composition ----------

export const OrphicDemo: React.FC = () => {
  const frame = useCurrentFrame();
  const outroStart = SCENE_STARTS[SCENES.length - 1];
  const dark = interpolate(frame, [outroStart, outroStart + 24], [0, 1], {...clamp, easing: easeInOut});
  return (
    <AbsoluteFill style={{backgroundColor: interpolateColors(dark, [0, 1], ['#ECEDF0', INK])}}>
      <Background dark={dark} />
      {SCENES.map((scene, i) => {
        const dur = sceneDuration(scene);
        return (
          <Sequence key={i} from={SCENE_STARTS[i]} durationInFrames={dur} name={scene.kind === 'clip' ? scene.name : scene.kind}>
            {scene.kind === 'intro' && <Intro duration={dur} />}
            {scene.kind === 'clip' && <ClipScene scene={scene} />}
            {scene.kind === 'card' && <ValuesCard duration={dur} />}
            {scene.kind === 'outro' && <Outro />}
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
