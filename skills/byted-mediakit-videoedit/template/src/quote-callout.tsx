import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

export type QuoteCalloutTheme = 'notion' | 'cyberpunk' | 'apple' | 'aurora' | 'douyin';
export type QuoteCalloutPosition =
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

export type QuoteCalloutProps = {
  text: string;
  author?: string;
  theme?: QuoteCalloutTheme;
  position?: QuoteCalloutPosition;
  durationMs?: number;
};

const msToFrames = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

const themeStyles: Record<
  QuoteCalloutTheme,
  {
    container: React.CSSProperties;
    quoteMark: React.CSSProperties;
    text: React.CSSProperties;
    author: React.CSSProperties;
  }
> = {
  notion: {
    container: {
      background: 'rgba(255, 253, 247, 0.95)',
      borderLeft: '4px solid #E16259',
      borderRadius: '0 8px 8px 0',
    },
    quoteMark: {
      color: '#E16259',
      fontFamily: 'Georgia, serif',
    },
    text: {
      color: '#37352F',
      fontFamily: '"Georgia", "Noto Serif SC", serif',
    },
    author: {
      color: '#787774',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
    },
  },
  cyberpunk: {
    container: {
      background: 'rgba(13, 13, 13, 0.95)',
      border: '1px solid #00F5FF',
      borderLeft: '4px solid #FF00FF',
    },
    quoteMark: {
      color: '#00F5FF',
      textShadow: '0 0 20px #00F5FF',
    },
    text: {
      color: '#FFFFFF',
      fontFamily: '-apple-system, sans-serif',
    },
    author: {
      color: '#FF00FF',
      fontFamily: '"Courier New", monospace',
    },
  },
  apple: {
    container: {
      background: 'rgba(255, 255, 255, 0.85)',
      borderRadius: 16,
      backdropFilter: 'blur(20px)',
    },
    quoteMark: {
      color: '#0071E3',
    },
    text: {
      color: '#1D1D1F',
      fontFamily: '-apple-system, "SF Pro Display", "PingFang SC", sans-serif',
      fontWeight: 400,
    },
    author: {
      color: '#86868B',
      fontFamily: '-apple-system, "SF Pro Text", sans-serif',
    },
  },
  aurora: {
    container: {
      background: 'rgba(15, 15, 35, 0.9)',
      borderRadius: 16,
      border: '1px solid rgba(102, 126, 234, 0.3)',
    },
    quoteMark: {
      background: 'linear-gradient(135deg, #667EEA, #F093FB)',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
    },
    text: {
      color: '#FFFFFF',
      fontFamily: '"Avenir Next", "PingFang SC", sans-serif',
    },
    author: {
      color: '#B8B8D0',
      fontFamily: '-apple-system, sans-serif',
    },
  },
  douyin: {
    container: {
      background: 'rgba(11, 11, 11, 0.92)',
      borderLeft: '4px solid #25F4EE',
      borderRadius: '0 12px 12px 0',
      boxShadow: '0 8px 24px rgba(0, 0, 0, 0.45)',
    },
    quoteMark: {
      color: '#FE2C55',
      textShadow: '0 0 14px rgba(254, 44, 85, 0.6)',
    },
    text: {
      color: '#FFFFFF',
      fontFamily: '"Montserrat", "PingFang SC", sans-serif',
      textShadow: '-2px 0 0 #25F4EE, 2px 0 0 #FE2C55',
    },
    author: {
      color: '#B8B8B8',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
    },
  },
};

