# Easy Autoclicker

Autoclicker y auto presser de teclado gratuito y sin funciones "premium"
bloqueadas detrás de un pago. Pensado como alternativa libre a programas como
OP Auto Clicker o distintos keyboard pressers que piden suscripción para
desbloquear lo básico.

## Funciones

- **Clic de mouse automático**: botón izquierdo/derecho/medio, clic simple,
  doble o triple, intervalo fijo o aleatorio (con rango mín/máx), retraso
  inicial, repetición infinita o por cantidad de clics, y posición fija o en
  la posición actual del cursor. La posición fija admite una variación de ±N
  píxeles para que los clics no caigan siempre en el mismo punto exacto.
- **Teclas y combinaciones simultáneas**: agrega tantas teclas como quieras,
  cada una con su propio intervalo (con variación aleatoria opcional),
  retraso inicial, cantidad de repeticiones y modo "Pulsar" (tap continuo) o
  "Mantener" (tecla presionada todo el rato, útil para correr en un juego).
  Cada fila acepta combinaciones completas como `ctrl+shift+a`, y el botón
  **Capturar** evita tener que acordarse del nombre de la tecla.
- **Grabador de macros**: graba una secuencia real de movimientos de mouse,
  clics, scroll y teclas, y reprodúcela en loop o una cantidad de veces, con
  **control de velocidad** (de 0.25x a 4x). Se puede grabar sin los
  movimientos del mouse para que la macro quede chica y el cursor no se
  mueva. Las hotkeys del programa no quedan grabadas dentro de la macro.
- **Secuencia de pasos**: encadena pasos que corren uno tras otro (no
  simultáneos): pulsar una tecla o combinación N veces, mantenerla X
  segundos, hacer clic, mantener el clic, mover el mouse a una posición,
  usar la rueda, escribir un texto, esperar X segundos o esperar un tiempo
  al azar dentro de un rango. Los pasos se reordenan, se duplican y se
  pueden desmarcar para saltearlos sin borrarlos.
- **Hotkeys globales configurables, con modificadores**: iniciar/detener,
  pánico (detiene todo), grabar macro, reproducir macro y ejecutar
  secuencia. Se asignan presionando la combinación deseada (`f6`,
  `ctrl+shift+k`, lo que sea) y el programa avisa si una combinación ya está
  usada por otra acción.
- **Límite de tiempo**: opción de detener todo automáticamente después de N
  segundos.
- **Estado en vivo**: contador de clics, tiempo corriendo y clics por
  segundo reales.
- **Perfiles guardables**: guarda cualquier combinación de ajustes (mouse,
  teclas, pasos y hotkeys) como un perfil con nombre.
- **Macros y secuencias con nombre**: se guardan, cargan y eliminan desde la
  propia ventana, y también se pueden importar o exportar como archivos
  `.json` para compartirlas.
- **Configuración persistente**: la app recuerda los últimos ajustes y el
  tamaño de la ventana entre una sesión y otra.
- **Bandeja del sistema**: permite minimizar la ventana a la bandeja en lugar
  de cerrarla (requiere `pystray` y `Pillow`, incluidos en
  `requirements.txt`).
- **Siempre visible**: opción de mantener la ventana por encima del resto.
- **Pestaña de ayuda** con los nombres de tecla reconocidos y cómo se escribe
  cada cosa.

Todo lo anterior está disponible siempre, sin límites de tiempo ni capas de
pago.

## Seguridad al automatizar

El hotkey de pánico detiene todo de golpe y suelta cualquier tecla o botón
que haya quedado presionado, así que una tecla en modo "Mantener" o una macro
cortada a mitad no deja el teclado trabado. El límite de tiempo de la
pestaña Ajustes sirve como red extra si dejas algo corriendo y te olvidas.

## Uso

```bash
pip install -r requirements.txt
python autoclicker.py
```

### Pruebas

```bash
pip install -r requirements-dev.txt
python -m pytest tests
```

Las pruebas cubren la lógica que no depende de la interfaz: interpretación de
nombres de tecla y combinaciones, ejecución de secuencias, macros, hotkeys y
persistencia en disco. Usan controladores falsos, así que no mueven el mouse
ni escriben nada de verdad.

### Compilar a ejecutable (Windows)

```bash
pyinstaller EasyAutoclicker.spec
```

El ejecutable queda en `dist/EasyAutoclicker.exe`.

## Advertencia

Usa este programa de forma responsable. Automatizar clics o teclas puede
violar los términos de servicio de algunos juegos o aplicaciones; la
responsabilidad de ese uso es de quien lo ejecuta.

## Licencia

MIT. Ver [LICENSE](LICENSE).
