/*
 * W3C validation of the built HTML (Nu Html Checker via vnu-jar, needs Java).
 * Fails the build on any validation error.
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import vnu from "vnu-jar";

const rootDir = (process.argv[2] || "public").replace(/\/$/, "");
const files = (await fs.readdir(rootDir, { recursive: true }))
  .filter((f) => f.endsWith(".html"))
  .map((f) => path.join(rootDir, f));

try {
  execFileSync("java", ["-jar", vnu, "--errors-only", "--also-check-svg", ...files], { stdio: "inherit" });
} catch {
  console.error("❌ HTML validation failed");
  process.exit(1);
}
console.log(`✅ HTML valid (${files.length} pages)`);
