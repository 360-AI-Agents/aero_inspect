import { Container, getContainer } from "@cloudflare/containers";
import { env } from "cloudflare:workers";

export { ContainerProxy } from "@cloudflare/containers";

// Statements run immediately as they arrive; there is no cross-statement
// rollback here (see backend/db_d1.py docstring for why).
async function runD1(request, workerEnv) {
  if (request.headers.get("x-d1-proxy-secret") !== workerEnv.D1_PROXY_SECRET) {
    return json({ ok: false, error: "unauthorized" }, 401);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "invalid JSON body" }, 400);
  }

  const sanitize = (params) =>
    (params || []).map((p) => (typeof p === "boolean" ? (p ? 1 : 0) : p));

  const db = workerEnv.aeroinspect_db;

  try {
    if (Array.isArray(body.batch)) {
      const stmts = body.batch.map((s) => db.prepare(s.sql).bind(...sanitize(s.params)));
      const out = await db.batch(stmts);
      return json({
        ok: true,
        batch: out.map((r) => ({
          results: r.results || [],
          meta: { changes: r.meta?.changes, last_row_id: r.meta?.last_row_id },
        })),
      });
    }

    const stmt = db.prepare(body.sql).bind(...sanitize(body.params));
    const result = await stmt.all();
    return json({
      ok: true,
      results: result.results || [],
      meta: {
        changes: result.meta?.changes,
        last_row_id: result.meta?.last_row_id,
      },
    });
  } catch (e) {
    return json({ ok: false, error: String(e) }, 500);
  }
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json" },
  });
}

export class Backend extends Container {
  defaultPort = 8000;
  sleepAfter = "30m";
  enableInternet = false;
  envVars = {
    DATABASE_URL: "sqlite+d1http://d1.internal/",
    D1_PROXY_SECRET: env.D1_PROXY_SECRET,
    ALLOWED_ORIGINS: "*",
  };
}

// NOTE: must be a plain assignment after the class declaration, not a
// `static outboundByHost = {...}` class field inside the class body — class
// fields create an own property via [[DefineOwnProperty]] and never invoke
// the inherited static setter that Container defines for this, so the
// handler silently never registers and every request falls through to
// "Origin is disallowed".
Backend.outboundByHost = {
  "d1.internal": (request, workerEnv) => runD1(request, workerEnv),
};

export default {
  async fetch(request, env) {
    const container = getContainer(env.BACKEND, "main");
    return container.fetch(request);
  },
};
