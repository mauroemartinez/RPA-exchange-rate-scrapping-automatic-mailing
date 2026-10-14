// Tests del Worker sin red: `fetch` falso. Se corren con `node --test` desde esta carpeta (o `npm test`).
import assert from "node:assert/strict";
import { test } from "node:test";

import worker from "./disparador.js";

const env = { REPO: "alguien/repo", RAMA: "main", CRON_CONTROL: "43 22 * * 1-5", GITHUB_TOKEN: "token-de-prueba" };

function conRespuestas(...estados) {
  const pedidos = [];
  globalThis.fetch = async (url, opciones) => {
    pedidos.push({ url, opciones });
    const status = estados.shift() ?? 204;
    return { status, text: async () => `cuerpo ${status}` };
  };
  return pedidos;
}

// Sin esperas reales entre reintentos
globalThis.setTimeout = (seguir) => seguir();

test("el horario de la corrida pide corrida-diaria.yml en modo real", async () => {
  const pedidos = conRespuestas(204);
  await worker.scheduled({ cron: "0 19 * * 1-5" }, env);
  assert.equal(pedidos.length, 1);
  assert.equal(pedidos[0].url, "https://api.github.com/repos/alguien/repo/actions/workflows/corrida-diaria.yml/dispatches");
  assert.equal(pedidos[0].opciones.method, "POST");
  assert.equal(pedidos[0].opciones.headers.Authorization, "Bearer token-de-prueba");
  assert.deepEqual(JSON.parse(pedidos[0].opciones.body), { ref: "main", inputs: { modo: "real" } });
});

test("el horario del control pide control-diario.yml con la alerta prendida", async () => {
  const pedidos = conRespuestas(204);
  await worker.scheduled({ cron: env.CRON_CONTROL }, env);
  assert.match(pedidos[0].url, /control-diario\.yml\/dispatches$/);
  assert.deepEqual(JSON.parse(pedidos[0].opciones.body), { ref: "main", inputs: { alertar: "true" } });
});

test("un 5xx se reintenta y la invocación termina bien si GitHub se recupera", async () => {
  const pedidos = conRespuestas(502, 204);
  await worker.scheduled({ cron: "0 19 * * 1-5" }, env);
  assert.equal(pedidos.length, 2);
});

test("un 401 no se reintenta y la invocación falla con el motivo", async () => {
  const pedidos = conRespuestas(401);
  await assert.rejects(worker.scheduled({ cron: "0 19 * * 1-5" }, env), /HTTP 401/);
  assert.equal(pedidos.length, 1);
});

test("sin el secreto no se llama a GitHub", async () => {
  const pedidos = conRespuestas(204);
  await assert.rejects(worker.scheduled({ cron: "0 19 * * 1-5" }, { ...env, GITHUB_TOKEN: undefined }), /GITHUB_TOKEN/);
  assert.equal(pedidos.length, 0);
});
