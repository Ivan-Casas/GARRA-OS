# GARRA-OS — Agente Robótico Autónomo con Interfaz Cognitiva

**Instituto Tecnológico de León**
Ingeniería en Sistemas Computacionales — Sistemas Programables

Unidad 4: Comunicaciones

Docente: Ma. Verónica Tapia Ibarra

## Integrantes

- Alcalá Ramos Luz Estefanía
- Bahena Mora Emilio Salvador
- Casas Bastidas José Iván
- Fischer González Patrick

## Objetivo

Conectar el robot GARRA-OS (basado en ESP32 con MicroPython) a un servidor en Python mediante el protocolo MQTT, publicando la telemetría de todos los sensores y atendiendo comandos remotos para todos los actuadores, respetando el encapsulamiento de la HAL (Hardware Abstraction Layer).

## Estructura del repositorio

```
GARRA-OS/
├── dispositivos.py        # HAL: clases SensorBox y ActuatorBox (se carga en la ESP32)
├── Comunicaciones.py      # Módulo MQTT de la ESP32 (Wi-Fi + cliente MQTT + callbacks)
├── Main.py                # Programa principal de la ESP32 (loop con MQTT)
├── servidor_mqtt.py       # Servidor en Python (corre en la PC)
├── README.md              # Este archivo
└── docs/
    └── Reporte_Unidad4.docx   # Reporte con análisis individual por integrante
```

## Hardware utilizado

| Componente | Pin ESP32 | Función |
|---|---|---|
| HC-SR04 TRIG | GPIO 5 | Disparo ultrasónico |
| HC-SR04 ECHO | GPIO 18 | Lectura del rebote |
| MPU6050 SDA | GPIO 21 (I2C-1) | Datos del acelerómetro |
| MPU6050 SCL | GPIO 22 (I2C-1) | Reloj I2C |
| Divisor batería | GPIO 34 (ADC) | Nivel de batería |
| OLED 0.96" SDA | GPIO 21 (I2C-0) | Cara del avatar |
| OLED 0.96" SCL | GPIO 22 (I2C-0) | Reloj I2C |
| Servo SG90 | GPIO 13 (PWM) | Cuello del robot |
| Buzzer/PAM8403 | GPIO 26 (PWM) | Sonidos |

## Matriz de Tópicos MQTT

Formato jerárquico de 4 niveles según la rúbrica:
`proyecto / tipo_nodo / nombre_modulo / id_dispositivo`

### Sensores (la ESP32 publica → el servidor escucha)

| Tópico | Tipo de dato | Ejemplo | Descripción |
|---|---|---|---|
| `garra/sensor/distancia/01` | float (cm) | `45.30` | Distancia medida con HC-SR04 |
| `garra/sensor/aceleracion/01` | JSON | `{"x":0.01,"y":0.02,"z":0.98}` | Aceleración X/Y/Z en g |
| `garra/sensor/golpe/01` | bool | `true` / `false` | Impacto detectado por MPU6050 |
| `garra/sensor/bateria/01` | float (%) | `78.5` | Nivel estimado de batería |

### Actuadores — estado (la ESP32 confirma → el servidor escucha)

| Tópico | Tipo de dato | Ejemplo |
|---|---|---|
| `garra/actuador/oled/01` | string | `feliz` |
| `garra/actuador/servo/01` | int (grados) | `90` |
| `garra/actuador/buzzer/01` | string | `OK` |

### Comandos (el servidor publica → la ESP32 ejecuta)

| Tópico | Payload esperado | Acción HAL invocada |
|---|---|---|
| `garra/comando/oled/01` | `feliz` / `alerta` / `neutro` | `actuadores.mostrar_emocion()` |
| `garra/comando/servo/01` | número 0–180 | `actuadores.mover_cuello()` |
| `garra/comando/buzzer/01` | JSON `{"frecuencia":880,"duracion":0.2}` | `actuadores.emitir_sonido()` |
| `garra/comando/paro/01` | cualquier texto (`STOP`) | `actuadores.estado_seguro()` |

## Requisitos previos

### En la ESP32 (MicroPython 1.20+)

Subir desde Thonny estos archivos a la raíz del ESP32:

- `dispositivos.py`
- `Comunicaciones.py`
- `Main.py`
- `ssd1306.py` (librería OLED, se consigue desde el repositorio oficial de MicroPython)

La librería `umqtt.simple` ya viene incluida en el firmware de MicroPython para ESP32.

### En la PC (servidor)

```bash
pip install paho-mqtt
```

## Paso a paso para correr el proyecto

### 1. Configurar la red Wi-Fi en la ESP32

Abrir `Main.py` y editar las constantes:

```python
SSID_WIFI     = "TU_RED_WIFI"
PASSWORD_WIFI = "TU_PASSWORD"
```

> Recomendación: usar el hotspot del celular para evitar bloqueos de firewall del laboratorio.

### 2. Subir el código a la ESP32

Desde Thonny → `View → Files` → arrastrar los 4 archivos `.py` a "MicroPython device".

### 3. Ejecutar el servidor en la PC

```bash
python servidor_mqtt.py
```

Se conecta a `test.mosquitto.org`, se suscribe a la telemetría y muestra el menú para enviar comandos.

### 4. Ejecutar el Main.py en la ESP32

Desde Thonny presionar `Run` (F5). La ESP32:

1. Se conecta al Wi-Fi y muestra su IP en la OLED.
2. Se conecta al broker MQTT.
3. Empieza a publicar telemetría cada 2 segundos.
4. Espera comandos desde la PC.

### 5. Probar la comunicación bidireccional

Desde el menú del servidor:

- Opción 1 → `feliz` → la cara del robot cambia.
- Opción 2 → `45` → el cuello se mueve.
- Opción 3 → frecuencia `1000`, duración `0.3` → suena un beep.
- Opción 4 → el robot entra en estado seguro inmediatamente.

En paralelo, en la consola del servidor se ven los datos llegando con timestamp.

## Encapsulamiento de la HAL — Validación

El módulo `Comunicaciones.py` **nunca importa `machine`** ni accede a `Pin`, `PWM`, `ADC` o `I2C` directamente. Todas las acciones sobre hardware pasan por métodos de las clases `SensorBox` y `ActuatorBox` definidas en `dispositivos.py`.

Ejemplo del callback de la OLED (`Comunicaciones.py`):

```python
if topico_str == self.cmd_oled:
    self.actuadores.mostrar_emocion(mensaje_str)   # <- HAL
    self.cliente.publish(self.topico_estado_oled, mensaje_str)
```

No se ve un solo `Pin(13).value(...)` en el módulo de comunicaciones. Esto cumple la regla "Cero Lógica en el Main / Cero Pines en Comunicaciones".

## Reporte y análisis individual

El reporte completo con la sección de análisis individual por integrante (problema → solución → conclusión) se encuentra en `docs/Reporte.docx`.

## Licencia y autoría

Proyecto académico del Tecnológico Nacional de México — Instituto Tecnológico de León, 2026.
