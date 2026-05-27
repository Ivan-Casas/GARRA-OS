# =========================================================================
# 
# Instituto Tecnológico de León
# Ingeniería en Sistemas Computacionales | Sistemas Programables
# 
# PROYECTO: GARRA-OS - Agente Robotico Autonomo con Interfaz Cognitiva
#
# INTEGRANTES:
#   - Álcala Ramos Luz Estefania
#   - Bahena Mora Emilio Salvador
#   - Casas Bastidas José Iván
#   - Fischer González Patrick
#
# Archivo: Dispositivos.py
#
# Módulo 4: Comunicaciones 
#
# DOCENTE: Ma. Veronica Tapia Ibarra
#
# DESCRIPCION:
#
# Biblioteca HAL (Hardware Abstraction Layer) que encapsula el control de
# los sensores y actuadores del robot GARRA-OS. Esta libreria oculta la
# complejidad del manejo directo de pines, ADC, PWM e I2C para que el
# programa principal pueda interactuar con el hardware mediante metodos
# de alto nivel (ej. medir_distancia_cm, mover_cuello, mostrar_emocion).
# =========================================================================

# Importamos las clases necesarias del modulo machine de MicroPython.
# Pin sirve para configurar pines digitales, ADC para lecturas analogicas,
# PWM para senales moduladas (servos, buzzer) e I2C para la pantalla OLED.
from machine import Pin, ADC, PWM, I2C

# Importamos ssd1306 que es la libreria oficial para manejar la pantalla
# OLED de 0.96 pulgadas con controlador SSD1306 via I2C.
import ssd1306

# Importamos time para usar delays y medir tiempos (necesario en el HC-SR04).
import time


