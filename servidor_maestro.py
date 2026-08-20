import os
from flask import Flask, request, jsonify

app = Flask(__name__)

# Estructuras de datos en memoria para el servidor
salas = {} # Almacena los jugadores dentro de cada sala: { "CODIGO": [ {"id": 123, "nombre": "Jugador1"}, ... ] }
posiciones_jugadores = {} # Almacena la posición y estado en tiempo real: { "CODIGO": { "id_jugador": {"x": 0, "y": 0, ...} } }

@app.route('/')
def home():
    return "¡El servidor de Battle Royale multijugador está activo y funcionando correctamente!"

# ==========================================
# RUTAS DE GESTIÓN DE SALAS (LOBBY)
# ==========================================

@app.route('/crear_sala', methods=['POST'])
def crear_sala():
    data = request.json or {}
    codigo = data.get("codigo", "").upper()
    nombre_creador = data.get("nombre", "Anónimo")
    
    if not codigo:
        return jsonify({"exito": False, "error": "Código de sala vacío"})
    
    if codigo in salas:
        return jsonify({"exito": False, "error": "La sala ya existe"})
    
    # Inicializamos la sala con su primer jugador (el host)
    salas[codigo] = [{
        "id": data.get("id_jugador", 1),
        "nombre": nombre_creador
    }]
    posiciones_jugadores[codigo] = {}
    
    return jsonify({"exito": True, "mensaje": "Sala creada con éxito"})

@app.route('/unirse_sala', methods=['POST'])
def unirse_sala():
    data = request.json or {}
    codigo = data.get("codigo", "").upper()
    jugador_id = data.get("id_jugador")
    nombre_jugador = data.get("nombre", "Jugador")
    
    if codigo not in salas:
        return jsonify({"exito": False, "error": "La sala no existe"})
    
    # Verificamos si el jugador ya está en la lista para no duplicarlo
    jugadores_actuales = salas[codigo]
    existe = any(str(j.get("id")) == str(jugador_id) for j in jugadores_actuales)
    
    if not existe:
        jugadores_actuales.append({
            "id": jugador_id,
            "nombre": nombre_jugador
        })
        
    return jsonify({"exito": True, "jugadores": jugadores_actuales})

@app.route('/verificar_sala/<codigo>', methods=['GET'])
def verificar_sala(codigo):
    codigo = codigo.upper()
    if codigo in salas:
        return jsonify({
            "exito": True, 
            "jugadores": salas[codigo]
        })
    return jsonify({"exito": False, "error": "Sala no encontrada"})


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
        
        # Guardamos las coordenadas, dirección, arma y estados del jugador
        posiciones_jugadores[codigo][str(jugador_id)] = {
            "x": data.get("x", 2000),
            "y": data.get("y", 2000),
            "mirando_izquierda": data.get("mirando_izquierda", False),
            "accion": data.get("accion", "NORMAL"),
            "z_salto": data.get("z_salto", 0),
            "arma": data.get("arma", "pistola")
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
    # Configuración para ejecutar en local o en Render automáticamente
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
