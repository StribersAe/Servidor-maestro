import os
import random
import string
import threading
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

# Límites de la beta
MIN_PLAYERS = 2
MAX_PLAYERS = 5
ROOM_CODE_LENGTH = 4
PLAYER_TTL_SECONDS = 20

# Estado en memoria. Es adecuado para una beta de una sola instancia de Render.
salas = {}  # codigo -> {host_id, players: {id: player}, state, created_at, started_at}
posiciones_jugadores = {}  # codigo -> jugador_id -> estado visible
lock = threading.RLock()


def respuesta_error(mensaje, status=400):
    return jsonify({"exito": False, "error": mensaje}), status


def texto_seguro(value, fallback, max_len=20):
    value = str(value or "").strip()
    return value[:max_len] or fallback


def generar_codigo():
    with lock:
        for _ in range(100):
            codigo = "".join(random.choices(string.digits, k=ROOM_CODE_LENGTH))
            if codigo not in salas:
                return codigo
    raise RuntimeError("No fue posible generar un código de sala disponible")


def obtener_sala(codigo):
    return salas.get(str(codigo or "").strip().upper())


def obtener_id(data):
    return texto_seguro(data.get("id_jugador"), "", 64)


def limpiar_jugadores_desconectados(sala):
    ahora = time.time()
    vencidos = [
        jugador_id for jugador_id, jugador in sala["players"].items()
        if ahora - jugador.get("last_seen", ahora) > PLAYER_TTL_SECONDS
    ]
    for jugador_id in vencidos:
        del sala["players"][jugador_id]
        posiciones_jugadores.get(sala["code"], {}).pop(jugador_id, None)

    if sala["state"] == "WAITING_CONFIRMATION":
        sala["ready"] = {
            jugador_id: listo
            for jugador_id, listo in sala["ready"].items()
            if jugador_id in sala["players"]
        }


def resumen_sala(sala):
    limpiar_jugadores_desconectados(sala)
    players = list(sala["players"].values())
    return {
        "exito": True,
        "codigo": sala["code"],
        "total": len(players),
        "maximo": MAX_PLAYERS,
        "minimo_para_iniciar": MIN_PLAYERS,
        "estado": sala["state"],
        "host_id": sala["host_id"],
        "listos": dict(sala["ready"]),
        "sala": {"jugadores": players},
    }


@app.route("/", methods=["GET"])
def home():
    return "¡El servidor de Battle Royale multijugador está activo y funcionando correctamente!"


@app.route("/salud", methods=["GET"])
def salud():
    return jsonify({"exito": True, "servidor": "activo", "maximo_jugadores": MAX_PLAYERS})


@app.route("/crear_sala", methods=["POST"])
def crear_sala():
    data = request.get_json(silent=True) or {}
    jugador_id = obtener_id(data)
    if not jugador_id:
        return respuesta_error("Falta id_jugador")

    nombre = texto_seguro(data.get("jugador") or data.get("nombre"), "Jugador")
    codigo_solicitado = str(data.get("codigo") or "").strip().upper()

    with lock:
        codigo = codigo_solicitado or generar_codigo()
        if codigo in salas:
            return respuesta_error("El código de sala ya está ocupado", 409)

        ahora = time.time()
        salas[codigo] = {
            "code": codigo,
            "host_id": jugador_id,
            "players": {
                jugador_id: {
                    "id": jugador_id,
                    "nombre": nombre,
                    "last_seen": ahora,
                }
            },
            "ready": {jugador_id: False},
            "state": "LOBBY",
            "created_at": ahora,
            "started_at": None,
        }
        posiciones_jugadores[codigo] = {}
        return jsonify(resumen_sala(salas[codigo]))


@app.route("/unirse_sala", methods=["POST"])
def unirse_sala():
    data = request.get_json(silent=True) or {}
    codigo = str(data.get("codigo") or "").strip().upper()
    jugador_id = obtener_id(data)
    if not codigo or not jugador_id:
        return respuesta_error("Se requiere código e id_jugador")

    nombre = texto_seguro(data.get("jugador") or data.get("nombre"), "Jugador")
    with lock:
        sala = obtener_sala(codigo)
        if not sala:
            return respuesta_error("La sala no existe", 404)
        limpiar_jugadores_desconectados(sala)

        if sala["state"] != "LOBBY":
            return respuesta_error("La partida ya comenzó o la sala no acepta jugadores", 409)
        if jugador_id not in sala["players"] and len(sala["players"]) >= MAX_PLAYERS:
            return respuesta_error(f"La sala está llena; máximo {MAX_PLAYERS} jugadores", 409)

        ahora = time.time()
        sala["players"][jugador_id] = {
            "id": jugador_id,
            "nombre": nombre,
            "last_seen": ahora,
        }
        sala["ready"][jugador_id] = False
        return jsonify(resumen_sala(sala))


@app.route("/estado_sala", methods=["GET"])
def estado_sala():
    codigo = str(request.args.get("codigo") or "").strip().upper()
    with lock:
        sala = obtener_sala(codigo)
        if not sala:
            return respuesta_error("Sala no encontrada", 404)
        return jsonify(resumen_sala(sala))


@app.route("/latido", methods=["POST"])
def latido():
    data = request.get_json(silent=True) or {}
    codigo = str(data.get("codigo") or "").strip().upper()
    jugador_id = obtener_id(data)
    with lock:
        sala = obtener_sala(codigo)
        if not sala or jugador_id not in sala["players"]:
            return respuesta_error("Jugador no pertenece a la sala", 403)
        sala["players"][jugador_id]["last_seen"] = time.time()
        return jsonify({"exito": True})


