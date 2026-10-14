/**
 * Dispara la corrida diaria del reporte en GitHub Actions, a horario, desde Cloudflare.
 *
 * POR QUÉ: el horario propio de GitHub (schedule) es "best effort" en el plan
 * gratis y llegó con horas de atraso o no llegó (08, 09, 10 y 12/10/2026). La
 * orden manual (workflow_dispatch) arranca en segundos. Hasta ahora la mandaba la
 * tarea de Windows de la PC del mantenedor, que no sirve con la PC apagada. Los
 * horarios (Cron Triggers) de Cloudflare son puntuales y gratis, y no dependen de
 * ninguna máquina propia.
 *
 * QUÉ HACE: en cada horario de wrangler.toml, un POST a la API de GitHub con la
 * orden. Tres de los horarios piden la corrida en modo real (la misma corrida,
 * sin --forzar: si el día ya salió, encuentra la fila y termina como omitida sin
 * mandar nada; los feriados los saltea sola). El último pide el control, que
 * avisa por mail si el día hábil quedó sin fila.
 *
 * Si GitHub no responde, reintenta dos veces con 30 s de espera. Si aun así no
 * se pudo, la invocación termina con error y queda marcada así en el panel de
 * Cloudflare. Una respuesta 401 o 403 es el token vencido o sin permiso, y 404,
 * el workflow o el repo mal escritos: eso no se reintenta.
 *
 * Variables: REPO, RAMA y CRON_CONTROL salen de wrangler.toml; GITHUB_TOKEN es
 * un secreto del Worker (`wrangler secret put GITHUB_TOKEN`), un fine-grained
 * PAT con permiso Actions de lectura y escritura solo sobre este repo.
 */

const CORRIDA = { workflow: "corrida-diaria.yml", inputs: { modo: "real" } };
const CONTROL = { workflow: "control-diario.yml", inputs: { alertar: "true" } };

const INTENTOS = 3;
const ESPERA_MS = 30_000;

export default {
  async scheduled(evento, env) {
    const orden = evento.cron === env.CRON_CONTROL ? CONTROL : CORRIDA;
    await disparar(orden, env, evento.cron);
  },
};

async function disparar(orden, env, cron) {
  if (!env.GITHUB_TOKEN) {
    throw new Error("Falta el secreto GITHUB_TOKEN: npx wrangler secret put GITHUB_TOKEN");
  }
  const url = `https://api.github.com/repos/${env.REPO}/actions/workflows/${orden.workflow}/dispatches`;
  const pedido = {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      "User-Agent": "reporte-macro-disparador",
    },
    body: JSON.stringify({ ref: env.RAMA, inputs: orden.inputs }),
  };

  let ultimo = "";
  for (let intento = 1; intento <= INTENTOS; intento++) {
    try {
      const respuesta = await fetch(url, pedido);
      if (respuesta.status === 204) {
        console.log(`${cron}: ${orden.workflow} disparado en ${env.REPO}`);
        return;
      }
      const detalle = (await respuesta.text()).replace(/\s+/g, " ").slice(0, 200);
      ultimo = `HTTP ${respuesta.status} ${detalle}`;
      if (respuesta.status < 500) break; // credenciales o configuración: reintentar no cambia nada
    } catch (error) {
      ultimo = `${error.name}: ${error.message}`;
    }
    console.warn(`${cron}: intento ${intento} de ${INTENTOS} falló (${ultimo})`);
    if (intento < INTENTOS) await new Promise((seguir) => setTimeout(seguir, ESPERA_MS));
  }
  throw new Error(`${orden.workflow} no se pudo disparar: ${ultimo}`);
}
