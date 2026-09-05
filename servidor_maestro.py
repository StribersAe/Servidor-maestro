import os
import random
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

# Estado en memoria por sala. La configuración visual del dispositivo nunca se almacena aquí.
salas = {}
posiciones_jugadores = {}
estado_partida = {}
salas_balas = {}
salas_cajas = {}
lock_estado = threading.RLock()

MAX_JUGADORES = 5
MAX_ARMAS = 2
MAX_TIPOS_MUNICION = 3
MAX_GRANADAS = 4
MAX_VENDAS = 10
MUNICION_POR_ARMA = {
    "pistola": "ligera", "revolver": "ligera", "uzi": "ligera", "mp5": "ligera",
    "escopeta": "escopeta", "carabina": "pesada", "sniper": "pesada",
    "minigun": "pesada", "lanzacohetes": "cohete",
}


def _jugador_pertenece(codigo, jugador_id):
    return codigo in salas and any(str(j.get("id")) == str(jugador_id) for j in salas[codigo])


def _normalizar_inventario(data):
    armas = data.get("armas", [data.get("arma", "pistola"), None])
    if not isinstance(armas, list):
        armas = ["pistola", None]
    armas = [a if isinstance(a, str) and a else None for a in (armas + [None, None])[:2]]
    armas = [a if a in MUNICION_POR_ARMA else None for a in armas[:2]]
    if all(a is None for a in armas):
        armas[0] = "pistola"

    municion = data.get("municion_tipos", {})
    if not isinstance(municion, dict):
        municion = {}
    municion = {str(k): max(0, int(v)) for k, v in municion.items() if isinstance(v, (int, float))}
    municion = dict(list(municion.items())[:MAX_TIPOS_MUNICION])

    granadas = data.get("granadas", {})
    if not isinstance(granadas, dict):
        granadas = {}
    gd = max(0, int(granadas.get("granada_dano", 0)))
    gh = max(0, int(granadas.get("granada_humo", 0)))
    total_g = min(MAX_GRANADAS, gd + gh)
    if gd + gh > total_g:
        exceso = gd + gh - total_g
        gh = max(0, gh - exceso)
    granadas = {"granada_dano": gd, "granada_humo": gh}

    return {
        "armas": armas,
        "arma_slot": 0 if int(data.get("arma_slot", 0)) not in (0, 1) else int(data.get("arma_slot", 0)),
        "cargador": max(0, int(data.get("cargador", 0))),
        "reserva": max(0, int(data.get("reserva", 0))),
        "vendas": min(MAX_VENDAS, max(0, int(data.get("vendas", 0)))),
        "granadas": granadas,
        "municion_tipos": municion,
    }


def _serializar_cajas(codigo):
    salida = []
    for caja in salas_cajas.get(codigo, []):
        salida.append({
            "id": caja.get("id"),
            "x": caja.get("x", 0), "y": caja.get("y", 0),
            "w": caja.get("w", 50), "h": caja.get("h", 50),
            "abierta": bool(caja.get("abierta", False)),
            "contenido": caja.get("contenido", []),
        })
    return salida


@app.route('/')
def home():
    return "¡El servidor de Battle Royale multijugador está activo y funcionando correctamente!"


@app.route('/crear_sala', methods=['POST'])
def crear_sala():
    data = request.json or {}
    nombre_creador = data.get("jugador") or data.get("nombre", "Anónimo")
    id_jugador = str(data.get("id_jugador", nombre_creador))
    with lock_estado:
        codigo = str(data.get("codigo", random.randint(1000, 9999))).upper()
        while codigo in salas:
            codigo = str(random.randint(1000, 9999))
        salas[codigo] = [{"id": id_jugador, "nombre": nombre_creador}]
        posiciones_jugadores[codigo] = {}
        estado_partida[codigo] = {"iniciada": False, "estado": "LOBBY", "listos": {id_jugador: False}}
        salas_balas[codigo] = []
        salas_cajas[codigo] = []
    return jsonify({"exito": True, "codigo": codigo, "total": 1, "mensaje": "Sala creada con éxito"})


