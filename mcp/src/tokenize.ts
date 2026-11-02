// Mirrors tokenize() in scripts/build-mcp-data.py, which indexes the guidance
// with the same rules. test/tokenize.test.ts checks both against the samples
// the build script writes into guidance.json.

const TOKEN_RE = /[a-z0-9_]+/g;
const STOPWORDS = new Set(
  (
    "a an and are as at be by do does for from how i if in is it its of on or " +
    "should that the this to use what when which why with you your"
  ).split(" "),
);

export function tokenize(text: string): string[] {
  const tokens: string[] = [];
  for (const raw of text.toLowerCase().match(TOKEN_RE) ?? []) {
    const parts = [raw];
    if (raw.includes("_")) {
      parts.push(...raw.split("_").filter((p) => p.length > 0));
    }
    for (let token of parts) {
      if (token.length < 2 || STOPWORDS.has(token)) {
        continue;
      }
      if (token.length > 4 && token.endsWith("s") && !token.endsWith("ss")) {
        token = token.slice(0, -1);
      }
      tokens.push(token);
    }
  }
  return tokens;
}
