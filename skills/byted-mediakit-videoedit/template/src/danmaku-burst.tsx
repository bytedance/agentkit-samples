import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

export type DanmakuBurstTheme = 'notion' | 'cyberpunk' | 'apple' | 'aurora' | 'douyin';

export type DanmakuBurstProps = {
  messages: string[];
  highlight?: string;
  theme?: DanmakuBurstTheme;
  durationMs?: number;
};

const msToFrames = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

// Deterministic pseudo-random based on index
const pseudoRandom = (seed: number) => {
  const x = Math.sin(seed * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};

const messageColors: Record<DanmakuBurstTheme, string[]> = {
  douyin: ['#FFFFFF', '#25F4EE', '#FE2C55', '#FFFFFF', '#FFD700'],
  notion: ['#37352F', '#E16259', '#0B6E99', '#DFAB01', '#37352F'],
  cyberpunk: ['#00F5FF', '#FF00FF', '#FFFF00', '#00F5FF', '#FF00FF'],
  apple: ['#FFFFFF', '#0071E3', '#FFFFFF', '#34C759', '#FFFFFF'],
  aurora: ['#667EEA', '#F093FB', '#4FACFE', '#F5576C', '#FFD194'],
};

const messageShadows: Record<DanmakuBurstTheme, string> = {
  douyin: '1px 1px 3px rgba(0,0,0,0.8), -1px -1px 3px rgba(0,0,0,0.8)',
  notion: '1px 1px 2px rgba(0,0,0,0.3)',
  cyberpunk: '0 0 8px currentColor, 0 0 16px currentColor',
  apple: '0 2px 10px rgba(0,0,0,0.4)',
  aurora: '0 0 12px rgba(102,126,234,0.6)',
};

const highlightThemes: Record<DanmakuBurstTheme, React.CSSProperties> = {
  douyin: {
    color: '#FFFFFF',
    textShadow: '-3px 0 0 #25F4EE, 3px 0 0 #FE2C55, 0 0 20px rgba(255,255,255,0.4)',
    WebkitTextStroke: '1px rgba(0,0,0,0.5)',
    fontFamily: '"Montserrat", "PingFang SC", sans-serif',
    fontWeight: 900,
  },
  notion: {
    color: '#37352F',
    background: 'linear-gradient(180deg, transparent 50%, #FBF3DB 50%)',
    padding: '0 12px',
    fontFamily: '"Georgia", "Noto Serif SC", serif',
    fontWeight: 700,
  },
  cyberpunk: {
    color: '#00F5FF',
    textShadow: '0 0 10px #00F5FF, 0 0 30px #00F5FF, 0 0 60px #FF00FF',
    fontFamily: '"Orbitron", "STHeiti", sans-serif',
    fontWeight: 900,
    letterSpacing: '0.05em',
  },
  apple: {
    color: '#FFFFFF',
    textShadow: '0 2px 20px rgba(0,0,0,0.5)',
    fontFamily: '-apple-system, "SF Pro Display", "PingFang SC", sans-serif',
    fontWeight: 700,
    letterSpacing: '-0.02em',
  },
  aurora: {
    background: 'linear-gradient(135deg, #667EEA 0%, #764BA2 50%, #F093FB 100%)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    backgroundClip: 'text',
    filter: 'drop-shadow(0 4px 20px rgba(102,126,234,0.5))',
    fontFamily: '"Avenir Next", "PingFang SC", sans-serif',
    fontWeight: 700,
  },
};

export const DanmakuBurst: React.FC<DanmakuBurstProps> = ({
  messages,
  highlight,
  theme = 'douyin',
  durationMs = 3000,
}) => {
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const totalFrames = Math.min(durationInFrames, msToFrames(durationMs, fps));
  const exitStart = totalFrames - msToFrames(400, fps);

  const colors = messageColors[theme];
  const shadow = messageShadows[theme];

  // Limit to 8 messages max, spread across the height
  const visibleMessages = messages.slice(0, 8);
  const rowCount = visibleMessages.length;

  return (
    <div style={{width: '100%', height: '100%', position: 'relative', overflow: 'hidden'}}>
      {/* Floating danmaku rows */}
      {visibleMessages.map((msg, idx) => {
        // Stagger start: each message starts slightly after the previous
        const staggerMs = idx * 180;
        const staggerFrames = msToFrames(staggerMs, fps);
        const localFrame = Math.max(frame - staggerFrames, 0);
        const rowDurationFrames = Math.max(totalFrames - staggerFrames, msToFrames(1000, fps));

        // Vertical position: spread rows evenly, offset slightly for variety
        const rowSpacing = height / (rowCount + 1);
        const yBase = rowSpacing * (idx + 1);
        const yOffset = (pseudoRandom(idx * 3 + 1) - 0.5) * rowSpacing * 0.3;
        const y = yBase + yOffset;

        // Horizontal: fly from right to left
        // Start off-screen right, travel past left edge
        const travelDistance = width + 400;
        const startX = width + 100 + pseudoRandom(idx * 5) * 200;
        const endX = -300;

        const xProgress = interpolate(
          localFrame,
          [0, rowDurationFrames],
          [startX, endX],
          {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
        );

        const opacity = interpolate(
          frame,
          [staggerFrames, staggerFrames + msToFrames(200, fps), exitStart, totalFrames],
          [0, 1, 1, 0],
          {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
        );

        const color = colors[idx % colors.length];
        const fontSize = 22 + pseudoRandom(idx * 7) * 10;

        return (
          <div
            key={idx}
            style={{
              position: 'absolute',
              top: y,
              left: xProgress,
              transform: 'translateY(-50%)',
              fontSize,
              fontWeight: 700,
              color,
              textShadow: shadow,
              fontFamily: '"STHeiti", "Heiti SC", "Microsoft YaHei", "PingFang SC", sans-serif',
              whiteSpace: 'nowrap',
              opacity,
              willChange: 'transform',
            }}
          >
            {msg}
          </div>
        );
      })}

      {/* Optional centered highlight text */}
      {highlight ? (
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
            fontSize: 72,
            fontWeight: 900,
            textAlign: 'center',
            whiteSpace: 'nowrap',
            opacity: interpolate(
              frame,
              [msToFrames(200, fps), msToFrames(600, fps), exitStart, totalFrames],
              [0, 1, 1, 0],
              {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
            ),
            transform: `translate(-50%, -50%) scale(${interpolate(
              frame,
              [msToFrames(200, fps), msToFrames(500, fps)],
              [0.5, 1.0],
              {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
            )})`,
            ...highlightThemes[theme],
          }}
        >
          {highlight}
        </div>
      ) : null}
    </div>
  );
};
