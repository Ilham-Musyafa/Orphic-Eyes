import {continueRender, delayRender, staticFile} from 'remotion';

export const FONT = 'Montserrat';

const weights: [string, string][] = [
  ['500', 'fonts/montserrat-latin-500-normal.woff2'],
  ['600', 'fonts/montserrat-latin-600-normal.woff2'],
  ['800', 'fonts/montserrat-latin-800-normal.woff2'],
];

if (typeof document !== 'undefined') {
  const handle = delayRender('Loading Montserrat');
  Promise.all(
    weights.map(([weight, file]) => {
      const face = new FontFace(FONT, `url(${staticFile(file)}) format('woff2')`, {weight});
      return face.load().then((f) => document.fonts.add(f));
    }),
  )
    .then(() => continueRender(handle))
    .catch((err) => {
      console.error(err);
      continueRender(handle);
    });
}