export const QuoteCallout: React.FC<QuoteCalloutProps> = ({
  text,
  author,
  theme = 'notion',
  position = 'bottom',
  durationMs = 5000,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const totalFrames = Math.min(durationInFrames, msToFrames(durationMs, fps));
  const exitStart = totalFrames - msToFrames(500, fps);
  const exitEnd = exitStart + msToFrames(400, fps);

  const maxWidth = Math.min(800, Math.max(320, width - 80));
  const marginX = Math.max(64, width * 0.08);
  const marginY = Math.max(64, height * 0.1);
  const normalizedPosition = typeof position === 'string' ? position : 'bottom';
  const anchor =
    normalizedPosition === 'top'
      ? {x: width / 2, y: marginY, alignX: '-50%', alignY: '0%'}
      : normalizedPosition === 'bottom'
        ? {x: width / 2, y: height - marginY, alignX: '-50%', alignY: '-100%'}
        : normalizedPosition === 'left'
          ? {x: marginX, y: height / 2, alignX: '0%', alignY: '-50%'}
          : normalizedPosition === 'right'
            ? {x: width - marginX, y: height / 2, alignX: '-100%', alignY: '-50%'}
            : normalizedPosition === 'tl' || normalizedPosition === 'lt'
              ? {x: marginX, y: marginY, alignX: '0%', alignY: '0%'}
              : normalizedPosition === 'tr' || normalizedPosition === 'rt'
                ? {x: width - marginX, y: marginY, alignX: '-100%', alignY: '0%'}
                : normalizedPosition === 'bl' || normalizedPosition === 'lb'
                  ? {x: marginX, y: height - marginY, alignX: '0%', alignY: '-100%'}
                  : normalizedPosition === 'br' || normalizedPosition === 'rb'
                    ? {x: width - marginX, y: height - marginY, alignX: '-100%', alignY: '-100%'}
                    : {x: width / 2, y: height - marginY, alignX: '-50%', alignY: '-100%'};

  const enterProgress = spring({
    frame,
    fps,
    config: {damping: 14, stiffness: 180, mass: 1},
    durationInFrames: msToFrames(600, fps),
  });

  const containerOpacity = interpolate(
    frame,
    [0, msToFrames(600, fps), exitStart, exitEnd],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );
  const containerX = interpolate(
    enterProgress,
    [0, 1],
    [-30, 0]
  );
  const exitX = interpolate(
    frame,
    [exitStart, exitEnd],
    [0, 30],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  const textOpacity = interpolate(
    frame,
    [msToFrames(300, fps), msToFrames(700, fps)],
    [0.5, 1],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  const authorOpacity = author
    ? interpolate(
        frame,
        [msToFrames(600, fps), msToFrames(1000, fps)],
        [0, 0.7],
        {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
      )
    : 0;
  const authorY = author
    ? interpolate(
        frame,
        [msToFrames(600, fps), msToFrames(1000, fps)],
        [10, 0],
        {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
      )
    : 0;

  const themeStyle = themeStyles[theme];

  return (
    <div style={{width: '100%', height: '100%', position: 'relative'}}>
      <div
        style={{
          position: 'absolute',
          left: anchor.x,
          top: anchor.y,
          width: maxWidth,
          maxWidth,
          padding: '32px 40px',
          opacity: containerOpacity,
          transform: `translate(${anchor.alignX}, ${anchor.alignY}) translate3d(${containerX + exitX}px, 0, 0)`,
          boxSizing: 'border-box',
          ...themeStyle.container,
        }}
      >
        <div style={{fontSize: 72, lineHeight: 1, opacity: 0.3, marginBottom: -20, ...themeStyle.quoteMark}}>
          "
        </div>
        <div
          style={{
            fontSize: 32,
            lineHeight: 1.5,
            fontWeight: 500,
            whiteSpace: 'normal',
            overflowWrap: 'break-word',
            wordBreak: 'break-word',
            opacity: textOpacity,
            ...themeStyle.text,
          }}
        >
          {text}
        </div>
        {author ? (
          <div
            style={{
              marginTop: 16,
              fontSize: 18,
              opacity: authorOpacity,
              transform: `translateY(${authorY}px)`,
              ...themeStyle.author,
            }}
          >
            {author}
          </div>
        ) : null}
      </div>
    </div>
  );
};