# =========================================================================
# CLASE: SensorBox
# Encapsula los tres sensores principales del robot GARRA-OS:
#   1. HC-SR04 (ultrasonico)  -> Distancia de obstaculos para frenado.
#   2. MPU6050 (acelerometro) -> Propiocepcion y deteccion de golpes.
#   3. Divisor de voltaje     -> Lectura del nivel de bateria.
# =========================================================================
class SensorBox:
    """
    Clase encargada de la gestion y estabilizacion de lecturas de los
    sensores del robot GARRA-OS. Devuelve valores ya procesados en sus
    unidades naturales (cm, g de aceleracion, % de bateria).
    """

    # Metodo constructor: se ejecuta al crear el objeto SensorBox.
    # Configura los pines y prepara las estructuras internas para los
    # promedios moviles (estabilizacion de lecturas).
    def __init__(self):
        # ------- SENSOR ULTRASONICO HC-SR04 -------
        # El pin TRIG envia un pulso de 10us para iniciar la medicion.
        # Se configura como salida digital en el GPIO 5.
        self.trig = Pin(5, Pin.OUT)

        # El pin ECHO recibe el rebote del ultrasonido.
        # Se configura como entrada digital en el GPIO 18.
        self.echo = Pin(18, Pin.IN)

        # Aseguramos que TRIG arranque en bajo para evitar disparos falsos.
        self.trig.value(0)

        # ------- SENSOR MPU6050 (Acelerometro/Giroscopio) -------
        # Creamos un bus I2C para comunicarnos con el MPU6050.
        # Usamos el I2C numero 1 con SCL=22 y SDA=21 (estandar en ESP32).
        self.i2c_mpu = I2C(1, scl=Pin(22), sda=Pin(21), freq=400000)

        # Direccion I2C tipica del MPU6050 (0x68 cuando AD0 esta en GND).
        self.direccion_mpu = 0x68

        # Despertamos el MPU6050: por defecto arranca en modo "sleep".
        # Escribimos 0x00 en el registro 0x6B (PWR_MGMT_1) para activarlo.
        try:
            self.i2c_mpu.writeto_mem(self.direccion_mpu, 0x6B, bytes([0x00]))
        except OSError:
            # Si el sensor no responde, imprimimos un aviso pero no detenemos
            # el programa. Esto facilita pruebas sin todos los modulos.
            print("Aviso: MPU6050 no detectado en I2C")

        # ------- SENSOR DE BATERIA (Divisor de voltaje en ADC) -------
        # Conectamos un divisor de voltaje al pin 34 (entrada ADC).
        # Esto permite medir hasta ~7.4V de bateria de forma segura para el ESP32.
        self.sensor_bateria = ADC(Pin(34))

        # Configuramos atenuacion 11dB para leer el rango completo (~0 a 3.3V).
        self.sensor_bateria.atten(ADC.ATTN_11DB)

        # ------- LISTA DE HISTORIAL PARA PROMEDIO MOVIL -------
        # Guardamos las ultimas 5 lecturas de distancia para suavizarlas.
        # Esto evita que un valor erratico del HC-SR04 dispare un falso freno.
        self.historial_distancia = []

    # -----------------------------------------------------------------
    # Metodo: medir_distancia_cm
    # Parametros: ninguno.
    # Que hace: dispara un pulso ultrasonico, mide el tiempo de rebote
    #           y lo convierte a centimetros. Luego aplica un promedio
    #           movil de las ultimas 5 lecturas para estabilizar.
    # Devuelve: distancia en centimetros (float) o -1 si hubo timeout.
    # -----------------------------------------------------------------
    def medir_distancia_cm(self):
        # Aseguramos que TRIG este en bajo antes del pulso.
        self.trig.value(0)
        time.sleep_us(2)

        # Generamos el pulso de disparo de 10 microsegundos en TRIG.
        self.trig.value(1)
        time.sleep_us(10)
        self.trig.value(0)

        # Esperamos a que ECHO suba (inicio del retorno del ultrasonido).
        # Usamos un timeout para evitar bloqueos si no hay rebote.
        tiempo_inicio = time.ticks_us()
        while self.echo.value() == 0:
            # Si pasan mas de 30ms sin respuesta, marcamos error.
            if time.ticks_diff(time.ticks_us(), tiempo_inicio) > 30000:
                return -1
        inicio_pulso = time.ticks_us()

        # Esperamos a que ECHO baje (fin del retorno).
        while self.echo.value() == 1:
            if time.ticks_diff(time.ticks_us(), inicio_pulso) > 30000:
                return -1
        fin_pulso = time.ticks_us()

        # Calculamos la duracion del pulso en microsegundos.
        duracion = time.ticks_diff(fin_pulso, inicio_pulso)

        # Formula: distancia (cm) = duracion (us) / 58.
        # Esto se deriva de la velocidad del sonido (343 m/s) y el viaje de ida y vuelta.
        distancia = duracion / 58

        # Agregamos la lectura al historial para el promedio movil.
        self.historial_distancia.append(distancia)

        # Mantenemos el historial con solo las ultimas 5 lecturas.
        if len(self.historial_distancia) > 5:
            self.historial_distancia.pop(0)

        # Calculamos y devolvemos el promedio de las lecturas guardadas.
        promedio = sum(self.historial_distancia) / len(self.historial_distancia)
        return promedio

    # -----------------------------------------------------------------
    # Metodo: leer_aceleracion
    # Parametros: ninguno.
    # Que hace: lee los registros del MPU6050 que contienen los valores
    #           de aceleracion en los tres ejes (X, Y, Z). Convierte el
    #           valor crudo a unidades de "g" (gravedad terrestre).
    # Devuelve: diccionario con las claves 'x', 'y', 'z' en unidades g.
    # -----------------------------------------------------------------
    def leer_aceleracion(self):
        try:
            # Leemos 6 bytes desde el registro 0x3B (ACCEL_XOUT_H).
            # Estos contienen 2 bytes por cada eje: X, Y y Z.
            datos = self.i2c_mpu.readfrom_mem(self.direccion_mpu, 0x3B, 6)

            # Convertimos los 2 bytes de cada eje en un entero con signo.
            # El MPU6050 entrega datos en complemento a 2 de 16 bits.
            ax = (datos[0] << 8) | datos[1]
            ay = (datos[2] << 8) | datos[3]
            az = (datos[4] << 8) | datos[5]

            # Si el valor supera 32767, lo interpretamos como negativo.
            if ax > 32767: ax -= 65536
            if ay > 32767: ay -= 65536
            if az > 32767: az -= 65536

            # Dividimos entre 16384 (sensibilidad por defecto +/-2g) para
            # obtener el valor en unidades de gravedad.
            return {
                "x": ax / 16384,
                "y": ay / 16384,
                "z": az / 16384
            }
        except OSError:
            # Si la comunicacion falla, devolvemos ceros para no romper el main.
            return {"x": 0, "y": 0, "z": 0}

    # -----------------------------------------------------------------
    # Metodo: detectar_golpe
    # Parametros: umbral (float) - valor de aceleracion a partir del cual
    #             se considera que hubo un golpe. Por defecto 1.8g.
    # Que hace: lee la aceleracion total y la compara contra el umbral.
    #           Sirve para detectar impactos o caidas del robot.
    # Devuelve: True si hubo un golpe, False en caso contrario.
    # -----------------------------------------------------------------
    def detectar_golpe(self, umbral=1.8):
        # Obtenemos la lectura de aceleracion actual.
        a = self.leer_aceleracion()

        # Calculamos la magnitud del vector aceleracion (formula de Pitagoras).
        magnitud = (a["x"]**2 + a["y"]**2 + a["z"]**2) ** 0.5

        # Devolvemos True solo si la magnitud supera el umbral configurado.
        return magnitud > umbral

    # -----------------------------------------------------------------
    # Metodo: leer_bateria_porcentaje
    # Parametros: ninguno.
    # Que hace: toma 10 muestras del ADC del divisor de voltaje, las
    #           promedia y las convierte a porcentaje de bateria estimado
    #           para una bateria de 7.4V (rango 6.0V a 8.4V).
    # Devuelve: porcentaje de bateria (float entre 0 y 100).
    # -----------------------------------------------------------------
    def leer_bateria_porcentaje(self):
        # Inicializamos un acumulador para promediar las muestras.
        suma = 0

        # Tomamos 10 lecturas del ADC para reducir el ruido.
        for _ in range(10):
            suma += self.sensor_bateria.read()
            time.sleep_ms(2)

        # Calculamos el promedio de las muestras.
        promedio = suma / 10

        # Convertimos a voltaje: el ADC tiene 12 bits (0-4095) y rango ~3.3V.
        voltaje_adc = (promedio / 4095) * 3.3

        # Como usamos un divisor que reduce la senal a la mitad, multiplicamos por 2
        # para obtener el voltaje real de la bateria.
        voltaje_bateria = voltaje_adc * 2

        # Mapeamos el voltaje al porcentaje: 6.0V = 0%, 8.4V = 100%.
        porcentaje = ((voltaje_bateria - 6.0) / (8.4 - 6.0)) * 100

        # Limitamos el resultado entre 0 y 100 para evitar valores fuera de rango.
        if porcentaje < 0:
            porcentaje = 0
        if porcentaje > 100:
            porcentaje = 100

        # Devolvemos el porcentaje calculado.
        return porcentaje

    # -----------------------------------------------------------------
    # Metodo: obtener_resumen_sensores
    # Parametros: ninguno.
    # Que hace: invoca a todos los metodos de lectura y los agrupa en un
    #           solo diccionario. Esto facilita el uso en el main, que
    #           solo necesita pedir "el estado completo" en una llamada.
    # Devuelve: diccionario con distancia, aceleracion, golpe y bateria.
    # -----------------------------------------------------------------
    def obtener_resumen_sensores(self):
        return {
            "distancia_cm": self.medir_distancia_cm(),
            "aceleracion": self.leer_aceleracion(),
            "golpe": self.detectar_golpe(),
            "bateria": self.leer_bateria_porcentaje()
        }