@app.route('/unirse_sala', methods=['POST'])
def unirse_sala():
    data = request.json or {}
    codigo = str(data.get("codigo", "")).upper()
    nombre_jugador = data.get("jugador") or data.get("nombre", "Jugador")
    jugador_id = str(data.get("id_jugador", nombre_jugador))
    with lock_estado:
        if not codigo or codigo not in salas:
            return jsonify({"exito": False, "error": "La sala no existe"}), 404
        jugadores_actuales = salas[codigo]
        existe = any(str(j.get("id")) == jugador_id for j in jugadores_actuales)
        if not existe:
            if len(jugadores_actuales) >= MAX_JUGADORES:
                return jsonify({"exito": False, "error": "Sala llena"}), 409
            if estado_partida[codigo].get("iniciada"):
                return jsonify({"exito": False, "error": "La partida ya comenzó"}), 409
            jugadores_actuales.append({"id": jugador_id, "nombre": nombre_jugador})
        estado_partida[codigo].setdefault("listos", {})[jugador_id] = False
    return jsonify({"exito": True, "total": len(jugadores_actuales), "jugadores": jugadores_actuales})


@app.route('/estado_sala', methods=['GET'])
def estado_sala():
    codigo = request.args.get("codigo", "").upper()
    with lock_estado:
        if codigo in salas and codigo in estado_partida:
            info = estado_partida[codigo]
            return jsonify({"exito": True, "total": len(salas[codigo]), "estado": info.get("estado", "LOBBY"), "listos": info.get("listos", {}), "sala": {"jugadores": salas[codigo]}})
    return jsonify({"exito": False, "error": "Sala no encontrada"}), 404


@app.route('/solicitar_inicio', methods=['POST'])
def solicitar_inicio():
    data = request.json or {}
    codigo = str(data.get("codigo", "")).upper()
    with lock_estado:
        if codigo in estado_partida:
            estado_partida[codigo]["estado"] = "ESPERANDO_CONFIRMACION"
            return jsonify({"exito": True})
    return jsonify({"exito": False, "error": "Sala no encontrada"}), 404


@app.route('/enviar_respuesta', methods=['POST'])
def enviar_respuesta():
    data = request.json or {}
    codigo = str(data.get("codigo", "")).upper()
    jugador_id = str(data.get("id_jugador", ""))
    accion = data.get("accion")
    with lock_estado:
        if codigo in estado_partida and _jugador_pertenece(codigo, jugador_id):
            estado_partida[codigo].setdefault("listos", {})[jugador_id] = accion == "LISTO"
            return jsonify({"exito": True})
    return jsonify({"exito": False, "error": "Error al actualizar respuesta"}), 400


@app.route('/iniciar_partida', methods=['POST'])
def iniciar_partida():
    data = request.json or {}
    codigo = str(data.get("codigo", "")).upper()
    with lock_estado:
        if codigo in estado_partida:
            listos = estado_partida[codigo].get("listos", {})
            if listos and len(listos) == len(salas.get(codigo, [])) and all(listos.values()):
                estado_partida[codigo]["iniciada"] = True
                estado_partida[codigo]["estado"] = "INICIADA"
                return jsonify({"exito": True})
            return jsonify({"exito": False, "error": "No todos los jugadores están listos"})
    return jsonify({"exito": False, "error": "Sala no encontrada"}), 404


@app.route('/verificar_partida/<codigo>', methods=['GET'])
def verificar_partida(codigo):
    codigo = codigo.upper()
    with lock_estado:
        return jsonify(estado_partida.get(codigo, {"iniciada": False, "estado": "LOBBY"}))


@app.route('/actualizar_posicion', methods=['POST'])
def actualizar_posicion():
    data = request.json or {}
    codigo = str(data.get("codigo", "")).upper()
    jugador_id = str(data.get("id_jugador", ""))
    with lock_estado:
        if not _jugador_pertenece(codigo, jugador_id):
            return jsonify({"exito": False, "error": "Jugador no pertenece a la sala"}), 403
        inventario = _normalizar_inventario(data)
        posiciones_jugadores.setdefault(codigo, {})[jugador_id] = {
            "x": data.get("x", 2000), "y": data.get("y", 2000),
            "mirando_izquierda": bool(data.get("mirando_izquierda", False)),
            "nombre": data.get("nombre", jugador_id),
            "outfit": data.get("outfit", {}),
            "arma": data.get("arma", "pistola"),
            **inventario,
        }
        # La primera actualización que trae cajas inicializa el estado autoritativo.
        cajas_cliente = data.get("cajas", [])
        if not salas_cajas.get(codigo) and isinstance(cajas_cliente, list):
            salas_cajas[codigo] = []
            for c in cajas_cliente:
                if not isinstance(c, dict) or not c.get("id"):
                    continue
                salas_cajas[codigo].append({
                    "id": str(c["id"]), "x": int(c.get("x", 0)), "y": int(c.get("y", 0)),
                    "w": int(c.get("w", 50)), "h": int(c.get("h", 50)),
                    "abierta": bool(c.get("abierta", False)),
                    "contenido": c.get("contenido", []) if isinstance(c.get("contenido", []), list) else [],
                })
        nuevas_balas = data.get("balas", [])
        if isinstance(nuevas_balas, list):
            salas_balas.setdefault(codigo, []).extend(nuevas_balas)
            salas_balas[codigo] = salas_balas[codigo][-60:]
        return jsonify({
            "exito": True,
            "jugadores": posiciones_jugadores[codigo],
            "inventarios": {jid: p.get("armas", ["pistola", None]) for jid, p in posiciones_jugadores[codigo].items()},
            "cajas": _serializar_cajas(codigo),
            "balas": salas_balas.get(codigo, []),
        })


