/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_NETWORK: string;
  readonly VITE_API_ENDPOINT: string;
  readonly VITE_NODE_URL: string;
  readonly VITE_EXPLORER_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
  readonly DEV: boolean;
}
