from flask import Flask, request, jsonify
import random
import string

app = Flask(__name__)

salas = {}

def generar_codigo_sala():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

@app.route('/crear_sala', methods=['POST'])
def crear_sala():
    data = request.json or {}
    nombre_jugador = data.get("jugador", "Jugador 1")
    codigo = generar_codigo_sala()
    
    while codigo in salas:
        codigo = generar_codigo_sala()
        
    salas[codigo] = {
        "host": nombre_jugador,
        "jugadores": [nombre_jugador],
        "en_partida": False
    }
    return jsonify({"exito": True, "codigo": codigo, "total": 1})

@app.route('/unirse_sala', methods=['POST'])
def unirse_sala():
    data = request.json or {}
    codigo = data.get("codigo", "").upper()
    nombre_jugador = data.get("jugador", f"Jugador_{random.randint(2,5)}")
    
    if codigo in salas:
        if not salas[codigo]["en_partida"]:
            if nombre_jugador not in salas[codigo]["jugadores"]:
                salas[codigo]["jugadores"].append(nombre_jugador)
            return jsonify({
                "exito": True, 
                "mensaje": "Unido con éxito", 
                "total": len(salas[codigo]["jugadores"]),
                "sala": salas[codigo]
            })
        else:
            return jsonify({"exito": False, "mensaje": "La partida ya empezó"})
    return jsonify({"exito": False, "mensaje": "Sala no encontrada"})

# Soportamos tanto /estado_sala?codigo=XYZ como /estado_sala/XYZ
@app.route('/estado_sala', methods=['GET'])
@app.route('/estado_sala/<codigo_url>', methods=['GET'])
def estado_sala(codigo_url=None):
    codigo = codigo_url or request.args.get("codigo", "").upper()
    if codigo in salas:
        total_jugadores = len(salas[codigo]["jugadores"])
        return jsonify({
            "exito": True, 
            "total": total_jugadores,
            "sala": salas[codigo]
        })
    return jsonify({"exito": False, "mensaje": "Sala no existe"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
