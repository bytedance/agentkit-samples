export interface EmbeddedWebAsset {
  body: Buffer;
  contentType: string;
}

// The binary build replaces this module with generated Vite assets.
export const embeddedWebAssets = new Map<string, EmbeddedWebAsset>();
