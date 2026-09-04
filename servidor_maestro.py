import os
from flask import Flask, request, jsonify
import random

app = Flask(__name__)

# ==========================================
# ESTRUCTURAS DE DATOS EN MEMORIA
# ==========================================

# { "CODIGO": [ {"id": "...", "nombre": "..."}, ... ] }
salas = {}

# { "CODIGO": { "id_jugador": {"x": 0, "y": 0, ...} } }
posiciones_jugadores = {}

# { "CODIGO": {"iniciada": False, "estado": "LOBBY", "listos": {}} }
estado_partida = {}

# { "CODIGO": [balas...] }
salas_balas = {}

# NUEVO:
# Estado autoritativo de las cajas de suministros por sala.
#
# Cada caja tiene esta estructura:
# {
#     "x": ...,
#     "y": ...,
#     "w": ...,
#     "h": ...,
#     "contenido": [
#         {"tipo": "arma", "nombre": "carabina"},
#         {"tipo": "balas", "nombre": "francotirador", ...},
#         {"tipo": "vendas", "cantidad": 2}
#     ],
#     "abierta": False
# }
salas_cajas = {}


@app.route('/')
def home():
    return "¡El servidor de Battle Royale multijugador está activo y funcionando correctamente!"


# ==========================================
# RUTAS DE GESTIÓN DE SALAS (LOBBY)
# ==========================================

@app.route('/crear_sala', methods=['POST'])
def crear_sala():
    data = request.json or {}

    nombre_creador = data.get("jugador") or data.get("nombre", "Anónimo")
    id_jugador = str(data.get("id_jugador", nombre_creador))

    codigo = str(data.get("codigo", random.randint(1000, 9999))).upper()

    if codigo not in salas:
        salas[codigo] = []

    if not any(str(j.get("id")) == id_jugador for j in salas[codigo]):
        salas[codigo].append({
            "id": id_jugador,
            "nombre": nombre_creador
        })

    if codigo not in posiciones_jugadores:
        posiciones_jugadores[codigo] = {}

    estado_partida[codigo] = {
        "iniciada": False,
        "estado": "LOBBY",
        "listos": {id_jugador: False}
    }

    # Reiniciamos las balas y las cajas de la nueva sala.
    salas_balas[codigo] = []
    salas_cajas[codigo] = []

    return jsonify({
        "exito": True,
        "codigo": codigo,
        "total": len(salas[codigo]),
        "mensaje": "Sala creada con éxito"
    })


@app.route('/unirse_sala', methods=['POST'])
def unirse_sala():
    data = request.json or {}

    codigo = data.get("codigo", "").upper()
    nombre_jugador = data.get("jugador") or data.get("nombre", "Jugador")
    jugador_id = str(data.get("id_jugador", nombre_jugador))

    if not codigo or codigo not in salas:
        return jsonify({
            "exito": False,
            "error": "La sala no existe"
        })

    jugadores_actuales = salas[codigo]

    existe = any(
        str(j.get("id")) == jugador_id
        for j in jugadores_actuales
    )

    if not existe:
        jugadores_actuales.append({
            "id": jugador_id,
            "nombre": nombre_jugador
        })

    if codigo in estado_partida:
        if "listos" not in estado_partida[codigo]:
            estado_partida[codigo]["listos"] = {}

        estado_partida[codigo]["listos"][jugador_id] = False

    return jsonify({
        "exito": True,
        "total": len(jugadores_actuales),
        "jugadores": jugadores_actuales
    })


@app.route('/estado_sala', methods=['GET'])
def estado_sala():
    codigo = request.args.get("codigo", "").upper()

    if codigo in salas and codigo in estado_partida:
        total_jugadores = len(salas[codigo])
        info_estado = estado_partida[codigo]

        return jsonify({
            "exito": True,
            "total": total_jugadores,
            "estado": info_estado.get("estado", "LOBBY"),
            "listos": info_estado.get("listos", {}),
            "sala": {
                "jugadores": salas[codigo]
            }
        })

    return jsonify({
        "exito": False,
        "error": "Sala no encontrada"
    }), 404


# ==========================================
# RUTAS DE CONTROL DE PARTIDA
# ==========================================

@app.route('/solicitar_inicio', methods=['POST'])
def solicitar_inicio():
    data = request.json or {}
    codigo = data.get("codigo", "").upper()

    if codigo in estado_partida:
        estado_partida[codigo]["estado"] = "ESPERANDO_CONFIRMACION"

        return jsonify({
            "exito": True
        })

    return jsonify({
        "exito": False,
        "error": "Sala no encontrada"
    })


@app.route('/enviar_respuesta', methods=['POST'])
def enviar_respuesta():
    data = request.json or {}

    codigo = data.get("codigo", "").upper()
    jugador_id = str(data.get("id_jugador", ""))
    accion = data.get("accion")

    if codigo in estado_partida and jugador_id:
        if "listos" not in estado_partida[codigo]:
            estado_partida[codigo]["listos"] = {}

        estado_partida[codigo]["listos"][jugador_id] = (
            accion == "LISTO"
        )

        return jsonify({
            "exito": True
        })

    return jsonify({
        "exito": False,
        "error": "Error al actualizar respuesta"
    })


