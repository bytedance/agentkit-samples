import React, {useLayoutEffect} from 'react';
import {Composition, getInputProps} from 'remotion';
import {ChapterTitle} from './chapter-title';
import {DanmakuBurst} from './danmaku-burst';
import {FancyText} from './fancy-text';
import {LowerThird} from './lower-third';
import {QuoteCallout} from './quote-callout';

const msToFrames = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

const defaultFps = 30;
const inputProps = getInputProps() as {config?: {videoInfo?: {width?: number; height?: number}}};
const previewVideoInfo = inputProps?.config?.videoInfo ?? {};
const previewWidth =
  typeof previewVideoInfo.width === 'number' ? previewVideoInfo.width : 1920;
const previewHeight =
  typeof previewVideoInfo.height === 'number' ? previewVideoInfo.height : 1080;

const RenderFrameFix: React.FC = () => {
  useLayoutEffect(() => {
    const original = window.requestAnimationFrame;
    window.requestAnimationFrame = (cb: FrameRequestCallback) =>
      window.setTimeout(() => cb(performance.now()), 0);
    return () => {
      window.requestAnimationFrame = original;
    };
  }, []);
  return null;
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <RenderFrameFix />
      <Composition
        id="ChapterTitle"
        component={ChapterTitle}
        durationInFrames={msToFrames(4000, defaultFps)}
        fps={defaultFps}
        width={previewWidth}
        height={previewHeight}
        defaultProps={{
          number: 'Part 1',
          title: '精彩时刻',
          subtitle: '弹幕高能区间',
          theme: 'douyin',
          durationMs: 4000,
        }}
      />
      <Composition
        id="fancy-text"
        component={FancyText}
        durationInFrames={msToFrames(2000, defaultFps)}
        fps={defaultFps}
        width={previewWidth}
        height={previewHeight}
        defaultProps={{
          text: '666',
          style: 'emphasis',
          theme: 'douyin',
          position: 'top',
          durationMs: 2000,
          safeMargin: 24,
        }}
      />
      <Composition
        id="lower-third"
        component={LowerThird}
        durationInFrames={msToFrames(5000, defaultFps)}
        fps={defaultFps}
        width={previewWidth}
        height={previewHeight}
        defaultProps={{
          name: 'UP主昵称',
          role: '游戏区',
          company: 'bilibili',
          theme: 'douyin',
          durationMs: 5000,
        }}
      />
      <Composition
        id="quote-callout"
        component={QuoteCallout}
        durationInFrames={msToFrames(5000, defaultFps)}
        fps={defaultFps}
        width={previewWidth}
        height={previewHeight}
        defaultProps={{
          text: '这一波操作太丝滑了',
          author: '— 弹幕金句',
          theme: 'douyin',
          position: 'bottom',
          durationMs: 5000,
        }}
      />
      <Composition
        id="danmaku-burst"
        component={DanmakuBurst}
        durationInFrames={msToFrames(3000, defaultFps)}
        fps={defaultFps}
        width={previewWidth}
        height={previewHeight}
        defaultProps={{
          messages: ['666', '哈哈哈', '绝了', '牛啊', '名场面', 'awsl'],
          highlight: '名场面',
          theme: 'douyin',
          durationMs: 3000,
        }}
      />
    </>
  );
};
