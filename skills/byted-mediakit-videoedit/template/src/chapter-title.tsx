import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

export type ChapterTitleTheme = 'notion' | 'cyberpunk' | 'apple' | 'aurora' | 'douyin';

export type ChapterTitleProps = {
  number?: string;
  title?: string;
  subtitle?: string;
  theme?: ChapterTitleTheme;
  durationMs?: number;
};

const msToFrames = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

const themeStyles: Record<ChapterTitleTheme, {
  number: React.CSSProperties;
  title: React.CSSProperties;
  subtitle: React.CSSProperties;
  line: React.CSSProperties;
}> = {
  notion: {
    number: {
      color: '#E16259',
      fontFamily: '"SF Mono", monospace',
    },
    title: {
      color: '#37352F',
      fontFamily: '"Georgia", "Noto Serif SC", serif',
    },
    subtitle: {
      color: '#787774',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
    },
    line: {
      background: 'linear-gradient(90deg, #DFAB01, #E16259)',
    },
  },
  cyberpunk: {
    number: {
      color: '#FF00FF',
      fontFamily: '"Orbitron", monospace',
      textShadow: '0 0 10px #FF00FF',
    },
    title: {
      color: '#00F5FF',
      fontFamily: '"Orbitron", sans-serif',
      textShadow: '0 0 20px #00F5FF',
    },
    subtitle: {
      color: '#888',
      fontFamily: '"Courier New", monospace',
    },
    line: {
      background: 'linear-gradient(90deg, #00F5FF, #FF00FF, #00F5FF)',
      boxShadow: '0 0 20px #00F5FF',
    },
  },
  apple: {
    number: {
      color: '#0071E3',
      fontFamily: '-apple-system, "SF Pro Text", sans-serif',
    },
    title: {
      color: '#1D1D1F',
      fontFamily: '-apple-system, "SF Pro Display", sans-serif',
      fontWeight: 600,
    },
    subtitle: {
      color: '#86868B',
      fontFamily: '-apple-system, "SF Pro Text", sans-serif',
    },
    line: {
      background: '#0071E3',
    },
  },
  aurora: {
    number: {
      background: 'linear-gradient(135deg, #F093FB, #F5576C)',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      fontFamily: '"SF Mono", monospace',
    },
    title: {
      background: 'linear-gradient(135deg, #667EEA, #764BA2, #F093FB)',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      fontFamily: '"Avenir Next", sans-serif',
    },
    subtitle: {
      color: '#B8B8D0',
      fontFamily: '-apple-system, sans-serif',
    },
    line: {
      background: 'linear-gradient(90deg, #667EEA, #764BA2, #F093FB)',
    },
  },
  douyin: {
    number: {
      color: '#25F4EE',
      fontFamily: '"Montserrat", "SF Mono", monospace',
      textShadow: '0 0 10px rgba(37, 244, 238, 0.6)',
    },
    title: {
      color: '#FFFFFF',
      fontFamily: '"Montserrat", "PingFang SC", sans-serif',
      textShadow:
        '-3px 0 0 #25F4EE, 3px 0 0 #FE2C55, 0 8px 24px rgba(0, 0, 0, 0.45)',
    },
    subtitle: {
      color: '#B8B8B8',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
    },
    line: {
      background: 'linear-gradient(90deg, #25F4EE, #FE2C55)',
    },
  },
};

export const ChapterTitle: React.FC<ChapterTitleProps> = ({
  number,
  title,
  subtitle,
  theme,
  durationMs,
}) => {
  const resolvedTheme = theme ?? 'notion';
  const resolvedDurationMs = durationMs ?? 4000;
  const resolvedTitle = title ?? '';
  const resolvedSubtitle = subtitle ?? '';
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const totalFrames = Math.min(durationInFrames, msToFrames(resolvedDurationMs, fps));
  const exitStart = msToFrames(resolvedDurationMs - 600, fps);
  const exitEnd = exitStart + msToFrames(500, fps);
  const enterEnd = msToFrames(300, fps);

  const containerOpacity = interpolate(
    frame,
    [0, enterEnd, exitStart, exitEnd],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );
  const containerScale = interpolate(
    frame,
    [exitStart, exitEnd],
    [1, 0.95],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  const numberOpacity = number
    ? interpolate(
        frame,
        [msToFrames(100, fps), msToFrames(500, fps)],
        [0, 1],
        {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
      )
    : 0;
  const numberY = number
    ? interpolate(
        frame,
        [msToFrames(100, fps), msToFrames(500, fps)],
        [-20, 0],
        {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
      )
    : 0;

  const titleStart = msToFrames(200, fps);
  const titleSpring = spring({
    frame: frame - titleStart,
    fps,
    config: {damping: 14, stiffness: 180, mass: 1},
    durationInFrames: msToFrames(600, fps),
  });
  const titleOpacity = interpolate(
    frame,
    [titleStart, titleStart + msToFrames(600, fps)],
    [0, 1],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );
  const titleY = interpolate(titleSpring, [0, 1], [30, 0]);

  const subtitleOpacity = resolvedSubtitle
    ? interpolate(
        frame,
        [msToFrames(500, fps), msToFrames(900, fps)],
        [0, 0.8],
        {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
      )
    : 0;
  const subtitleY = resolvedSubtitle
    ? interpolate(
        frame,
        [msToFrames(500, fps), msToFrames(900, fps)],
        [20, 0],
        {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
      )
    : 0;

  const lineWidth = interpolate(
    frame,
    [msToFrames(400, fps), msToFrames(900, fps)],
    [0, 120],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  const themeStyle = themeStyles[resolvedTheme];

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'transparent',
      }}
    >
      <div
        style={{
          textAlign: 'center',
          opacity: containerOpacity,
          transform: `scale(${containerScale})`,
        }}
      >
        {number ? (
          <div
            style={{
              fontSize: 24,
              fontWeight: 600,
              marginBottom: 12,
              opacity: numberOpacity,
              transform: `translateY(${numberY}px)`,
              ...themeStyle.number,
            }}
          >
            {number}
          </div>
        ) : null}
        <div
          style={{
            fontSize: 64,
            fontWeight: 700,
            opacity: titleOpacity,
            transform: `translateY(${titleY}px)`,
            ...themeStyle.title,
          }}
        >
          {resolvedTitle}
        </div>
        {resolvedSubtitle ? (
          <div
            style={{
              fontSize: 24,
              marginTop: 16,
              opacity: subtitleOpacity,
              transform: `translateY(${subtitleY}px)`,
              ...themeStyle.subtitle,
            }}
          >
            {resolvedSubtitle}
          </div>
        ) : null}
        <div
          style={{
            width: lineWidth,
            height: 3,
            margin: '24px auto 0',
            ...themeStyle.line,
          }}
        />
      </div>
    </div>
  );
};