@app.route('/operar_caja', methods=['POST'])
def operar_caja():
    data = request.json or {}
    codigo = str(data.get("codigo", "")).upper()
    jugador_id = str(data.get("id_jugador", ""))
    caja_id = str(data.get("caja_id", ""))
    accion = str(data.get("accion", ""))
    item_index = int(data.get("item_index", -1))
    slot = data.get("slot")
    with lock_estado:
        if not _jugador_pertenece(codigo, jugador_id):
            return jsonify({"exito": False, "error": "Jugador no pertenece a la sala"}), 403
        caja = next((c for c in salas_cajas.get(codigo, []) if str(c.get("id")) == caja_id), None)
        jugador = posiciones_jugadores.setdefault(codigo, {}).setdefault(jugador_id, _normalizar_inventario({}))
        if caja is None or not (0 <= item_index < len(caja.get("contenido", []))):
            return jsonify({"exito": False, "error": "Objeto o caja no disponible"}), 409
        item = caja["contenido"][item_index]
        if accion not in ("TOMAR", "CAMBIAR"):
            return jsonify({"exito": False, "error": "Acción no válida"}), 400

        armas = list(jugador.get("armas", ["pistola", None]))[:2]
        while len(armas) < 2:
            armas.append(None)
        if item.get("tipo") == "arma":
            nombre = item.get("nombre")
            if not isinstance(nombre, str):
                return jsonify({"exito": False, "error": "Arma inválida"}), 400
            hueco = next((i for i, a in enumerate(armas) if a is None), None)
            if accion == "TOMAR" and hueco is None:
                return jsonify({"exito": False, "error": "Inventario de armas lleno", "caja": caja}), 409
            destino = hueco if hueco is not None else int(slot) if slot in (0, 1, "0", "1") else None
            if destino is None or destino not in (0, 1):
                return jsonify({"exito": False, "error": "Selecciona un arma para cambiar"}), 409
            vieja = armas[destino]
            armas[destino] = nombre
            if vieja is None:
                caja["contenido"].pop(item_index)
            else:
                caja["contenido"][item_index] = {"tipo": "arma", "nombre": vieja}
            jugador["armas"] = armas
            jugador["arma_slot"] = destino
        elif item.get("tipo") == "balas":
            mun = dict(jugador.get("municion_tipos", {}))
            tipo = MUNICION_POR_ARMA.get(str(item.get("nombre", "")), str(item.get("nombre", "ligera")))
            if tipo not in mun and len(mun) >= MAX_TIPOS_MUNICION:
                return jsonify({"exito": False, "error": "Límite de 3 tipos de munición"}), 409
            cantidad = max(1, int(item.get("cantidad", 10)))
            mun[tipo] = mun.get(tipo, 0) + cantidad
            jugador["municion_tipos"] = mun
            caja["contenido"].pop(item_index)
        elif item.get("tipo") == "vendas":
            actuales = int(jugador.get("vendas", 0))
            cantidad = min(max(0, int(item.get("cantidad", 1))), MAX_VENDAS - actuales)
            if cantidad <= 0:
                return jsonify({"exito": False, "error": "Límite de vendas alcanzado"}), 409
            jugador["vendas"] = actuales + cantidad
            item["cantidad"] = int(item.get("cantidad", 1)) - cantidad
            if item["cantidad"] <= 0:
                caja["contenido"].pop(item_index)
        elif item.get("tipo") == "granada":
            granadas = dict(jugador.get("granadas", {}))
            total = sum(max(0, int(v)) for v in granadas.values())
            if total >= MAX_GRANADAS:
                return jsonify({"exito": False, "error": "Límite de granadas alcanzado"}), 409
            nombre = str(item.get("nombre", "granada_dano"))
            granadas[nombre] = granadas.get(nombre, 0) + 1
            jugador["granadas"] = granadas
            caja["contenido"].pop(item_index)
        else:
            return jsonify({"exito": False, "error": "Objeto no compatible"}), 400

        if not caja["contenido"]:
            caja["abierta"] = True
        return jsonify({"exito": True, "caja": caja, "inventario": jugador})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
