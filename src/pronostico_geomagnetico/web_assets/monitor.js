"use strict";

const el = id => document.getElementById(id);
const texto = (id, valor) => { el(id).textContent = valor; };
const numero = (valor, decimales = 2) => valor == null ? "—" : Number(valor).toLocaleString("es-ES", {
  minimumFractionDigits: decimales, maximumFractionDigits: decimales
});
const fecha = new Intl.DateTimeFormat("es-ES", { timeZone: "UTC", day: "numeric", month: "short",
  hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const sello = marca => marca ? marca.slice(0, 19).replace("T", " ") + " UTC" : "—";
const intervalo = (inicio, fin) => inicio && fin
  ? fecha.format(new Date(inicio)) + " – " + fecha.format(new Date(fin)) + " UTC" : "—";
const horasMinutos = segundos => {
  if (segundos == null) return "—";
  const min = Math.floor(segundos / 60);
  if (min < 1) return Math.floor(segundos) + " s";
  return min >= 60 ? Math.floor(min / 60) + " h " + min % 60 + " min" : min + " min";
};
const motivos = {
  fuente_no_disponible: "No se pudo consultar la fuente. Vuelve a intentarlo.",
  datos_incompletos: "GFZ aún no contiene los tres bloques requeridos. Vuelve a consultar tras unos minutos.",
  datos_caducados: "El último bloque encontrado cerró hace más de tres horas.",
  cambio_bloque: "Empezó el bloque durante la consulta. Actualiza para calcular el siguiente.",
  modelo_no_disponible: "El modelo local no está cargado.",
  reloj_inconsistente: "El reloj del servidor cambió durante la consulta. Vuelve a intentarlo.",
  inferencia_invalida: "El modelo devolvió un valor fuera de la escala de Kp.",
  archivo_omni_invalido: "El archivo OMNI no se pudo procesar.",
  ventanas_omni_incompletas: "El archivo falta o no tiene ventanas completas para ese día."
};

async function api(url, method = "GET") {
  const respuesta = await fetch(url, { method });
  if (!respuesta.ok) {
    const datos = await respuesta.json().catch(() => ({}));
    throw new Error(typeof datos.detail === "string" ? datos.detail : "Error HTTP " + respuesta.status + ".");
  }
  return respuesta.json();
}

async function accion(boton, estado, ejecutar, inicio = "Consultando…") {
  boton.disabled = true;
  if (estado) texto(estado, inicio);
  try { await ejecutar(); }
  catch (error) { if (estado) texto(estado, error.message); }
  finally { boton.disabled = false; }
}

function badge(id, leyenda, estado) {
  texto(id, leyenda);
  el(id).dataset.estado = estado;
}

function nodo(etiqueta, valor) {
  const elemento = document.createElement(etiqueta);
  if (valor !== undefined) elemento.textContent = valor;
  return elemento;
}

const SERIES = [
  { campo: "kp_persistencia", etiqueta: "Persistencia", color: "#a4b9fa", trazo: [5, 5] },
  { campo: "kp_observado", etiqueta: "Observado", color: "#ffd38a", trazo: [] },
  { campo: "kp_previsto", etiqueta: "Previsto", color: "#76e4d1", trazo: [] }
];

function grafica(id, filas, campos = SERIES) {
  const area = el(id);
  area.resize?.disconnect();
  area.replaceChildren();
  const dispersion = area.dataset.grafica === "dispersion";
  const datos = dispersion ? filas.filter(r => r.kp_observado != null && r.kp_previsto != null) : filas;
  if (!datos.some(r => campos.some(c => r[c.campo] != null))) {
    const aviso = nodo("p", "Sin valores para mostrar en este periodo.");
    aviso.className = "vacio";
    area.append(aviso);
    return;
  }
  const figura = nodo("figure");
  const canvas = nodo("canvas");
  canvas.tabIndex = 0;
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", dispersion ? "Kp observado frente a previsto. Usa las flechas para recorrer puntos."
    : "Serie temporal UTC de Kp. Usa las flechas para recorrer bloques.");
  const info = nodo("output", "Pasa el cursor o usa ← → para consultar los valores.");
  figura.append(canvas, info);
  area.append(figura);
  const ctx = canvas.getContext("2d");
  const tiempos = datos.map(r => Date.parse(r.objetivo_inicio));
  let seleccion = -1;
  let posiciones = [];

  function dibujar() {
    const w = canvas.clientWidth, h = canvas.clientHeight, escala = devicePixelRatio || 1;
    if (!w || !h) return;
    canvas.width = w * escala;
    canvas.height = h * escala;
    ctx.scale(escala, escala);
    const l = 33, d = w - 19, t = 14, b = h - 35;
    const y = kp => b - (b - t) * kp / 9;
    const desde = tiempos[0], hasta = tiempos.at(-1);
    const desplazamiento = k => l + (d - l) * k;
    const xt = ms => desplazamiento(hasta === desde ? .5 : (ms - desde) / (hasta - desde));
    const xo = kp => desplazamiento(kp / 9);
    posiciones = datos.map((r, i) => dispersion ? [xo(r.kp_observado), y(r.kp_previsto)] : [xt(tiempos[i]), 0]);
    ctx.font = "11px system-ui";
    ctx.fillStyle = "#b2bfd0";
    ctx.textAlign = "right";
    for (const kp of [0, 3, 5, 7, 9]) {
      ctx.strokeStyle = kp === 5 ? "#795e3d" : "#344258";
      ctx.setLineDash(kp === 5 ? [3, 3] : []);
      ctx.beginPath(); ctx.moveTo(l, y(kp)); ctx.lineTo(d, y(kp)); ctx.stroke();
      ctx.fillText(String(kp), l - 6, y(kp) + 3);
    }
    ctx.setLineDash([]);
    ctx.textAlign = "center";
    if (dispersion) {
      for (const kp of [0, 3, 6, 9]) ctx.fillText(String(kp), xo(kp), b + 14);
      ctx.fillText("Kp observado", (l + d) / 2, b + 28);
      ctx.textAlign = "left";
      ctx.fillText("Kp previsto", l + 8, t + 11);
      ctx.strokeStyle = "#a4b9fa";
      ctx.setLineDash([4, 4]);
      ctx.beginPath(); ctx.moveTo(xo(0), y(0)); ctx.lineTo(xo(9), y(9)); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#76e4d1aa";
      for (const [x, v] of posiciones) {
        ctx.beginPath(); ctx.arc(x, v, 3, 0, Math.PI * 2); ctx.fill();
      }
    } else {
      const etiquetas = hasta === desde ? [desde] : [desde, (desde + hasta) / 2, hasta];
      etiquetas.forEach((ms, i) => {
        ctx.textAlign = etiquetas.length === 1 || i === 1 ? "center" : i === 0 ? "left" : "right";
        ctx.fillText(fecha.format(new Date(ms)), xt(ms), b + 18);
      });
      for (const c of campos) {
        ctx.lineWidth = 1.7;
        ctx.strokeStyle = ctx.fillStyle = c.color;
        ctx.setLineDash(c.trazo);
        let anterior = null;
        datos.forEach((r, i) => {
          const valor = r[c.campo];
          if (valor == null) { anterior = null; return; }
          const x = posiciones[i][0], v = y(valor);
          if (anterior && tiempos[i] - anterior[2] <= 10800000) {
            ctx.beginPath(); ctx.moveTo(anterior[0], anterior[1]); ctx.lineTo(x, v); ctx.stroke();
          }
          if (datos.length < 60 || !anterior) {
            ctx.beginPath(); ctx.arc(x, v, 2.5, 0, Math.PI * 2); ctx.fill();
          }
          anterior = [x, v, tiempos[i]];
        });
        ctx.setLineDash([]);
      }
    }
    if (seleccion >= 0) {
      ctx.strokeStyle = "#f3f7fc";
      ctx.lineWidth = 1;
      const [x, v] = posiciones[seleccion];
      ctx.beginPath();
      if (dispersion) ctx.arc(x, v, 6, 0, 2 * Math.PI);
      else { ctx.moveTo(x, t); ctx.lineTo(x, b); }
      ctx.stroke();
    }
  }

  function seleccionar(i) {
    seleccion = i;
    const fila = datos[i];
    const partes = campos.filter(c => fila[c.campo] != null).map(c => c.etiqueta + " " + numero(fila[c.campo]));
    info.textContent = fecha.format(new Date(tiempos[i])) + " UTC · " + (partes.join(" · ") || "sin dato");
    dibujar();
  }
  canvas.addEventListener("pointermove", evento => {
    const rect = canvas.getBoundingClientRect();
    const x = evento.clientX - rect.left, y = evento.clientY - rect.top;
    const distancia = ([px, py]) => dispersion ? Math.hypot(px - x, py - y) : Math.abs(px - x);
    const i = posiciones.reduce((mejor, punto, indice) =>
      distancia(punto) < distancia(posiciones[mejor]) ? indice : mejor, 0);
    if (i !== seleccion) seleccionar(i);
  });
  canvas.addEventListener("keydown", evento => {
    if (!["ArrowLeft", "ArrowRight"].includes(evento.key)) return;
    evento.preventDefault();
    const i = seleccion < 0 ? 0 : seleccion + (evento.key === "ArrowRight" ? 1 : -1);
    seleccionar(Math.max(0, Math.min(datos.length - 1, i)));
  });
  area.resize = new ResizeObserver(dibujar);
  area.resize.observe(canvas);
  dibujar();
}

function filaTabla(contenedor, celdas) {
  const fila = nodo("tr");
  for (const celda of celdas) {
    const td = nodo("td");
    if (celda instanceof Node) td.append(celda);
    else td.textContent = celda;
    fila.append(td);
  }
  contenedor.append(fila);
}

function estadoObservacion(r) {
  if (r.estado === "disponible") return "Kp " + numero(r.kp_observado) + " · " +
    (r.calidad === "def" ? "definitivo" : "provisional") + " · " + sello(r.objetivo_inicio);
  return {
    bloque_abierto: "El bloque sigue abierto.",
    observacion_pendiente: "GFZ aún no ofrece un valor válido para ese bloque.",
    fuente_no_disponible: "GFZ no está disponible."
  }[r.estado] || "Observación no disponible.";
}

let vencimiento;
function mostrarDirecto(r) {
  clearTimeout(vencimiento);
  const valido = r.estado === "emitido";
  badge("estado-pronostico", valido ? "Emitido" : "Sin pronóstico", valido ? "bueno" : "aviso");
  texto("kp-operativo", numero(r.kp_previsto));
  texto("intervalo", intervalo(r.objetivo_inicio, r.objetivo_fin));
  texto("anticipo", horasMinutos(r.anticipacion_segundos));
  texto("emision", sello(r.emision));
  texto("ventana", intervalo(r.ventana_inicio, r.ventana_fin));
  texto("recepcion", sello(r.recepcion));
  texto("edad", horasMinutos(r.antiguedad_segundos));
  badge("cobertura", r.bloques_validos + "/" + r.bloques_esperados + " bloques", valido ? "bueno" : "aviso");
  texto("mensaje-pronostico", valido ? "Persistencia al emitir: Kp " + numero(r.kp_persistencia) + ". La observación llegará tras el cierre."
    : motivos[r.motivo] || "Pronóstico no disponible.");
  el("mensaje-pronostico").dataset.estado = valido ? "bueno" : "aviso";
  el("marcador").hidden = !valido;
  if (valido) {
    el("marcador").style.left = (100 * r.kp_previsto / 9) + "%";
    vencimiento = setTimeout(() => {
      badge("estado-pronostico", "Bloque iniciado", "aviso");
      texto("kp-operativo", "—");
      texto("anticipo", "—");
      el("marcador").hidden = true;
      texto("mensaje-pronostico", "El intervalo mostrado ya empezó. Actualiza para calcular el próximo.");
    }, Math.max(0, Date.parse(r.objetivo_inicio) - Date.now()));
  }
  el("mediciones").hidden = !valido;
  el("lista-mediciones").replaceChildren(...(r.mediciones || []).map(m => nodo("li",
    intervalo(m.inicio, m.fin) + " · Kp " + numero(m.kp) + (m.calidad === "def" ? " definitivo" : " provisional"))));
}

const metricas = [["MAE", "mae"], ["RMSE", "rmse"], ["R²", "r2"], ["MAE en tormentas", "mae_tormentas"],
  ["Precisión", "precision"], ["Recall", "recall"], ["F1", "f1"]];
function pintarMetricas(id, c, operativo = false) {
  const contenedor = el(id);
  contenedor.replaceChildren();
  if (!c.modelo) return;
  contenedor.append(nodo("h3", operativo ? "Métricas de los pares disponibles" : "Métricas en todo el periodo"));
  const recuento = c.bloques + "/" + c.esperados + " bloques comunes · " + numero(c.cobertura * 100, 1) +
    " % de cobertura · " + c.modelo.tormentas + " tormentas observadas (Kp ≥ 5)";
  contenedor.append(nodo("p", recuento));
  const comparacion = nodo("div");
  comparacion.className = "metric-bars";
  const escalas = [["Error medio global", "mae"], ["Error medio en tormentas", "mae_tormentas"]];
  const maximo = Math.max(1, ...escalas.flatMap(([, k]) => [c.modelo[k], c.persistencia[k]]));
  for (const [titulo, k] of escalas) {
    const grupo = nodo("div");
    grupo.append(nodo("h4", titulo));
    for (const [nombre, valor, clase] of [
      ["Boosting", c.modelo[k], "boosting"], ["Persistencia", c.persistencia[k], "persistencia"]
    ]) {
      const barra = nodo("div");
      barra.className = "metric-bar " + clase;
      const carril = nodo("div"), relleno = nodo("span");
      carril.className = "metric-rail";
      carril.setAttribute("aria-hidden", "true");
      relleno.style.width = valor == null ? "0%" : (100 * valor / maximo) + "%";
      carril.append(relleno);
      barra.append(nodo("span", nombre), carril, nodo("strong", numero(valor, 3)));
      grupo.append(barra);
    }
    comparacion.append(grupo);
  }
  contenedor.append(comparacion);
  const tabla = nodo("table");
  const cabeza = nodo("thead"), cabecera = nodo("tr"), cuerpo = nodo("tbody");
  tabla.append(cabeza, cuerpo);
  cabeza.append(cabecera);
  for (const valor of ["Método", ...metricas.map(m => m[0]), "VN / FP / FN / VP"]) {
    const th = nodo("th", valor); th.scope = "col"; cabecera.append(th);
  }
  for (const [nombre, met] of [["Boosting", c.modelo], ["Persistencia", c.persistencia]]) {
    filaTabla(cuerpo, [nombre, ...metricas.map(([, k]) => numero(met[k], 3)), met.matriz.flat().join(" / ")]);
  }
  const caja = nodo("div"); caja.className = "table-wrap"; caja.append(tabla);
  contenedor.append(caja, nodo("p", "VN: verdaderos negativos · FP: falsos positivos · FN: falsos negativos · VP: verdaderos positivos."));
  if (c.modelo.tormentas && c.modelo.matriz[1][1] === 0) {
    contenedor.append(nodo("p", "Con el umbral de Kp previsto ≥ 5, el Boosting no detectó ninguna tormenta de esta muestra."));
  }
}

async function actualizarSeguimiento() {
  const r = await api("/api/seguimiento?dias=" + el("rango-operativo").value);
  const pares = r.comparacion.bloques;
  const cuenta = (n, singular, plural) => n + " " + (n === 1 ? singular : plural);
  texto("resumen-operativo", (r.estado === "evaluacion_pendiente" ? "Evaluación operativa pendiente" : "Muestra operativa acumulada") +
    " · " + cuenta(r.emisiones, "emisión", "emisiones") + " · " + cuenta(r.serie.length, "bloque único", "bloques únicos") +
    " · " + pares + " con observación (" + cuenta(r.definitivos, "definitiva", "definitivas") + ")");
  grafica("operativa", r.serie);
  pintarMetricas("metricas-operativas", r.comparacion, true);
  const cuerpo = el("tabla-operativa");
  cuerpo.replaceChildren();
  for (const fila of [...r.serie].reverse()) {
    const o = fila.observacion;
    let estado = o ? (o.calidad === "def" ? "Definitivo" : "Provisional") : "Bloque abierto";
    if (fila.cerrado && o?.calidad !== "def") {
      const boton = nodo("button", o ? "Revisar provisional" : "Incorporar Kp");
      boton.className = "secondary";
      boton.type = "button";
      boton.onclick = () => accion(boton, "mensaje-seguimiento", async () => {
        const obs = await api("/api/pronosticos/" + fila.auditoria_id + "/observacion", "POST");
        texto("mensaje-seguimiento", estadoObservacion(obs) + (obs.error_absoluto == null ? ""
          : " · error absoluto " + numero(obs.error_absoluto)));
        await actualizarSeguimiento();
      });
      estado = boton;
    }
    filaTabla(cuerpo, [intervalo(fila.objetivo_inicio, fila.objetivo_fin), numero(fila.kp_previsto),
      numero(fila.kp_persistencia), numero(fila.kp_observado), numero(o?.error_absoluto), estado]);
  }
  return r;
}

el("actualizar").onclick = () => accion(el("actualizar"), "mensaje-pronostico", async () => {
  badge("estado-pronostico", "Consultando GFZ", "aviso");
  try {
    mostrarDirecto(await api("/api/pronostico", "POST"));
  } catch (error) {
    badge("estado-pronostico", "Error de consulta", "aviso");
    throw error;
  }
  await actualizarSeguimiento().catch(error => texto("resumen-operativo", error.message));
});
el("ultimo").onclick = () => accion(el("ultimo"), "obs-ultimo", async () =>
  texto("obs-ultimo", estadoObservacion(await api("/api/observacion"))));
el("rango-operativo").onchange = () => actualizarSeguimiento().catch(error => texto("resumen-operativo", error.message));

let informe = {};
async function periodoInforme() {
  const clave = el("periodo-eval").value;
  const p = informe.periodos[clave];
  if (!p) return;
  const inicio = el("fecha-eval").value, dias = el("dias-eval").value;
  texto("estado-evaluacion", "Cargando periodo…");
  const r = await api("/api/evaluacion/" + clave + "?inicio=" + inicio + "&dias=" + dias);
  texto("estado-evaluacion", p.titulo + " · " + p.inicio + " a " + p.fin_exclusivo + " (fin excluido) · " +
    (clave === "omni" ? "Proyecto II, fechas de evaluación anteriores."
      : "Nowcasts archivados como entradas, Kp definitivo como referencia." +
        (informe.corresponde_modelo_cargado ? "" : " El artefacto cargado difiere del evaluado.")));
  pintarMetricas("metricas-eval", p);
  grafica("eval-linea", r.serie);
  grafica("eval-dispersion", r.serie, [SERIES[1], SERIES[2]]);
}

function cambiarPeriodo() {
  const p = informe.periodos[el("periodo-eval").value];
  const control = el("fecha-eval");
  control.min = p.inicio;
  control.max = new Date(Date.parse(p.fin_exclusivo) - 86400000).toISOString().slice(0, 10);
  control.value = p.dia_demo;
  periodoInforme().catch(error => texto("estado-evaluacion", error.message));
}
el("periodo-eval").onchange = cambiarPeriodo;
el("form-evaluacion").onsubmit = evento => {
  evento.preventDefault();
  accion(evento.currentTarget.querySelector("button"), "estado-evaluacion", periodoInforme);
};

let historico = [];
el("historico-form").onsubmit = evento => {
  evento.preventDefault();
  accion(evento.currentTarget.querySelector("button"), "estado-historico", async () => {
    el("resultado-omni").hidden = true;
    texto("contraste", "");
    const r = await api("/api/historico?dia=" + el("dia-omni").value, "POST");
    if (r.estado !== "reproducido") {
      texto("estado-historico", motivos[r.motivo] || "Reproducción no disponible.");
      return;
    }
    historico = r.serie;
    const predichos = historico.filter(b => b.kp_previsto != null);
    texto("estado-historico", r.fuente + " · " + predichos.length + "/" + historico.length + " bloques calculados.");
    texto("ia", "Respuesta de IA simulada · " + r.ia.texto);
    const cuerpo = el("tabla-omni");
    cuerpo.replaceChildren();
    for (const b of historico) filaTabla(cuerpo, [intervalo(b.objetivo_inicio, b.objetivo_fin), numero(b.kp_previsto), numero(b.kp_observado)]);
    el("bloque-omni").replaceChildren(...predichos.map(b =>
      new Option(intervalo(b.objetivo_inicio, b.objetivo_fin), b.objetivo_inicio)));
    el("resultado-omni").hidden = false;
    grafica("grafica-omni", historico, [SERIES[1], SERIES[2]]);
  });
};
el("contrastar").onclick = () => accion(el("contrastar"), "contraste", async () => {
  const b = el("bloque-omni").value;
  const p = historico.find(r => r.objetivo_inicio === b).kp_previsto;
  const r = await api("/api/observacion?bloque=" + encodeURIComponent(b));
  if (el("bloque-omni").value !== b || el("resultado-omni").hidden) return;
  texto("contraste", estadoObservacion(r) + (r.kp_observado == null ? "" :
    " · error absoluto " + numero(Math.abs(p - r.kp_observado))));
});
el("viento").onclick = () => accion(el("viento"), "estado-viento", async () => {
  const r = await api("/api/viento");
  const detalle = r.motivo === "fuente_no_disponible" ? "No se pudo consultar NOAA." :
    r.minutos_validos + "/" + r.minutos_esperados + " minutos emparejados (" + (r.satelites.join(", ") || "sin satélite común") +
    "). Último minuto válido: " + sello(r.ultimo_dato) + ".";
  texto("estado-viento", detalle);
});

api("/health").then(r => badge("salud", r.modelo_operativo.estado === "cargado" ? "Servicio operativo" :
  "Modelo operativo no disponible", r.modelo_operativo.estado === "cargado" ? "bueno" : "aviso"))
  .catch(() => badge("salud", "Servicio no disponible", "aviso"));
actualizarSeguimiento().then(r => {
  if (r.vigente && !el("actualizar").disabled) mostrarDirecto(r.vigente);
}).catch(error => texto("resumen-operativo", error.message));
api("/api/evaluacion").then(r => {
  informe = r;
  const opciones = Object.entries(r.periodos);
  if (!opciones.length) {
    texto("estado-evaluacion", "El informe todavía no se ha generado.");
    el("form-evaluacion").hidden = true;
    return;
  }
  el("periodo-eval").replaceChildren(...opciones.map(([k, p]) => new Option(p.titulo, k)));
  if (r.periodos.gfz2026) el("periodo-eval").value = "gfz2026";
  cambiarPeriodo();
}).catch(error => texto("estado-evaluacion", error.message));
