export interface ComposerKeyEvent {
  key: string;
  isComposing: boolean;
  keyCode: number;
}

export function isImeComposerKey(
  event: ComposerKeyEvent,
  compositionActive: boolean,
  compositionJustEnded: boolean,
): boolean {
  return (
    compositionActive ||
    event.isComposing ||
    event.keyCode === 229 ||
    (compositionJustEnded && event.key === "Enter")
  );
}
