import { execFileSync } from "node:child_process";

const ports = [8123, 5173];

function run(command, args) {
  try {
    return execFileSync(command, args, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
  } catch {
    return "";
  }
}

function killPid(pid) {
  if (!pid || pid === String(process.pid)) return;
  try {
    if (process.platform === "win32") {
      execFileSync("taskkill", ["/PID", pid, "/F"], { stdio: "ignore" });
    } else {
      process.kill(Number(pid), "SIGTERM");
    }
  } catch {
    // Process may have already exited.
  }
}

if (process.platform === "win32") {
  const output = run("netstat", ["-ano", "-p", "tcp"]);
  for (const line of output.split(/\r?\n/)) {
    if (!line.includes("LISTENING")) continue;
    for (const port of ports) {
      if (line.includes(`:${port}`)) {
        killPid(line.trim().split(/\s+/).at(-1));
      }
    }
  }
} else {
  for (const port of ports) {
    const output = run("lsof", ["-ti", `tcp:${port}`]);
    for (const pid of output.split(/\s+/).filter(Boolean)) {
      killPid(pid);
    }
  }
}
