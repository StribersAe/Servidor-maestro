import os
from flask import Flask, request, jsonify
import random

app = Flask(__name__)

salas = {}
posiciones_jugadores = {}
estado_partida = {}
salas_balas = {}
salas_cajas = {}  # codigo -> {caja_id: contenido}
inventarios_sala = {}  # codigo -> {id_jugador: inventario_dict}

@app.route('/')
def home():
    return "¡Servidor Battle Royale activo con inventario y cajas persistentes!"

@app.route('/crear_sala', methods=['POST'])
def crear_sala():
    data = request.json or {}
    nombre_creador = data.get("jugador") or data.get("nombre", "Anónimo")
    id_jugador = str(data.get("id_jugador", nombre_creador))
    codigo = str(data.get("codigo", random.randint(1000, 9999))).upper()
    if codigo not in salas:
        salas[codigo] = []
    if not any(str(j.get("id")) == id_jugador for j in salas[codigo]):
        salas[codigo].append({"id": id_jugador, "nombre": nombre_creador})
    if codigo not in posiciones_jugadores:
        posiciones_jugadores[codigo] = {}
    estado_partida[codigo] = {"iniciada": False, "estado": "LOBBY", "listos": {id_jugador: False}}
    salas_balas[codigo] = []
    salas_cajas[codigo] = {}
    inventarios_sala[codigo] = {}
    return jsonify({"exito": True, "codigo": codigo, "total": len(salas[codigo]), "mensaje": "Sala creada"})

@app.route('/unirse_sala', methods=['POST'])
def unirse_sala():
    data = request.json or {}
    codigo = data.get("codigo", "").upper()
    nombre_jugador = data.get("jugador") or data.get("nombre", "Jugador")
    jugador_id = str(data.get("id_jugador", nombre_jugador))
    if not codigo or codigo not in salas:
        return jsonify({"exito": False, "error": "La sala no existe"})
    jugadores_actuales = salas[codigo]
    existe = any(str(j.get("id")) == jugador_id for j in jugadores_actuales)
    if not existe:
        jugadores_actuales.append({"id": jugador_id, "nombre": nombre_jugador})
    if codigo in estado_partida:
        if "listos" not in estado_partida[codigo]:
            estado_partida[codigo]["listos"] = {}
        estado_partida[codigo]["listos"][jugador_id] = False
    return jsonify({"exito": True, "total": len(jugadores_actuales), "jugadores": jugadores_actuales})

@app.route('/estado_sala', methods=['GET'])
def estado_sala():
    codigo = request.args.get("codigo", "").upper()
    if codigo in salas and codigo in estado_partida:
        total_jugadores = len(salas[codigo])
        info_estado = estado_partida[codigo]
        return jsonify({"exito": True, "total": total_jugadores, "estado": info_estado.get("estado", "LOBBY"), "listos": info_estado.get("listos", {}), "sala": {"jugadores": salas[codigo]}})
    return jsonify({"exito": False, "error": "Sala no encontrada"}), 404

@app.route('/solicitar_inicio', methods=['POST'])
def solicitar_inicio():
    data = request.json or {}
    codigo = data.get("codigo", "").upper()
    if codigo in estado_partida:
        estado_partida[codigo]["estado"] = "ESPERANDO_CONFIRMACION"
        return jsonify({"exito": True})
    return jsonify({"exito": False, "error": "Sala no encontrada"})

@app.route('/enviar_respuesta', methods=['POST'])
def enviar_respuesta():
    data = request.json or {}
    codigo = data.get("codigo", "").upper()
    jugador_id = str(data.get("id_jugador", ""))
    accion = data.get("accion")
    if codigo in estado_partida and jugador_id:
        if "listos" not in estado_partida[codigo]:
            estado_partida[codigo]["listos"] = {}
        estado_partida[codigo]["listos"][jugador_id] = (accion == "LISTO")
        return jsonify({"exito": True})
    return jsonify({"exito": False, "error": "Error"})