# =========================================================================
# CLASE: ActuatorBox
# Encapsula los tres actuadores principales del robot GARRA-OS:
#   1. Pantalla OLED 0.96" (I2C) -> Cara del avatar (ojos del leon).
#   2. Servomotor SG90 (PWM)     -> Cuello para girar la mirada.
#   3. Buzzer/Bocina PAM8403     -> Indicador sonoro de eventos.
# =========================================================================
class ActuatorBox:
    """
    Clase encargada del control de los actuadores del robot GARRA-OS.
    Ofrece comandos de alto nivel como mostrar_emocion(), mover_cuello()
    y un metodo de seguridad estado_seguro() que apaga todo.
    """

    # Metodo constructor: configura los tres actuadores principales.
    def __init__(self):
        # ------- PANTALLA OLED (cara del avatar) -------
        # Creamos un bus I2C numero 0 con SCL=22 y SDA=21.
        # Compartimos el bus con el MPU6050 (cada dispositivo tiene
        # su propia direccion, asi que no hay conflicto).
        self.i2c_oled = I2C(0, scl=Pin(22), sda=Pin(21))

        # Inicializamos la pantalla OLED de 128x64 pixeles.
        self.pantalla = ssd1306.SSD1306_I2C(128, 64, self.i2c_oled)

        # ------- SERVOMOTOR SG90 (cuello del robot) -------
        # Configuramos PWM en el pin 13 con frecuencia de 50Hz (estandar de servos).
        self.servo_cuello = PWM(Pin(13), freq=50)

        # Centramos el servo al inicio (posicion neutra, 90 grados).
        # El valor 77 corresponde a un pulso de ~1.5ms (centro del SG90).
        self.servo_cuello.duty(77)

        # ------- BUZZER / BOCINA (PAM8403 + buzzer pasivo) -------
        # Lo controlamos con PWM en el pin 26.
        # Iniciamos en silencio (duty = 0).
        self.bocina = PWM(Pin(26), freq=1000)
        self.bocina.duty(0)

    # -----------------------------------------------------------------
    # Metodo: mostrar_emocion
    # Parametros: emocion (str) - puede ser "feliz", "alerta" o "neutro".
    # Que hace: dibuja en la pantalla OLED una representacion simple de
    #           los ojos del leon segun la emocion solicitada. Esto es
    #           la "cara" del robot que mira el usuario.
    # Devuelve: nada (None).
    # -----------------------------------------------------------------
    def mostrar_emocion(self, emocion):
        # Limpiamos la pantalla rellenandola con pixeles apagados (0).
        self.pantalla.fill(0)

        # Si la emocion es "feliz", dibujamos dos ojos abiertos y una sonrisa.
        if emocion == "feliz":
            # Ojo izquierdo: un rectangulo relleno.
            self.pantalla.fill_rect(20, 20, 25, 20, 1)
            # Ojo derecho: otro rectangulo simetrico.
            self.pantalla.fill_rect(83, 20, 25, 20, 1)
            # Texto de apoyo en la parte inferior para reforzar la emocion.
            self.pantalla.text(":)", 56, 50)

        # Si la emocion es "alerta", dibujamos ojos mas grandes (sorpresa).
        elif emocion == "alerta":
            self.pantalla.fill_rect(20, 15, 25, 25, 1)
            self.pantalla.fill_rect(83, 15, 25, 25, 1)
            self.pantalla.text("!ALERTA!", 30, 50)

        # Caso por defecto: ojos neutros (rectangulos pequenos).
        else:
            self.pantalla.fill_rect(25, 25, 15, 15, 1)
            self.pantalla.fill_rect(88, 25, 15, 15, 1)
            self.pantalla.text("...", 56, 50)

        # Enviamos el buffer al hardware para que la imagen se vea.
        self.pantalla.show()

    # -----------------------------------------------------------------
    # Metodo: mostrar_telemetria
    # Parametros: ip (str), bateria (float).
    # Que hace: muestra en la OLED informacion tecnica util para el
    #           desarrollador (direccion IP y nivel de bateria).
    # Devuelve: nada.
    # -----------------------------------------------------------------
    def mostrar_telemetria(self, ip, bateria):
        # Limpiamos la pantalla.
        self.pantalla.fill(0)

        # Escribimos un encabezado en la primera linea.
        self.pantalla.text("GARRA-OS", 30, 0)

        # Linea con la direccion IP del robot.
        self.pantalla.text("IP:" + str(ip), 0, 20)

        # Linea con el porcentaje de bateria, formateado con 1 decimal.
        self.pantalla.text("Bat:{:.1f}%".format(bateria), 0, 40)

        # Mostramos el contenido en pantalla.
        self.pantalla.show()

    # -----------------------------------------------------------------
    # Metodo: mover_cuello
    # Parametros: angulo (int) entre 0 y 180 grados.
    # Que hace: convierte el angulo deseado en el valor de duty
    #           correspondiente para el servomotor SG90 y lo aplica.
    #           Esto permite que el robot "mire" hacia el usuario.
    # Devuelve: nada.
    # -----------------------------------------------------------------
    def mover_cuello(self, angulo):
        # Limitamos el angulo al rango fisico del servo (0-180 grados).
        if angulo < 0:
            angulo = 0
        if angulo > 180:
            angulo = 180

        # Mapeamos el angulo al duty: 0 grados ~= 25, 180 grados ~= 125.
        # Esto corresponde a pulsos de ~0.5ms y ~2.5ms respectivamente.
        duty = int(25 + (angulo / 180) * 100)

        # Aplicamos el valor calculado al PWM del servo.
        self.servo_cuello.duty(duty)

    # -----------------------------------------------------------------
    # Metodo: emitir_sonido
    # Parametros: frecuencia (int) en Hz, duracion (float) en segundos.
    # Que hace: hace sonar el buzzer/bocina con la frecuencia y duracion
    #           indicadas. Sirve como tono de bienvenida o alerta.
    # Devuelve: nada.
    # -----------------------------------------------------------------
    def emitir_sonido(self, frecuencia, duracion):
        # Cambiamos la frecuencia del PWM al tono deseado.
        self.bocina.freq(frecuencia)

        # Subimos el duty a la mitad (512 de 1023) para generar el sonido.
        self.bocina.duty(512)

        # Esperamos el tiempo solicitado mientras el sonido se reproduce.
        time.sleep(duracion)

        # Apagamos el sonido bajando el duty a 0.
        self.bocina.duty(0)

    # -----------------------------------------------------------------
    # Metodo: estado_seguro
    # Parametros: ninguno.
    # Que hace: apaga TODOS los actuadores de manera segura. Se llama
    #           cuando se detecta un golpe, paro de emergencia o cuando
    #           el programa principal termina (KeyboardInterrupt).
    # Devuelve: nada.
    # -----------------------------------------------------------------
    def estado_seguro(self):
        # Detenemos el buzzer poniendo el duty en 0.
        self.bocina.duty(0)

        # Centramos el servo del cuello (posicion neutra).
        self.servo_cuello.duty(77)

        # Limpiamos la pantalla y mostramos un mensaje claro de seguridad.
        self.pantalla.fill(0)
        self.pantalla.text("ESTADO SEGURO", 15, 20)
        self.pantalla.text("Sistema OFF", 20, 40)
        self.pantalla.show()
