import { mkdir, copyFile } from "node:fs/promises";
const destination = new URL("../local_ai/static/vendor/", import.meta.url);
await mkdir(destination, { recursive: true });
for (const [source, target] of [
  ["node_modules/marked/lib/marked.umd.js", "marked.umd.js"],
  ["node_modules/marked/LICENSE", "marked.LICENSE.md"],
  ["node_modules/dompurify/dist/purify.min.js", "purify.min.js"],
  ["node_modules/dompurify/LICENSE", "DOMPurify.LICENSE"],
])
  await copyFile(
    new URL("../" + source, import.meta.url),
    new URL(target, destination),
  );
console.log("UI libraries copied for offline serving.");
