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

// absolute path instead of PATH lookup; CI runners and local JDK installs set JAVA_HOME
if (!process.env.JAVA_HOME) {
  console.error("❌ JAVA_HOME is not set – the HTML validation needs Java");
  process.exit(1);
}
const java = path.join(process.env.JAVA_HOME, "bin", "java");

try {
  execFileSync(java, ["-jar", vnu, "--errors-only", "--also-check-svg", ...files], { stdio: "inherit" });
} catch {
  console.error("❌ HTML validation failed");
  process.exit(1);
}
console.log(`✅ HTML valid (${files.length} pages)`);
