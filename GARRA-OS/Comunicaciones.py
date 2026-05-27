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
# Archivo: Comunicaciones.py
#
# Modulo 4: Comunicaciones
#
# DOCENTE: Ma. Veronica Tapia Ibarra
#
# OBJETIVO:
# Encapsular toda la logica de comunicacion MQTT del robot GARRA-OS.
# Este modulo se encarga de conectar la ESP32 al Wi-Fi, conectarse al
# broker Mosquitto publico, publicar la telemetria de TODOS los sensores
# y suscribirse a los comandos para TODOS los actuadores.
#
# IMPORTANTE: este archivo NO toca pines directamente. Toda accion sobre
# el hardware se delega a la HAL (clases SensorBox y ActuatorBox del
# archivo dispositivos.py). Asi cumplimos con el encapsulamiento de
# capas exigido en la rubrica.
# =========================================================================

# Importamos network para manejar la conexion Wi-Fi de la ESP32.
import network

# Importamos time para hacer pausas y medir intervalos no bloqueantes.
import time

# Importamos json para serializar la telemetria como cadenas legibles
# por cualquier cliente MQTT (el servidor de Python las parseara igual).
import json

# Importamos la libreria umqtt.simple, que viene incluida en MicroPython
# para ESP32 y permite publicar/suscribirse de manera muy ligera.
from umqtt.simple import MQTTClient


