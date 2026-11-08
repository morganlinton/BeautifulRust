// Bundles the server, its dependencies, and the generated data into one ES
// module for the Vercel Function in api/index.mjs.
import { mkdir, writeFile } from "node:fs/promises";
import { build } from "esbuild";

await build({
  entryPoints: ["src/index.ts"],
  outfile: "build/server.mjs",
  bundle: true,
  format: "esm",
  platform: "node",
  target: "node22",
  legalComments: "none",
  logLevel: "info",
});
// Vercel expects a static output directory; the function serves every path.
await mkdir("public", { recursive: true });
await writeFile("public/robots.txt", "User-agent: *\nAllow: /\n");
