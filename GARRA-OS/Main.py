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
# Archivo: Main.py
#
# Modulo 4: Comunicaciones
#
# DOCENTE: Ma. Veronica Tapia Ibarra
#
# OBJETIVO:
# Programa principal del robot GARRA-OS con integracion MQTT.
# Conecta la ESP32 al Wi-Fi y al broker Mosquitto, publica la telemetria
# de todos los sensores y atiende los comandos remotos de todos los
# actuadores. Mantiene la logica local de seguridad (frenado por golpe y
# por obstaculo) tal como se entrego en la unidad anterior.
#
# REGLA DE ENCAPSULAMIENTO:
# Este archivo NO accede a pines directamente. Toda la interaccion con
# hardware pasa por la HAL (dispositivos.py) y por el modulo de
# comunicaciones (Comunicaciones.py).
# =========================================================================

# Importamos las clases de la HAL para sensores y actuadores.
from dispositivos import SensorBox, ActuatorBox

# Importamos el modulo de comunicaciones MQTT que creamos para este sprint.
from Comunicaciones import ComunicadorMQTT

# Importamos time para los delays no bloqueantes entre publicaciones.
import time


# -------------------------------------------------------------------------
# CONFIGURACION DE RED (editar segun la red del laboratorio o del celular)
# -------------------------------------------------------------------------
SSID_WIFI     = "TU_RED_WIFI"        # Nombre de la red Wi-Fi
PASSWORD_WIFI = "TU_PASSWORD"        # Contrasena de la red
BROKER        = "test.mosquitto.org" # Broker MQTT publico que usaremos
ID_NODO       = "01"                 # ID unico del robot (para escalar)


# -------------------------------------------------------------------------
# INICIALIZACION DEL SISTEMA
# -------------------------------------------------------------------------

print("=========================================")
print("  GARRA-OS iniciando (modo MQTT)...")
print("=========================================")

# Instanciamos la HAL de sensores (configura HC-SR04, MPU6050 y bateria).
sensores = SensorBox()

# Instanciamos la HAL de actuadores (configura OLED, servo y buzzer).
actuadores = ActuatorBox()

# Mostramos cara neutra y un beep corto de bienvenida.
actuadores.mostrar_emocion("neutro")
actuadores.emitir_sonido(880, 0.2)

# Instanciamos el modulo MQTT pasandole las referencias de la HAL.
# De esta forma, los callbacks llaman SIEMPRE a metodos de la HAL,
# no a pines (cumple con el encapsulamiento exigido en la rubrica).
comunicador = ComunicadorMQTT(
    sensores=sensores,
    actuadores=actuadores,
    ssid=SSID_WIFI,
    password=PASSWORD_WIFI,
    broker=BROKER,
    id_dispositivo=ID_NODO
)

# Intentamos conectarnos al Wi-Fi. Si falla, terminamos aqui en estado seguro.
ip = comunicador.conectar_wifi()
if ip is None:
    actuadores.estado_seguro()
    raise SystemExit("No hay Wi-Fi, abortando.")

# Mostramos en la OLED la IP y la bateria (interfaz tecnica del proyecto).
actuadores.mostrar_telemetria(ip, sensores.leer_bateria_porcentaje())
time.sleep(2)

# Volvemos a la cara del avatar antes de entrar al loop principal.
actuadores.mostrar_emocion("neutro")

# Conectamos al broker MQTT y nos suscribimos a todos los comandos.
comunicador.conectar_broker()

# Avisamos por consola que estamos listos para publicar y recibir.
print("Sistema listo. Iniciando ciclo MQTT...")


# -------------------------------------------------------------------------
# CICLO PRINCIPAL DEL ROBOT (con MQTT)
# -------------------------------------------------------------------------

# Guardamos el momento de la ultima publicacion de telemetria.
# Asi publicamos cada 2 segundos sin bloquear la atencion de comandos.
ultima_publicacion = time.ticks_ms()

try:
    while True:

        # 1) Revisamos si llego algun comando MQTT (no bloqueante).
        #    Si llego, el callback del comunicador lo procesa solo.
        comunicador.revisar_mensajes()

        # 2) Cada 2 segundos publicamos la telemetria completa.
        if time.ticks_diff(time.ticks_ms(), ultima_publicacion) > 2000:
            datos = comunicador.publicar_telemetria()
            ultima_publicacion = time.ticks_ms()

            # Imprimimos en consola lo que acabamos de publicar.
            print("---------------------------------------")
            print("Distancia: {:.1f} cm".format(datos["distancia_cm"]))
            print("Bateria  : {:.1f} %".format(datos["bateria"]))
            print("Golpe    : {}".format(datos["golpe"]))

            # 3) LOGICA LOCAL DE SEGURIDAD POR GOLPE.
            #    Aunque el servidor puede mandar paro, mantenemos una
            #    proteccion LOCAL para no depender 100% de la red.
            if datos["golpe"]:
                print("!!! GOLPE DETECTADO -> ESTADO SEGURO !!!")
                actuadores.mostrar_emocion("alerta")
                actuadores.emitir_sonido(2000, 0.5)
                actuadores.estado_seguro()
                break

            # 4) LOGICA LOCAL DE OBSTACULO (< 30 cm).
            if 0 < datos["distancia_cm"] < 30:
                print(">>> Obstaculo cercano (local)")
                actuadores.mostrar_emocion("alerta")
                actuadores.emitir_sonido(1500, 0.15)

            # 5) AVISO DE BATERIA BAJA.
            if datos["bateria"] < 20:
                print(">>> Bateria baja")
                actuadores.emitir_sonido(400, 0.4)

        # Pequena pausa de 50ms para no saturar el CPU ni la red.
        time.sleep_ms(50)


# -------------------------------------------------------------------------
# MANEJO DE Ctrl+C (Thonny)
# -------------------------------------------------------------------------
except KeyboardInterrupt:
    print("Programa detenido por el usuario. Apagando GARRA-OS...")
    actuadores.estado_seguro()


# -------------------------------------------------------------------------
# MANEJO DE CUALQUIER OTRO ERROR
# -------------------------------------------------------------------------
except Exception as e:
    print("Error inesperado:", e)
    actuadores.estado_seguro()