# =========================================================================
# CLASE: ComunicadorMQTT
# Se encarga de:
#   1. Conectar la ESP32 al Wi-Fi.
#   2. Conectarse al broker test.mosquitto.org.
#   3. Publicar telemetria de sensores en topicos jerarquicos.
#   4. Recibir comandos por suscripcion y delegarlos a la HAL.
# =========================================================================
class ComunicadorMQTT:

    # Constructor: recibe las referencias a los objetos HAL (sensores y
    # actuadores) para no tocar el hardware directamente desde aqui.
    # Tambien recibe los datos de la red Wi-Fi y del broker.
    def __init__(self, sensores, actuadores,
                 ssid, password,
                 broker="test.mosquitto.org",
                 puerto=1883,
                 id_dispositivo="01"):

        # Guardamos las referencias a la HAL. Todas las acciones sobre
        # sensores o actuadores se haran SIEMPRE a traves de estos objetos.
        self.sensores = sensores
        self.actuadores = actuadores

        # Guardamos las credenciales de Wi-Fi para reutilizarlas si toca reconectar.
        self.ssid = ssid
        self.password = password

        # Guardamos la direccion del broker y el puerto (1883 es el estandar MQTT).
        self.broker = broker
        self.puerto = puerto

        # Guardamos el ID unico de este nodo. Sirve para escalar el sistema
        # si en el futuro hay varios robots GARRA-OS publicando a la vez.
        self.id_dispositivo = id_dispositivo

        # -----------------------------------------------------------------
        # DEFINICION DE TOPICOS (jerarquia de 4 niveles segun la rubrica):
        # proyecto / tipo_nodo / nombre_modulo / id_dispositivo
        # -----------------------------------------------------------------

        # Topicos de SENSORES (la ESP32 PUBLICA en estos topicos).
        self.topico_distancia  = "garra/sensor/distancia/"   + id_dispositivo
        self.topico_aceleracion = "garra/sensor/aceleracion/" + id_dispositivo
        self.topico_golpe      = "garra/sensor/golpe/"       + id_dispositivo
        self.topico_bateria    = "garra/sensor/bateria/"     + id_dispositivo

        # Topicos de ACTUADORES (la ESP32 REPORTA el estado actual aqui).
        self.topico_estado_oled  = "garra/actuador/oled/"  + id_dispositivo
        self.topico_estado_servo = "garra/actuador/servo/" + id_dispositivo
        self.topico_estado_buzzer = "garra/actuador/buzzer/" + id_dispositivo

        # Topicos de COMANDOS (la ESP32 se SUSCRIBE a estos para recibir ordenes).
        self.cmd_oled   = "garra/comando/oled/"   + id_dispositivo
        self.cmd_servo  = "garra/comando/servo/"  + id_dispositivo
        self.cmd_buzzer = "garra/comando/buzzer/" + id_dispositivo
        self.cmd_paro   = "garra/comando/paro/"   + id_dispositivo

        # Cliente MQTT. Se inicializa como None y se crea al conectar.
        self.cliente = None

    # -----------------------------------------------------------------
    # Metodo: conectar_wifi
    # Que hace: enciende la interfaz Wi-Fi de la ESP32 y se conecta al
    #           access point con las credenciales dadas en el constructor.
    # -----------------------------------------------------------------
    def conectar_wifi(self):
        # Creamos un objeto de tipo "estacion" (cliente Wi-Fi).
        wlan = network.WLAN(network.STA_IF)

        # Activamos el adaptador Wi-Fi.
        wlan.active(True)

        # Si ya estaba conectado, no hacemos nada y mostramos la IP.
        if not wlan.isconnected():
            print("Conectando a Wi-Fi:", self.ssid)
            wlan.connect(self.ssid, self.password)

            # Esperamos hasta 15 segundos a que asocie con el AP.
            intentos = 0
            while not wlan.isconnected() and intentos < 15:
                print(".", end="")
                time.sleep(1)
                intentos += 1

        # Si todo salio bien, imprimimos la IP asignada por DHCP.
        if wlan.isconnected():
            print("\nWi-Fi OK. IP:", wlan.ifconfig()[0])
            return wlan.ifconfig()[0]
        else:
            # Si despues de 15 s no hay conexion, avisamos pero no rompemos
            # el programa: el main puede seguir funcionando en modo offline.
            print("\nERROR: no se pudo conectar a Wi-Fi")
            return None

    # -----------------------------------------------------------------
    # Metodo: callback_comando
    # Que hace: es la funcion que MQTT llama AUTOMATICAMENTE cada vez
    #           que llega un mensaje a un topico al que estamos suscritos.
    #           Recibe el topico (bytes) y el mensaje (bytes) y decide a
    #           que metodo de la HAL llamar.
    # -----------------------------------------------------------------
    def callback_comando(self, topico, mensaje):
        # Convertimos topico y mensaje a string (vienen como bytes).
        topico_str = topico.decode()
        mensaje_str = mensaje.decode()

        # Imprimimos en consola para depurar lo que esta llegando.
        print("[MQTT IN] {} -> {}".format(topico_str, mensaje_str))

        # ----- COMANDO PARA LA OLED (cambia la emocion del avatar) -----
        # Esperamos texto plano: "feliz", "alerta" o "neutro".
        if topico_str == self.cmd_oled:
            self.actuadores.mostrar_emocion(mensaje_str)
            # Reportamos el nuevo estado al servidor para confirmacion.
            self.cliente.publish(self.topico_estado_oled, mensaje_str)

        # ----- COMANDO PARA EL SERVO (mueve el cuello) -----
        # Esperamos un numero entre 0 y 180 (en grados).
        elif topico_str == self.cmd_servo:
            try:
                angulo = int(mensaje_str)
                self.actuadores.mover_cuello(angulo)
                self.cliente.publish(self.topico_estado_servo, str(angulo))
            except ValueError:
                # Si el dato no es un numero valido, lo ignoramos.
                print("Comando servo invalido:", mensaje_str)

        # ----- COMANDO PARA EL BUZZER (emite un tono) -----
        # Esperamos JSON: {"frecuencia": 880, "duracion": 0.2}
        elif topico_str == self.cmd_buzzer:
            try:
                datos = json.loads(mensaje_str)
                self.actuadores.emitir_sonido(
                    datos["frecuencia"], datos["duracion"]
                )
                self.cliente.publish(self.topico_estado_buzzer, "OK")
            except Exception as e:
                print("Comando buzzer invalido:", e)

        # ----- COMANDO DE PARO DE EMERGENCIA -----
        # Cualquier mensaje en este topico (ej. "STOP") activa estado seguro.
        elif topico_str == self.cmd_paro:
            print("!!! PARO DE EMERGENCIA RECIBIDO !!!")
            self.actuadores.estado_seguro()

    # -----------------------------------------------------------------
    # Metodo: conectar_broker
    # Que hace: crea el cliente MQTT, configura el callback y se suscribe
    #           a TODOS los topicos de comandos del proyecto.
    # -----------------------------------------------------------------
    def conectar_broker(self):
        # Creamos el cliente MQTT con un id unico (importante: si dos
        # clientes usan el mismo client_id, el broker los desconecta).
        client_id = "garra_os_" + self.id_dispositivo

        self.cliente = MQTTClient(
            client_id=client_id,
            server=self.broker,
            port=self.puerto,
            keepalive=60
        )

        # Asignamos la funcion callback que procesara los mensajes entrantes.
        self.cliente.set_callback(self.callback_comando)

        # Intentamos conectarnos al broker.
        print("Conectando al broker MQTT:", self.broker)
        self.cliente.connect()
        print("Broker MQTT conectado.")

        # Nos suscribimos a TODOS los topicos de comandos.
        self.cliente.subscribe(self.cmd_oled)
        self.cliente.subscribe(self.cmd_servo)
        self.cliente.subscribe(self.cmd_buzzer)
        self.cliente.subscribe(self.cmd_paro)
        print("Suscripciones activas: oled, servo, buzzer, paro")

    # -----------------------------------------------------------------
    # Metodo: publicar_telemetria
    # Que hace: pide un resumen completo de los sensores a la HAL y
    #           publica cada lectura en su topico correspondiente.
    # Devuelve: el diccionario de datos que publico (util para el main).
    # -----------------------------------------------------------------
    def publicar_telemetria(self):
        # Pedimos a la HAL el estado de todos los sensores de una sola vez.
        datos = self.sensores.obtener_resumen_sensores()

        # Publicamos cada lectura en su topico. Convertimos a string porque
        # MQTT trabaja con bytes/cadenas, no con tipos Python.
        self.cliente.publish(self.topico_distancia,
                             "{:.2f}".format(datos["distancia_cm"]))

        # La aceleracion es un diccionario con x/y/z: lo serializamos en JSON.
        self.cliente.publish(self.topico_aceleracion,
                             json.dumps(datos["aceleracion"]))

        # El golpe es un bool: lo enviamos como "true" o "false" en minusculas.
        self.cliente.publish(self.topico_golpe,
                             "true" if datos["golpe"] else "false")

        # El nivel de bateria como porcentaje con 1 decimal.
        self.cliente.publish(self.topico_bateria,
                             "{:.1f}".format(datos["bateria"]))

        # Devolvemos el diccionario por si el main quiere usarlo tambien.
        return datos

    # -----------------------------------------------------------------
    # Metodo: revisar_mensajes
    # Que hace: revisa si hay mensajes pendientes en el broker SIN bloquear
    #           el ciclo principal. Si llego algo, se llama al callback.
    # -----------------------------------------------------------------
    def revisar_mensajes(self):
        # check_msg() es la version no bloqueante de wait_msg().
        # Si hay mensaje, dispara el callback; si no, sigue de largo.
        self.cliente.check_msg()
