import {Composition} from 'remotion';
import {OrphicDemo} from './OrphicDemo';
import {TOTAL_FRAMES, FPS} from './timeline';

export const RemotionRoot: React.FC = () => (
  <Composition
    id="OrphicDemo"
    component={OrphicDemo}
    durationInFrames={TOTAL_FRAMES}
    fps={FPS}
    width={1920}
    height={1080}
  />
);