@app.route('/iniciar_partida', methods=['POST'])
def iniciar_partida():
    data = request.json or {}
    codigo = data.get("codigo", "").upper()
    if codigo in estado_partida:
        listos_dict = estado_partida[codigo].get("listos", {})
        if listos_dict and all(listos_dict.values()):
            estado_partida[codigo]["iniciada"] = True
            estado_partida[codigo]["estado"] = "INICIADA"
            # reset cajas e inventarios para nueva partida
            salas_cajas[codigo] = {}
            inventarios_sala[codigo] = {}
            salas_balas[codigo] = []
            return jsonify({"exito": True})
        return jsonify({"exito": False, "error": "No todos listos"})
    return jsonify({"exito": False, "error": "Sala no encontrada"})

@app.route('/verificar_partida/<codigo>', methods=['GET'])
def verificar_partida(codigo):
    codigo = codigo.upper()
    if codigo in estado_partida:
        return jsonify(estado_partida[codigo])
    return jsonify({"iniciada": False, "estado": "LOBBY"})

@app.route('/actualizar_caja', methods=['POST'])
def actualizar_caja():
    data = request.json or {}
    codigo = data.get("codigo","").upper()
    caja_id = data.get("caja_id")
    contenido = data.get("contenido", [])
    if codigo not in salas_cajas:
        salas_cajas[codigo]={}
    # Validacion basica: contenido debe ser lista, no permitir duplicar armas infinitas
    # Evitar inconsistencias: si dos jugadores actualizan a la vez, el ultimo en llegar gana pero se conserva estado
    # Para evitar exploit, limitar max 10 items por caja
    if isinstance(contenido, list) and len(contenido)<=10:
        salas_cajas[codigo][str(caja_id)] = contenido
        return jsonify({"exito": True})
    return jsonify({"exito": False, "error": "Contenido invalido"})

@app.route('/actualizar_posicion', methods=['POST'])
def actualizar_posicion():
    data = request.json or {}
    codigo = data.get("codigo", "").upper()
    jugador_id = str(data.get("id_jugador", ""))
    if codigo in salas and jugador_id:
        if codigo not in posiciones_jugadores:
            posiciones_jugadores[codigo] = {}
        # Validaciones inventario
        inventario = data.get("inventario", {})
        armas = inventario.get("armas", [])
        if len(armas) > 2:
            armas = armas[:2]
            inventario["armas"]=armas
        # validar granadas max 4
        granadas = inventario.get("granadas", {})
        total_gr = sum(granadas.values()) if isinstance(granadas, dict) else 0
        if total_gr > 4:
            # truncar
            # simple: reducir frag
            pass
        # validar municion tipos max 3
        municion_tipos = inventario.get("municion_tipos", {})
        if isinstance(municion_tipos, dict) and len(municion_tipos)>3:
            # conservar solo 3 primeros
            keys = list(municion_tipos.keys())[:3]
            inventario["municion_tipos"] = {k: municion_tipos[k] for k in keys}

        posiciones_jugadores[codigo][jugador_id] = {
            "x": data.get("x", 2000),
            "y": data.get("y", 2000),
            "mirando_izquierda": data.get("mirando_izquierda", False),
            "nombre": data.get("nombre", jugador_id),
            "outfit": data.get("outfit", {}),
            "arma": data.get("arma", "pistola"),
            "inventario": inventario
        }
        if codigo not in inventarios_sala:
            inventarios_sala[codigo]={}
        inventarios_sala[codigo][jugador_id]=inventario

        nuevas_balas = data.get("balas", [])
        if codigo not in salas_balas:
            salas_balas[codigo] = []
        if nuevas_balas:
            salas_balas[codigo].extend(nuevas_balas)
            salas_balas[codigo] = salas_balas[codigo][-60:]

        return jsonify({
            "exito": True,
            "jugadores": posiciones_jugadores[codigo],
            "balas": salas_balas[codigo],
            "cajas": salas_cajas.get(codigo, {}),
            "inventarios": inventarios_sala.get(codigo, {})
        })
    return jsonify({"exito": False})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
