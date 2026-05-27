# =========================================================================
# Instituto Tecnologico de León
# Ingenieria en Sistemas Computacionales | Sistemas Programables
#
# PROYECTO: GARRA-OS - Agente Robotico Autonomo con Interfaz Cognitiva
#
# INTEGRANTES:
#   - Álcala Ramos Luz Estefania
#   - Bahena Mora Emilio Salvador
#   - Casas Bastidas José Iván
#   - Fischer González Patrick
#
# Archivo: Servidor_mqtt.py
#
# Modulo 4: Comunicaciones
#
# DOCENTE: Ma. Veronica Tapia Ibarra
#
# OBJETIVO:
# Servidor MQTT en Python para el proyecto GARRA-OS. Se conecta al broker
# publico test.mosquitto.org, se suscribe a TODOS los topicos de telemetria
# de la ESP32 (distancia, aceleracion, golpe, bateria) y permite al
# usuario enviar comandos a los actuadores (OLED, servo, buzzer y paro de
# emergencia) desde un menu por consola.
#
# Cada mensaje recibido se imprime con timestamp para tener evidencia de
# la comunicacion en tiempo real. Todo el envio de comandos se hace por
# MQTT (jamas tocamos el hardware desde aqui).
# ============================================================================

# Importamos paho-mqtt, el cliente MQTT mas usado en Python.
# Si no esta instalado: pip install paho-mqtt
import paho.mqtt.client as mqtt

# Importamos json para parsear la aceleracion (que llega como JSON).
import json

# Importamos datetime para anadir timestamp a cada mensaje recibido.
from datetime import datetime

# Importamos threading para que el menu y el listener de MQTT corran
# en paralelo (el menu en el hilo principal, MQTT en su propio hilo).
import threading


# -------------------------------------------------------------------------
# CONFIGURACION DEL BROKER (debe coincidir con la ESP32)
# -------------------------------------------------------------------------
BROKER  = "test.mosquitto.org"   # Broker publico, sin login.
PUERTO  = 1883                   # Puerto MQTT estandar (sin TLS).
ID_NODO = "01"                   # Debe coincidir con el ID en la ESP32.


# -------------------------------------------------------------------------
# CONSTRUCCION DE TOPICOS (la misma jerarquia que en la ESP32)
# Formato: proyecto / tipo_nodo / nombre_modulo / id_dispositivo
# -------------------------------------------------------------------------

# Topicos a los que nos SUSCRIBIMOS (vienen DESDE la ESP32).
TOPICO_DISTANCIA   = "garra/sensor/distancia/"   + ID_NODO
TOPICO_ACELERACION = "garra/sensor/aceleracion/" + ID_NODO
TOPICO_GOLPE       = "garra/sensor/golpe/"       + ID_NODO
TOPICO_BATERIA     = "garra/sensor/bateria/"     + ID_NODO

# Topicos de estado de actuadores (la ESP32 confirma aqui).
TOPICO_ESTADO_OLED   = "garra/actuador/oled/"   + ID_NODO
TOPICO_ESTADO_SERVO  = "garra/actuador/servo/"  + ID_NODO
TOPICO_ESTADO_BUZZER = "garra/actuador/buzzer/" + ID_NODO

# Topicos a los que PUBLICAMOS comandos (van HACIA la ESP32).
CMD_OLED   = "garra/comando/oled/"   + ID_NODO
CMD_SERVO  = "garra/comando/servo/"  + ID_NODO
CMD_BUZZER = "garra/comando/buzzer/" + ID_NODO
CMD_PARO   = "garra/comando/paro/"   + ID_NODO


# -------------------------------------------------------------------------
# CALLBACKS DE MQTT
# -------------------------------------------------------------------------

# Esta funcion se ejecuta cuando el cliente CONECTA al broker.
# rc == 0 significa exito; cualquier otro numero indica error.
def on_connect(cliente, userdata, flags, rc):
    if rc == 0:
        print("[OK] Conectado al broker:", BROKER)

        # Una vez conectados, nos suscribimos a TODOS los topicos de la ESP32.
        # Asi escuchamos toda su telemetria y sus confirmaciones.
        cliente.subscribe(TOPICO_DISTANCIA)
        cliente.subscribe(TOPICO_ACELERACION)
        cliente.subscribe(TOPICO_GOLPE)
        cliente.subscribe(TOPICO_BATERIA)
        cliente.subscribe(TOPICO_ESTADO_OLED)
        cliente.subscribe(TOPICO_ESTADO_SERVO)
        cliente.subscribe(TOPICO_ESTADO_BUZZER)
        print("[OK] Suscripciones activas para nodo:", ID_NODO)
    else:
        print("[ERROR] Conexion fallida, codigo:", rc)


