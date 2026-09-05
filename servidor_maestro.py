import os
from flask import Flask, request, jsonify
import random

app = Flask(__name__)

# Estructuras de datos en memoria para el servidor
salas = {} # { "CODIGO": [ {"id": "...", "nombre": "..."}, ... ] }
posiciones_jugadores = {} # { "CODIGO": { "id_jugador": {"x": 0, "y": 0, ...} } }
estado_partida = {} # { "CODIGO": {"iniciada": False, "estado": "LOBBY", "listos": {}} }
salas_balas = {} # Guardaremos el historial de balas activas por sala
salas_cajas = {} # { "CODIGO": [ {"rect": [...], "contenido": [...], "abierta": False} ] }
inventarios_jugadores = {} # { "CODIGO": { "id_jugador": {"armas": [], "municion": {}, "vendas": 0, "granadas": {}} } }

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
    
    salas_balas[codigo] = []
    
    # Inicializar cajas si no existen
    if codigo not in salas_cajas:
        salas_cajas[codigo] = []
    if codigo not in inventarios_jugadores:
        inventarios_jugadores[codigo] = {}
    
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
        return jsonify({"exito": False, "error": "La sala no existe"})
    
    jugadores_actuales = salas[codigo]
    existe = any(str(j.get("id")) == jugador_id for j in jugadores_actuales)
    
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
    return jsonify({"exito": False, "error": "Error al actualizar respuesta"})

@app.route('/iniciar_partida', methods=['POST'])
def iniciar_partida():
    data = request.json or {}
    codigo = data.get("codigo", "").upper()
    if codigo in estado_partida:
        listos_dict = estado_partida[codigo].get("listos", {})
        if listos_dict and all(listos_dict.values()):
            estado_partida[codigo]["iniciada"] = True
            estado_partida[codigo]["estado"] = "INICIADA"
            return jsonify({"exito": True})
        return jsonify({"exito": False, "error": "No todos los jugadores están listos"})
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
    jugador_id = str(data.get("id_jugador", ""))
    
    if codigo in salas and jugador_id:
        if codigo not in posiciones_jugadores:
            posiciones_jugadores[codigo] = {}
        
        posiciones_jugadores[codigo][jugador_id] = {
            "x": data.get("x", 2000),
            "y": data.get("y", 2000),
            "mirando_izquierda": data.get("mirando_izquierda", False),
            "nombre": data.get("nombre", jugador_id),
            "outfit": data.get("outfit", {}),
            "arma": data.get("arma", "pistola"),
            "arma_secundaria": data.get("arma_secundaria", None),
            "arma_equipada_idx": data.get("arma_equipada_idx", 0)
        }
        
        # Procesamos balas nuevas
        nuevas_balas = data.get("balas", [])
        if codigo not in salas_balas:
            salas_balas[codigo] = []
        
        if nuevas_balas:
            salas_balas[codigo].extend(nuevas_balas)
            salas_balas[codigo] = salas_balas[codigo][-60:]

        return jsonify({
            "exito": True, 
            "jugadores": posiciones_jugadores[codigo],
            "balas": salas_balas[codigo]
        })
    
    return jsonify({"exito": False})


# ==========================================
# RUTAS DE CAJAS E INVENTARIO
# ==========================================

@app.route('/sincronizar_cajas', methods=['POST'])
def sincronizar_cajas():
    """El host envía el estado inicial de las cajas al servidor."""
    data = request.json or {}
    codigo = data.get("codigo", "").upper()
    cajas = data.get("cajas", [])
    
    if codigo in salas:
        salas_cajas[codigo] = cajas
        return jsonify({"exito": True})
    return jsonify({"exito": False, "error": "Sala no encontrada"})

@app.route('/obtener_cajas', methods=['GET'])
def obtener_cajas():
    codigo = request.args.get("codigo", "").upper()
    if codigo in salas_cajas:
        return jsonify({"exito": True, "cajas": salas_cajas[codigo]})
    return jsonify({"exito": False, "error": "Sala no encontrada"})

@app.route('/actualizar_caja', methods=['POST'])
def actualizar_caja():
    """Actualiza el contenido de una caja específica."""
    data = request.json or {}
    codigo = data.get("codigo", "").upper()
    idx_caja = data.get("idx_caja", -1)
    contenido = data.get("contenido", [])
    abierta = data.get("abierta", False)
    
    if codigo in salas_cajas and 0 <= idx_caja < len(salas_cajas[codigo]):
        salas_cajas[codigo][idx_caja]["contenido"] = contenido
        salas_cajas[codigo][idx_caja]["abierta"] = abierta
        return jsonify({"exito": True})
    return jsonify({"exito": False, "error": "Caja no encontrada"})

@app.route('/actualizar_inventario', methods=['POST'])
def actualizar_inventario():
    """Actualiza el inventario de un jugador."""
    data = request.json or {}
    codigo = data.get("codigo", "").upper()
    jugador_id = str(data.get("id_jugador", ""))
    inventario = data.get("inventario", {})
    
    if codigo in salas:
        if codigo not in inventarios_jugadores:
            inventarios_jugadores[codigo] = {}
        inventarios_jugadores[codigo][jugador_id] = inventario
        return jsonify({"exito": True})
    return jsonify({"exito": False, "error": "Sala no encontrada"})

@app.route('/obtener_inventarios', methods=['GET'])
def obtener_inventarios():
    codigo = request.args.get("codigo", "").upper()
    if codigo in inventarios_jugadores:
        return jsonify({"exito": True, "inventarios": inventarios_jugadores[codigo]})
    return jsonify({"exito": False, "error": "Sala no encontrada"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
