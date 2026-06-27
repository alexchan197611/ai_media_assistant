import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join } from "node:path";

const root = process.cwd();
const candidates = process.platform === "win32"
  ? [join(root, ".venv", "Scripts", "python.exe"), "python"]
  : [join(root, ".venv", "bin", "python"), "python3", "python"];

const python = candidates.find(candidate => candidate === "python" || candidate === "python3" || existsSync(candidate));
if (!python) {
  console.error("未找到 Python。请先运行对应系统的 setup 脚本。");
  process.exit(1);
}

const result = spawnSync(python, process.argv.slice(2), {
  stdio: "inherit",
  shell: false,
  env: process.env,
});

process.exit(result.status ?? 1);
