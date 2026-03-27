import React from 'react';
import {Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

export type FancyTextTheme = 'notion' | 'cyberpunk' | 'apple' | 'aurora' | 'douyin';
export type FancyTextStyle = 'emphasis' | 'term' | 'number';
export type FancyTextPosition =
  | 'top'
  | 'tl'
  | 'tr'
  | 'bottom'
  | 'bl'
  | 'br'
  | 'left'
  | 'lt'
  | 'lb'
  | 'right'
  | 'rt'
  | 'rb';

export type FancyTextProps = {
  text: string;
  style?: FancyTextStyle;
  theme?: FancyTextTheme;
  position?: FancyTextPosition;
  durationMs?: number;
  safeMargin?: number;
};

const msToFrames = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

const baseStyle: React.CSSProperties = {
  position: 'absolute',
  fontFamily: '"STHeiti", "Heiti SC", "Microsoft YaHei", "PingFang SC", sans-serif',
  fontSize: 52,
  fontWeight: 'bold',
  whiteSpace: 'normal',
  wordBreak: 'break-word',
  overflowWrap: 'anywhere',
  textAlign: 'center',
  transformOrigin: 'center center',
  boxSizing: 'border-box',
};

const stylePresets: Record<FancyTextStyle, React.CSSProperties> = {
  emphasis: {
    color: '#FFED4E',
    WebkitTextStroke: '4px #FF1744',
    textShadow:
      '6px 6px 8px rgba(0, 0, 0, 0.5), 0 0 20px rgba(255, 23, 68, 0.3)',
    paintOrder: 'stroke fill',
  },
  term: {
    color: '#00E5FF',
    WebkitTextStroke: '4px #E91E63',
    textShadow:
      '6px 6px 8px rgba(0, 0, 0, 0.5), 0 0 20px rgba(233, 30, 99, 0.3)',
    paintOrder: 'stroke fill',
  },
  number: {
    color: '#FF6D00',
    WebkitTextStroke: '4px #1A237E',
    textShadow:
      '6px 6px 8px rgba(0, 0, 0, 0.5), 0 0 20px rgba(26, 35, 126, 0.3)',
    paintOrder: 'stroke fill',
  },
};

const themeStyles: Record<FancyTextTheme, Partial<Record<FancyTextStyle, React.CSSProperties>>> = {
  notion: {
    emphasis: {
      color: '#37352F',
      background: 'linear-gradient(180deg, transparent 50%, #FBF3DB 50%)',
      padding: '0 8px',
      WebkitTextStroke: 'unset',
      textShadow: 'none',
      transform: 'rotate(-1deg)',
      fontFamily: '"Georgia", "Noto Serif SC", serif',
      fontWeight: 700,
    },
    term: {
      color: '#E16259',
      background: 'linear-gradient(180deg, transparent 60%, rgba(225, 98, 89, 0.2) 60%)',
      padding: '0 8px',
      WebkitTextStroke: 'unset',
      textShadow: 'none',
      transform: 'rotate(0.5deg)',
      fontFamily: '"Georgia", "Noto Serif SC", serif',
      fontWeight: 700,
    },
    number: {
      color: '#0B6E99',
      background: 'linear-gradient(180deg, transparent 60%, rgba(11, 110, 153, 0.15) 60%)',
      padding: '0 8px',
      WebkitTextStroke: 'unset',
      textShadow: 'none',
      transform: 'rotate(-0.5deg)',
      fontFamily: '"Georgia", "Noto Serif SC", serif',
      fontWeight: 700,
    },
  },
  apple: {
    emphasis: {
      color: '#FFFFFF',
      textShadow: '0 2px 20px rgba(0, 0, 0, 0.3)',
      WebkitTextStroke: 'unset',
      fontFamily:
        '-apple-system, BlinkMacSystemFont, "SF Pro Display", "PingFang SC", sans-serif',
      fontWeight: 700,
      letterSpacing: '-0.02em',
    },
    term: {
      color: '#FFFFFF',
      textShadow: '0 2px 20px rgba(0, 0, 0, 0.3)',
      WebkitTextStroke: 'unset',
      fontFamily:
        '-apple-system, BlinkMacSystemFont, "SF Pro Display", "PingFang SC", sans-serif',
      fontWeight: 700,
      letterSpacing: '-0.02em',
    },
    number: {
      color: '#0071E3',
      textShadow: '0 2px 20px rgba(0, 113, 227, 0.4)',
      WebkitTextStroke: 'unset',
      fontFamily:
        '-apple-system, BlinkMacSystemFont, "SF Pro Display", "PingFang SC", sans-serif',
      fontWeight: 700,
      letterSpacing: '-0.02em',
    },
  },
  cyberpunk: {
    emphasis: {
      color: '#00F5FF',
      textShadow:
        '0 0 10px #00F5FF, 0 0 20px #00F5FF, 0 0 40px #00F5FF, 0 0 80px #FF00FF',
      WebkitTextStroke: 'unset',
      fontFamily: '"Orbitron", "STHeiti", "Heiti SC", sans-serif',
      fontWeight: 900,
      letterSpacing: '0.05em',
      textTransform: 'uppercase',
    },
    term: {
      color: '#FF00FF',
      textShadow:
        '0 0 10px #FF00FF, 0 0 20px #FF00FF, 0 0 40px #FF00FF, 0 0 80px #00F5FF',
      WebkitTextStroke: 'unset',
      fontFamily: '"Orbitron", "STHeiti", "Heiti SC", sans-serif',
      fontWeight: 900,
      letterSpacing: '0.05em',
      textTransform: 'uppercase',
    },
    number: {
      color: '#FFFF00',
      textShadow:
        '0 0 10px #FFFF00, 0 0 20px #FFFF00, 0 0 40px #00F5FF',
      WebkitTextStroke: 'unset',
      fontFamily: '"Orbitron", "STHeiti", "Heiti SC", sans-serif',
      fontWeight: 900,
      letterSpacing: '0.05em',
      textTransform: 'uppercase',
    },
  },
  aurora: {
    emphasis: {
      background:
        'linear-gradient(135deg, #667EEA 0%, #764BA2 50%, #F093FB 100%)',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      backgroundClip: 'text',
      filter: 'drop-shadow(0 4px 20px rgba(102, 126, 234, 0.5))',
      WebkitTextStroke: '1px rgba(255, 255, 255, 0.3)',
      fontFamily: '"Avenir Next", "PingFang SC", sans-serif',
      fontWeight: 700,
      letterSpacing: '0.02em',
    },
    term: {
      background:
        'linear-gradient(135deg, #F093FB 0%, #F5576C 50%, #FFD194 100%)',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      backgroundClip: 'text',
      filter: 'drop-shadow(0 4px 20px rgba(240, 147, 251, 0.5))',
      WebkitTextStroke: '1px rgba(255, 255, 255, 0.3)',
      fontFamily: '"Avenir Next", "PingFang SC", sans-serif',
      fontWeight: 700,
      letterSpacing: '0.02em',
    },
    number: {
      background:
        'linear-gradient(135deg, #4FACFE 0%, #00F2FE 100%)',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      backgroundClip: 'text',
      filter: 'drop-shadow(0 4px 20px rgba(79, 172, 254, 0.5))',
      WebkitTextStroke: '1px rgba(255, 255, 255, 0.3)',
      fontFamily: '"Avenir Next", "PingFang SC", sans-serif',
      fontWeight: 700,
      letterSpacing: '0.02em',
    },
  },
  douyin: {
    emphasis: {
      color: '#FFFFFF',
      textShadow:
        '-2px 0 0 #25F4EE, 2px 0 0 #FE2C55, 0 8px 24px rgba(0, 0, 0, 0.45)',
      WebkitTextStroke: 'unset',
      fontFamily: '"Montserrat", "PingFang SC", sans-serif',
      fontWeight: 700,
    },
    term: {
      color: '#FFFFFF',
      textShadow:
        '-2px 0 0 #25F4EE, 2px 0 0 #FE2C55, 0 8px 24px rgba(0, 0, 0, 0.45)',
      WebkitTextStroke: 'unset',
      fontFamily: '"Montserrat", "PingFang SC", sans-serif',
      fontWeight: 700,
    },
    number: {
      color: '#FFFFFF',
      textShadow:
        '-2px 0 0 #25F4EE, 2px 0 0 #FE2C55, 0 8px 24px rgba(0, 0, 0, 0.45)',
      WebkitTextStroke: 'unset',
      fontFamily: '"Montserrat", "PingFang SC", sans-serif',
      fontWeight: 700,
    },
  },
};

export const FancyText: React.FC<FancyTextProps> = ({
  text,
  style = 'emphasis',
  theme = 'notion',
  position = 'top',
  durationMs = 2000,
  safeMargin = 24,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const totalFrames = Math.min(durationInFrames, msToFrames(durationMs, fps));
  const enterFrames = msToFrames(600, fps);
  const exitFrames = msToFrames(300, fps);
  const exitStart = totalFrames - exitFrames;

  let enterScale = [0.8, 1.15] as [number, number];
  let settleScale = [1.15, 1.0] as [number, number];
  let wobbleRotate = [3, -3, 2, -2, 0];

  if (theme === 'apple') {
    enterScale = [0.95, 1.02];
    settleScale = [1.02, 1.0];
    wobbleRotate = [0, 0, 0, 0, 0];
  } else if (theme === 'notion') {
    enterScale = [0.85, 1.05];
    settleScale = [1.05, 1.0];
    wobbleRotate = [2, -1, 1, -0.5, 0];
  } else if (theme === 'aurora') {
    enterScale = [0.9, 1.08];
    settleScale = [1.08, 1.0];
    wobbleRotate = [1, -1, 0.5, -0.5, 0];
  } else if (theme === 'douyin') {
    enterScale = [1, 1];
    settleScale = [1, 1];
    wobbleRotate = [0, 0, 0, 0, 0];
  }

  const marginX = Math.max(safeMargin, width * 0.08);
  const marginY = Math.max(safeMargin, height * 0.1);
  const normalizedPosition = typeof position === 'string' ? position : 'top';
  const resolvedPosition =
    normalizedPosition === 'top'
      ? {x: width / 2, y: marginY}
      : normalizedPosition === 'bottom'
        ? {x: width / 2, y: height - marginY}
        : normalizedPosition === 'left'
          ? {x: marginX, y: height / 2}
          : normalizedPosition === 'right'
            ? {x: width - marginX, y: height / 2}
            : normalizedPosition === 'tl' || normalizedPosition === 'lt'
              ? {x: marginX, y: marginY}
              : normalizedPosition === 'tr' || normalizedPosition === 'rt'
                ? {x: width - marginX, y: marginY}
                : normalizedPosition === 'bl' || normalizedPosition === 'lb'
                  ? {x: marginX, y: height - marginY}
                  : normalizedPosition === 'br' || normalizedPosition === 'rb'
                    ? {x: width - marginX, y: height - marginY}
                    : {x: width / 2, y: marginY};

  const centerX = Math.min(
    Math.max(resolvedPosition.x, safeMargin),
    width - safeMargin
  );
  const centerY = Math.min(
    Math.max(resolvedPosition.y, safeMargin),
    height - safeMargin
  );

  const enterProgress = spring({
    frame,
    fps,
    config: {damping: 12, stiffness: 200, mass: 1},
    durationInFrames: enterFrames,
  });

  const enterScaleValue = interpolate(enterProgress, [0, 1], enterScale);
  const settleScaleValue = interpolate(
    frame,
    [enterFrames, enterFrames + msToFrames(300, fps)],
    settleScale,
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );
  const baseScale = frame <= enterFrames ? enterScaleValue : settleScaleValue;

  const exitScale = interpolate(
    frame,
    [exitStart, totalFrames],
    [1, 0.9],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );
  const scale = baseScale * exitScale;

  const enterRotate = interpolate(
    frame,
    [0, enterFrames],
    [0, wobbleRotate[0]],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  const wobbleDuration = Math.max(exitStart - enterFrames, 1);
  const segment = wobbleDuration / (wobbleRotate.length - 1);
  const wobbleInput = wobbleRotate.map((_, i) => enterFrames + i * segment);
  const wobbleRotateValue = interpolate(
    frame,
    wobbleInput,
    wobbleRotate,
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.ease)}
  );

  const rotate = frame <= enterFrames ? enterRotate : wobbleRotateValue;

  const opacity = interpolate(
    frame,
    [0, enterFrames, exitStart, totalFrames],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  const themeStyle = themeStyles[theme][style] ?? {};
  const stylePreset = stylePresets[style];

  const stableScale = Math.round(scale * 1000) / 1000;
  const stableRotate = Math.round(rotate * 100) / 100;
  const safeScale = Math.max(stableScale, 0.001);
  const availableHalfWidth = Math.max(
    Math.min(centerX - safeMargin, width - safeMargin - centerX),
    0
  );
  const availableHalfHeight = Math.max(
    Math.min(centerY - safeMargin, height - safeMargin - centerY),
    0
  );
  const maxWidth = (availableHalfWidth * 2) / safeScale;
  const maxHeight = (availableHalfHeight * 2) / safeScale;

  return (
    <div style={{width: '100%', height: '100%', position: 'relative'}}>
      <div
        style={{
          ...baseStyle,
          ...stylePreset,
          ...themeStyle,
          left: centerX,
          top: centerY,
          maxWidth,
          maxHeight,
          overflow: 'hidden',
          opacity,
          transform: `translate(-50%, -50%) translateZ(0) scale(${stableScale}) rotate(${stableRotate}deg)`,
          backfaceVisibility: 'hidden',
          WebkitFontSmoothing: 'antialiased',
        }}
      >
        {text}
      </div>
    </div>
  );
};