@app.route('/iniciar_partida', methods=['POST'])
def iniciar_partida():
    data = request.json or {}
    codigo = data.get("codigo", "").upper()

    if codigo in estado_partida:
        listos_dict = estado_partida[codigo].get("listos", {})

        if listos_dict and all(listos_dict.values()):
            estado_partida[codigo]["iniciada"] = True
            estado_partida[codigo]["estado"] = "INICIADA"

            return jsonify({
                "exito": True
            })

        return jsonify({
            "exito": False,
            "error": "No todos los jugadores están listos"
        })

    return jsonify({
        "exito": False,
        "error": "Sala no encontrada"
    })


@app.route('/verificar_partida/<codigo>', methods=['GET'])
def verificar_partida(codigo):
    codigo = codigo.upper()

    if codigo in estado_partida:
        return jsonify(estado_partida[codigo])

    return jsonify({
        "iniciada": False,
        "estado": "LOBBY"
    })


# ==========================================
# FUNCIONES AUXILIARES PARA LAS CAJAS
# ==========================================

def obtener_id_host(codigo):
    """
    El creador de la sala es el primer jugador de la lista.
    Ese jugador funciona como HOST y es el único autorizado
    para actualizar el estado de las cajas.
    """
    jugadores = salas.get(codigo, [])

    if not jugadores:
        return None

    return str(jugadores[0].get("id"))


def limpiar_cajas(cajas):
    """
    Valida y normaliza el estado de las cajas recibido desde el host.

    No modifica el contenido de los objetos de loot; solamente
    conserva los campos necesarios para sincronizarlos.
    """
    if not isinstance(cajas, list):
        return []

    cajas_limpias = []

    for caja in cajas:
        if not isinstance(caja, dict):
            continue

        rect = caja.get("rect", {})

        if not isinstance(rect, dict):
            rect = {}

        contenido = caja.get("contenido", [])

        if not isinstance(contenido, list):
            contenido = []

        contenido_limpio = []

        for item in contenido:
            if not isinstance(item, dict):
                continue

            # Copia completa del item para conservar sus datos
            # de munición, cantidad, tipo, nombre, etc.
            contenido_limpio.append(dict(item))

        cajas_limpias.append({
            "x": rect.get("x", caja.get("x", 0)),
            "y": rect.get("y", caja.get("y", 0)),
            "w": rect.get("w", caja.get("w", 0)),
            "h": rect.get("h", caja.get("h", 0)),
            "contenido": contenido_limpio,
            "abierta": bool(caja.get("abierta", False))
        })

    return cajas_limpias


# ==========================================
# RUTAS DE MULTIJUGADOR EN TIEMPO REAL
# ==========================================

@app.route('/actualizar_posicion', methods=['POST'])
def actualizar_posicion():
    data = request.json or {}

    codigo = data.get("codigo", "").upper()
    jugador_id = str(data.get("id_jugador", ""))

    if codigo in salas and jugador_id:

        if codigo not in posiciones_jugadores:
            posiciones_jugadores[codigo] = {}

        # ==========================================
        # POSICIÓN Y ESTADO DEL JUGADOR
        # ==========================================

        posiciones_jugadores[codigo][jugador_id] = {
            "x": data.get("x", 2000),
            "y": data.get("y", 2000),
            "mirando_izquierda": data.get(
                "mirando_izquierda",
                False
            ),
            "nombre": data.get(
                "nombre",
                jugador_id
            ),
            "outfit": data.get(
                "outfit",
                {}
            ),
            "arma": data.get(
                "arma",
                "pistola"
            ),
            "arma_secundaria": data.get(
                "arma_secundaria"
            )
        }

        # ==========================================
        # CAJAS DE SUMINISTROS
        # ==========================================
        #
        # SOLO EL HOST puede enviar el estado de las cajas.
        #
        # Esto evita que un cliente cualquiera sobrescriba el
        # inventario de las cajas de toda la partida.
        #
        # El host manda el estado COMPLETO de sus cajas.
        # Si un jugador toma una carabina y deja su arma anterior,
        # el host ya tendrá ese nuevo contenido y lo enviará aquí.
        #

        host_id = obtener_id_host(codigo)
        cajas_recibidas = data.get("cajas_armas")

        if (
            host_id is not None
            and jugador_id == host_id
            and isinstance(cajas_recibidas, list)
        ):
            salas_cajas[codigo] = limpiar_cajas(
                cajas_recibidas
            )

        # ==========================================
        # BALAS
        # ==========================================

        nuevas_balas = data.get("balas", [])

        if codigo not in salas_balas:
            salas_balas[codigo] = []

        if isinstance(nuevas_balas, list) and nuevas_balas:
            salas_balas[codigo].extend(nuevas_balas)

            # Conservamos solo las últimas 60.
            salas_balas[codigo] = salas_balas[codigo][-60:]

        # ==========================================
        # RESPUESTA A TODOS LOS CLIENTES
        # ==========================================

        return jsonify({
            "exito": True,
            "jugadores": posiciones_jugadores[codigo],
            "balas": salas_balas[codigo],
            "cajas_armas": salas_cajas.get(codigo, [])
        })

    return jsonify({
        "exito": False
    })


# ==========================================
# EJECUCIÓN DEL SERVIDOR
# ==========================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host='0.0.0.0',
        port=port,
        debug=True
    )
