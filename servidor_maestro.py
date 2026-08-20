from flask import Flask, request, jsonify
import random
import string

app = Flask(__name__)

# Memoria temporal para las salas activas
# Formato: { "CODIGO": { "host": "IP_o_ID", "jugadores": ["Jugador 1", "Jugador 2"], "en_partida": False } }
salas = {}

def generar_codigo_sala():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

@app.route('/crear_sala', methods=['POST'])
def crear_sala():
    data = request.json
    nombre_jugador = data.get("jugador", "Anónimo")
    codigo = generar_codigo_sala()
    
    while codigo in salas:
        codigo = generar_codigo_sala()
        
    salas[codigo] = {
        "host": nombre_jugador,
        "jugadores": [nombre_jugador],
        "en_partida": False
    }
    return jsonify({"exito": True, "codigo": codigo})

@app.route('/unirse_sala', methods=['POST'])
def unirse_sala():
    data = request.json
    codigo = data.get("codigo", "").upper()
    nombre_jugador = data.get("jugador", "Anónimo")
    
    if codigo in salas:
        if not salas[codigo]["en_partida"]:
            if nombre_jugador not in salas[codigo]["jugadores"]:
                salas[codigo]["jugadores"].append(nombre_jugador)
            return jsonify({"exito": True, "mensaje": "Unido con éxito", "sala": salas[codigo]})
        else:
            return jsonify({"exito": False, "mensaje": "La partida ya empezó"})
    return jsonify({"exito": False, "mensaje": "Sala no encontrada"})

@app.route('/estado_sala/<codigo>', methods=['GET'])
def estado_sala(codigo):
    codigo = codigo.upper()
    if codigo in salas:
        return jsonify({"exito": True, "sala": salas[codigo]})
    return jsonify({"exito": False, "mensaje": "Sala no existe"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
