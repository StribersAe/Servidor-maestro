import os
from flask import Flask, request, jsonify
import random

app = Flask(__name__)

# Estructuras de datos en memoria para el servidor
salas = {} # { "CODIGO": [ {"id": "...", "nombre": "..."}, ... ] }
posiciones_jugadores = {} # { "CODIGO": { "id_jugador": {"x": 0, "y": 0, ...} } }
estado_partida = {} # { "CODIGO": {"iniciada": False, "estado": "LOBBY"} }
listos_jugadores = {} # { "CODIGO": { "id_jugador": bool } }

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
    id_jugador = data.get("id_jugador", nombre_creador)
    
    codigo = str(data.get("codigo", random.randint(1000, 9999))).upper()
    
    if codigo not in salas:
        salas[codigo] = []
    
    if not any(str(j.get("id")) == str(id_jugador) for j in salas[codigo]):
        salas[codigo].append({
            "id": id_jugador,
            "nombre": nombre_creador
        })
        
    if codigo not in posiciones_jugadores:
        posiciones_jugadores[codigo] = {}
        
    estado_partida[codigo] = {"iniciada": False, "estado": "LOBBY"}
    
    if codigo not in listos_jugadores:
        listos_jugadores[codigo] = {}
    listos_jugadores[codigo][str(id_jugador)] = False
    
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
    jugador_id = data.get("id_jugador", nombre_jugador)
    
    if not codigo or codigo not in salas:
        return jsonify({"exito": False, "error": "La sala no existe"})
    
    jugadores_actuales = salas[codigo]
    existe = any(str(j.get("id")) == str(jugador_id) for j in jugadores_actuales)
    
    if not existe:
        jugadores_actuales.append({
            "id": jugador_id,
            "nombre": nombre_jugador
        })
        
    if codigo not in listos_jugadores:
        listos_jugadores[codigo] = {}
    listos_jugadores[codigo][str(jugador_id)] = False
        
    return jsonify({
        "exito": True, 
        "total": len(jugadores_actuales),
        "jugadores": jugadores_actuales
    })

@app.route('/estado_sala', methods=['GET'])
def estado_sala():
    codigo = request.args.get("codigo", "").upper()
    if codigo in salas:
        total_jugadores = len(salas[codigo])
        estado_actual = estado_partida.get(codigo, {}).get("estado", "LOBBY")
        listos_map = listos_jugadores.get(codigo, {})
        return jsonify({
            "exito": True,
            "total": total_jugadores,
            "estado": estado_actual,
            "listos": listos_map,
            "sala": {"jugadores": salas[codigo]}
        })
    return jsonify({"exito": False, "error": "Sala no encontrada"}), 404


# ==========================================
# RUTAS DE CONTROL DE PARTIDA (INICIO / MAPA)
# ==========================================

@app.route('/solicitar_inicio', methods=['POST'])
def solicitar_inicio():
    data = request.json or {}
    codigo = data.get("codigo", "").upper()
    if codigo in salas:
        estado_partida[codigo]["estado"] = "ESPERANDO_CONFIRMACION"
        return jsonify({"exito": True})
    return jsonify({"exito": False, "error": "Sala no encontrada"})

@app.route('/enviar_respuesta', methods=['POST'])
def enviar_respuesta():
    data = request.json or {}
    codigo = data.get("codigo", "").upper()
    id_jugador = data.get("id_jugador")
    accion = data.get("accion") # "LISTO" o "ESPERAR"
    
    if codigo in salas and id_jugador is not None:
        if codigo not in listos_jugadores:
            listos_jugadores[codigo] = {}
        listos_jugadores[codigo][str(id_jugador)] = (accion == "LISTO")
        return jsonify({"exito": True})
    return jsonify({"exito": False, "error": "Datos inválidos"})

@app.route('/iniciar_partida', methods=['POST'])
def iniciar_partida():
    data = request.json or {}
    codigo = data.get("codigo", "").upper()
    if codigo in salas:
        listos = listos_jugadores.get(codigo, {})
        # Opcional: verificar que todos estén listos, o forzar si el host lo decide
        estado_partida[codigo] = {"iniciada": True, "estado": "INICIADA"}
        return jsonify({"exito": True})
    return jsonify({"exito": False, "error": "Sala no encontrada"})

@app.route('/verificar_partida/<codigo>', methods=['GET'])
def verificar_partida(codigo):
    codigo = codigo.upper()
    if codigo in estado_partida:
        return jsonify(estado_partida[codigo])
    return jsonify({"iniciada": False, "estado": "LOBBY"})


# ==========================================
# RUTAS DE MULTIJUGADOR EN TIEMPO REAL (MAPA)
# ==========================================

@app.route('/actualizar_posicion', methods=['POST'])
def actualizar_posicion():
    data = request.json or {}
    codigo = data.get("codigo", "").upper()
    jugador_id = data.get("id_jugador")
    
    if codigo in salas and jugador_id is not None:
        if codigo not in posiciones_jugadores:
            posiciones_jugadores[codigo] = {}
        
        posiciones_jugadores[codigo][str(jugador_id)] = {
            "x": data.get("x", 2000),
            "y": data.get("y", 2000),
            "mirando_izquierda": data.get("mirando_izquierda", False),
            "nombre": data.get("nombre", str(jugador_id))
        }
        return jsonify({
            "exito": True, 
            "jugadores": posiciones_jugadores[codigo]
        })
    
    return jsonify({"exito": False})

@app.route('/obtener_posiciones/<codigo>', methods=['GET'])
def obtener_posiciones(codigo):
    codigo = codigo.upper()
    if codigo in posiciones_jugadores:
        return jsonify({
            "exito": True, 
            "jugadores": posiciones_jugadores[codigo]
        })
    return jsonify({"exito": True, "jugadores": {}})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