@app.route("/solicitar_inicio", methods=["POST"])
def solicitar_inicio():
    data = request.get_json(silent=True) or {}
    codigo = str(data.get("codigo") or "").strip().upper()
    jugador_id = obtener_id(data)
    with lock:
        sala = obtener_sala(codigo)
        if not sala:
            return respuesta_error("Sala no encontrada", 404)
        if jugador_id != sala["host_id"]:
            return respuesta_error("Solo el anfitrión puede solicitar el inicio", 403)
        limpiar_jugadores_desconectados(sala)
        if len(sala["players"]) < MIN_PLAYERS:
            return respuesta_error(f"Se necesitan al menos {MIN_PLAYERS} jugadores para iniciar", 409)
        sala["state"] = "WAITING_CONFIRMATION"
        sala["ready"] = {player_id: False for player_id in sala["players"]}
        return jsonify(resumen_sala(sala))


@app.route("/enviar_respuesta", methods=["POST"])
def enviar_respuesta():
    data = request.get_json(silent=True) or {}
    codigo = str(data.get("codigo") or "").strip().upper()
    jugador_id = obtener_id(data)
    accion = str(data.get("accion") or "").strip().upper()
    if accion not in {"LISTO", "ESPERAR"}:
        return respuesta_error("La acción debe ser LISTO o ESPERAR")

    with lock:
        sala = obtener_sala(codigo)
        if not sala or jugador_id not in sala["players"]:
            return respuesta_error("Jugador no pertenece a la sala", 403)
        if sala["state"] not in {"WAITING_CONFIRMATION", "LOBBY"}:
            return respuesta_error("La sala no está esperando confirmaciones", 409)

        sala["players"][jugador_id]["last_seen"] = time.time()
        sala["ready"][jugador_id] = accion == "LISTO"
        limpiar_jugadores_desconectados(sala)

        if (
            sala["state"] == "WAITING_CONFIRMATION"
            and len(sala["players"]) >= MIN_PLAYERS
            and sala["ready"]
            and all(sala["ready"].get(player_id, False) for player_id in sala["players"])
        ):
            sala["state"] = "STARTING"
            sala["started_at"] = time.time()

        return jsonify(resumen_sala(sala))


@app.route("/iniciar_partida", methods=["POST"])
def iniciar_partida():
    data = request.get_json(silent=True) or {}
    codigo = str(data.get("codigo") or "").strip().upper()
    jugador_id = obtener_id(data)
    with lock:
        sala = obtener_sala(codigo)
        if not sala:
            return respuesta_error("Sala no encontrada", 404)
        if jugador_id and jugador_id != sala["host_id"]:
            return respuesta_error("Solo el anfitrión puede confirmar el inicio", 403)
        limpiar_jugadores_desconectados(sala)
        if len(sala["players"]) < MIN_PLAYERS:
            return respuesta_error(f"Se necesitan al menos {MIN_PLAYERS} jugadores", 409)
        if not all(sala["ready"].get(player_id, False) for player_id in sala["players"]):
            return respuesta_error("No todos los jugadores están listos", 409)
        sala["state"] = "STARTING"
        sala["started_at"] = time.time()
        return jsonify(resumen_sala(sala))


@app.route("/verificar_partida/<codigo>", methods=["GET"])
def verificar_partida(codigo):
    with lock:
        sala = obtener_sala(codigo)
        if not sala:
            return jsonify({"exito": False, "iniciada": False, "estado": "NO_ENCONTRADA"}), 404
        info = resumen_sala(sala)
        info["iniciada"] = sala["state"] in {"STARTING", "INICIADA"}
        return jsonify(info)


@app.route("/actualizar_posicion", methods=["POST"])
def actualizar_posicion():
    data = request.get_json(silent=True) or {}
    codigo = str(data.get("codigo") or "").strip().upper()
    jugador_id = obtener_id(data)
    with lock:
        sala = obtener_sala(codigo)
        if not sala or jugador_id not in sala["players"]:
            return respuesta_error("Jugador no pertenece a la sala", 403)
        if sala["state"] not in {"STARTING", "INICIADA"}:
            return respuesta_error("La partida todavía no está iniciada", 409)

        x = max(0.0, min(4000.0, float(data.get("x", 2000))))
        y = max(0.0, min(4000.0, float(data.get("y", 2000))))
        sala["players"][jugador_id]["last_seen"] = time.time()
        posiciones_jugadores.setdefault(codigo, {})[jugador_id] = {
            "x": x,
            "y": y,
            "mirando_izquierda": bool(data.get("mirando_izquierda", False)),
            "nombre": sala["players"][jugador_id]["nombre"],
            "last_seen": time.time(),
        }
        return jsonify({"exito": True, "jugadores": posiciones_jugadores[codigo]})


@app.route("/obtener_posiciones/<codigo>", methods=["GET"])
def obtener_posiciones(codigo):
    codigo = str(codigo or "").strip().upper()
    with lock:
        sala = obtener_sala(codigo)
        if not sala:
            return respuesta_error("Sala no encontrada", 404)
        limpiar_jugadores_desconectados(sala)
        ahora = time.time()
        visibles = {
            jugador_id: estado
            for jugador_id, estado in posiciones_jugadores.get(codigo, {}).items()
            if ahora - estado.get("last_seen", ahora) <= PLAYER_TTL_SECONDS
            and jugador_id in sala["players"]
        }
        return jsonify({"exito": True, "jugadores": visibles})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
