# Orphic Eyes — demo video

Remotion project that turns the two raw OBS recordings into a ~64 s product demo.

- Output: `out/orphic-demo.mp4` (1920x1080, 30 fps, H.264, yuv420p)
- Edit decision list (trims, playback rates, camera keyframes, captions): `src/timeline.ts`
- Visuals (background, floating window, camera, captions, intro/card/outro): `src/OrphicDemo.tsx`

## Re-render

The raw clips are not committed. Copy them into `public/` first:

- `public/clip1.mp4`: recording started 22:18:03 (Try sample, Slider/Overlay/Diff)
- `public/clip2.mp4`: recording started 22:22:49 (Move, snap, Add request, Copy prompt, Verify)

```bash
npm install
npm run render
```

If Remotion can't download its headless Chrome, point it at a local one:

```bash
REMOTION_CHROME=/path/to/chrome-headless-shell npm run render
```
