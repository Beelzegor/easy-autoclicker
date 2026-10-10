# Easy Autoclicker

Autoclicker y auto presser de teclado gratuito y sin funciones "premium"
bloqueadas detrás de un pago. Pensado como alternativa libre a programas como
OP Auto Clicker o distintos keyboard pressers que piden suscripción para
desbloquear lo básico.

## Funciones

- **Clic de mouse automático**: botón izquierdo/derecho/medio, clic simple,
  doble o triple, intervalo fijo o aleatorio (con rango mín/máx), retraso
  inicial, repetición infinita o por cantidad de clics, y posición fija o en
  la posición actual del cursor.
- **Teclas simultáneas**: agrega tantas teclas como quieras, cada una con su
  propio intervalo, retraso inicial, cantidad de repeticiones y modo
  "Pulsar" (tap continuo) o "Mantener" (tecla presionada todo el rato, útil
  para correr en un juego).
- **Grabador de macros**: graba una secuencia real de movimientos de mouse,
  clics, scroll y teclas, y reprodúcela en loop o una cantidad de veces.
  Las macros se pueden guardar y cargar como archivos `.json`.
- **Hotkeys configurables**: asigna la tecla que prefieras para
  iniciar/detener y para el botón de pánico (detiene todo, incluida la
  grabación o reproducción de macros), sin quedar atado a F6/Esc.
- **Perfiles guardables**: guarda cualquier combinación de ajustes como un
  perfil con nombre y vuelve a cargarlo cuando quieras.
- **Configuración persistente**: la app recuerda los últimos ajustes usados
  entre una sesión y otra.
- **Bandeja del sistema**: permite minimizar la ventana a la bandeja en lugar
  de cerrarla (requiere `pystray` y `Pillow`, incluidos en `requirements.txt`).
- **Siempre visible**: opción de mantener la ventana por encima del resto.

Todo lo anterior está disponible siempre, sin límites de tiempo ni capas de
pago.

## Uso

```bash
pip install -r requirements.txt
python autoclicker.py
```

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