# Esta funcion se ejecuta cuando llega cualquier mensaje a un topico
# al que estamos suscritos. Imprime con timestamp para evidencia.
def on_message(cliente, userdata, msg):
    # Decodificamos el payload de bytes a string.
    payload = msg.payload.decode()

    # Generamos un timestamp con formato HH:MM:SS.
    timestamp = datetime.now().strftime("%H:%M:%S")

    # Imprimimos segun de que topico se trate (para que se vea ordenado).
    if msg.topic == TOPICO_DISTANCIA:
        print("[{}] DISTANCIA   : {} cm".format(timestamp, payload))

    elif msg.topic == TOPICO_ACELERACION:
        # La aceleracion viene en JSON, la parseamos para mostrarla bonita.
        try:
            datos = json.loads(payload)
            print("[{}] ACELERACION : x={:.2f}g y={:.2f}g z={:.2f}g".format(
                timestamp, datos["x"], datos["y"], datos["z"]
            ))
        except Exception:
            print("[{}] ACELERACION : {}".format(timestamp, payload))

    elif msg.topic == TOPICO_GOLPE:
        # Si llega "true", agregamos un aviso visual.
        if payload == "true":
            print("[{}] !!! GOLPE DETECTADO !!!".format(timestamp))
        else:
            print("[{}] golpe       : no".format(timestamp))

    elif msg.topic == TOPICO_BATERIA:
        print("[{}] BATERIA     : {} %".format(timestamp, payload))

    elif msg.topic == TOPICO_ESTADO_OLED:
        print("[{}] (estado OLED -> {})".format(timestamp, payload))

    elif msg.topic == TOPICO_ESTADO_SERVO:
        print("[{}] (estado servo -> {} grados)".format(timestamp, payload))

    elif msg.topic == TOPICO_ESTADO_BUZZER:
        print("[{}] (estado buzzer -> {})".format(timestamp, payload))

    else:
        # Cualquier topico desconocido lo mostramos crudo.
        print("[{}] {}: {}".format(timestamp, msg.topic, payload))


# -------------------------------------------------------------------------
# MENU DE USUARIO PARA ENVIAR COMANDOS
# -------------------------------------------------------------------------
def menu(cliente):
    # Mostramos un menu simple en bucle hasta que el usuario salga.
    while True:
        # Imprimimos las opciones disponibles.
        print("\n--- MENU GARRA-OS ---")
        print("1) Cambiar emocion (OLED)")
        print("2) Mover cuello (servo)")
        print("3) Emitir sonido (buzzer)")
        print("4) PARO DE EMERGENCIA")
        print("5) Salir")

        # Leemos la opcion del usuario.
        op = input("Opcion: ").strip()

        # Segun la opcion publicamos al topico correspondiente.
        if op == "1":
            # Pedimos una de las 3 emociones definidas en la HAL.
            emocion = input("Emocion (feliz/alerta/neutro): ").strip()
            cliente.publish(CMD_OLED, emocion)
            print(">> Comando enviado a", CMD_OLED)

        elif op == "2":
            # Pedimos el angulo (0 a 180) y lo enviamos como texto.
            angulo = input("Angulo (0-180): ").strip()
            cliente.publish(CMD_SERVO, angulo)
            print(">> Comando enviado a", CMD_SERVO)

        elif op == "3":
            # Pedimos frecuencia y duracion, y armamos un JSON.
            try:
                frec = int(input("Frecuencia en Hz: "))
                dur  = float(input("Duracion en segundos: "))
                payload = json.dumps({"frecuencia": frec, "duracion": dur})
                cliente.publish(CMD_BUZZER, payload)
                print(">> Comando enviado a", CMD_BUZZER)
            except ValueError:
                print("Valores invalidos.")

        elif op == "4":
            # Paro de emergencia: cualquier texto sirve, mandamos "STOP".
            cliente.publish(CMD_PARO, "STOP")
            print(">> PARO DE EMERGENCIA enviado.")

        elif op == "5":
            print("Cerrando servidor...")
            # Detenemos el loop de MQTT y salimos.
            cliente.loop_stop()
            cliente.disconnect()
            break

        else:
            print("Opcion no valida.")


# -------------------------------------------------------------------------
# PUNTO DE ENTRADA
# -------------------------------------------------------------------------
if __name__ == "__main__":

    print("=========================================")
    print("  Servidor MQTT - GARRA-OS")
    print("=========================================")

    # Creamos el cliente MQTT con un id unico para este servidor.
    cliente = mqtt.Client(client_id="garra_os_servidor")

    # Asignamos los callbacks definidos arriba.
    cliente.on_connect = on_connect
    cliente.on_message = on_message

    # Nos conectamos al broker con un keepalive de 60 segundos.
    cliente.connect(BROKER, PUERTO, keepalive=60)

    # Arrancamos el loop de MQTT en SEGUNDO PLANO (no bloquea el menu).
    cliente.loop_start()

    # Ejecutamos el menu en el hilo principal.
    try:
        menu(cliente)
    except KeyboardInterrupt:
        # Si el usuario aprieta Ctrl+C, salimos limpio.
        print("\nInterrumpido por el usuario.")
        cliente.loop_stop()
        cliente.disconnect()
