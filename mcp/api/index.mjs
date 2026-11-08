// The Vercel Function. `npm run build` bundles src/ and the generated data into
// build/server.mjs; this file only re-exports it, so Vercel never compiles the
// TypeScript itself.
export { default } from "../build/server.mjs";
