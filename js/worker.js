/* Data Detective - Python lab worker.
 * Runs Pyodide (CPython compiled to WebAssembly) off the main thread, so the page never freezes
 * and an infinite loop can be stopped by simply terminating this worker.
 */
const PYODIDE_VERSION = "0.28.3";
const INDEX_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

let pyodide = null;
let runtime = null;
const loadedFiles = new Set();
const loadedPkgs = new Set();

function post(type, data = {}) { self.postMessage({ type, ...data }); }

async function boot(runtimeUrl) {
  post("status", { stage: "core", text: "Booting Python (first time downloads ~10 MB, then it's cached)…" });
  importScripts(INDEX_URL + "pyodide.js");
  pyodide = await loadPyodide({ indexURL: INDEX_URL });
  pyodide.runPython(`import os; os.environ["MPLBACKEND"] = "Agg"; os.makedirs("/home/pyodide/lab", exist_ok=True); os.chdir("/home/pyodide/lab")`);
  const src = await (await fetch(runtimeUrl)).text();
  pyodide.FS.writeFile("/home/pyodide/dd_runtime.py", src);
  pyodide.runPython(`import sys; sys.path.insert(0, "/home/pyodide"); import dd_runtime`);
  runtime = pyodide.pyimport("dd_runtime");
}

async function ensurePackages(pkgs) {
  const need = pkgs.filter((p) => !loadedPkgs.has(p));
  if (!need.length) return;
  post("status", { stage: "packages", text: `Loading ${need.join(" + ")} into the lab…` });
  await pyodide.loadPackage(need);
  need.forEach((p) => loadedPkgs.add(p));
}

async function ensureFiles(files) {
  for (const f of files) {
    if (loadedFiles.has(f.name)) continue;
    const buf = await (await fetch(f.url)).arrayBuffer();
    pyodide.FS.writeFile("/home/pyodide/lab/" + f.name, new Uint8Array(buf));
    loadedFiles.add(f.name);
  }
}

self.onmessage = async (ev) => {
  const msg = ev.data;
  try {
    if (msg.type === "boot") {
      await boot(msg.runtimeUrl);
      post("ready", { version: PYODIDE_VERSION });
    } else if (msg.type === "prepare") {
      await ensurePackages(msg.packages || []);
      await ensureFiles(msg.files || []);
      post("prepared", { id: msg.id });
    } else if (msg.type === "run") {
      await ensurePackages(msg.packages || []);
      await ensureFiles(msg.files || []);
      // auto-load anything else the player imports (e.g. numpy in an early case)
      const all = (msg.prelude || []).join("\n") + "\n" + msg.code;
      try {
        await pyodide.loadPackagesFromImports(all);
      } catch (e) { /* unknown module: Python will raise a friendly ModuleNotFoundError */ }
      post("running", { id: msg.id });
      const fn = msg.check ? runtime.run_step : runtime.run_step;
      const res = fn(pyodide.toPy(msg.prelude || []), msg.code, msg.check || null);
      const js = res.toJs({ dict_converter: Object.fromEntries });
      res.destroy();
      post("result", { id: msg.id, result: js });
    }
  } catch (err) {
    post("fatal", { id: msg.id, error: String(err && err.message ? err.message : err) });
  }
};
