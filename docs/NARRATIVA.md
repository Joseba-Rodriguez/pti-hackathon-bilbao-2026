# Narrativa del pitch: PTI, «Tú apuntas. El robot hace el resto.»

Base: el vídeo `WhatsApp Video 2026-11-21 at 01.31.05.mp4`, de 62 s. Secuencia: Bilbao, 48 h → zona restringida
(uranio) → guiado por láser (apunta, coge, traza, deja) → 30 s de demo real → «Hoy, en un laboratorio»
→ «Mañana… en la Luna» → PTI.

## La idea en una frase
Hay objetos que ninguna mano humana debería tocar. Con PTI, el operador **apunta con un láser desde
fuera** y el robot, entrenado por imitación, **lo coge y lo lleva allí solo**. No hace falta mando, ni
programar, ni un operador experto.

## Por qué el láser (la respuesta a «¿por qué no teleoperar?»)
1. **Hoy, en el laboratorio (celdas calientes y cajas de guantes).** Para mover material radiactivo se usan
   brazos maestro-esclavo o guantes a través de un cristal. Hacen falta operadores formados, el trabajo es
   lento y cansa. Apuntar es algo que sabe hacer cualquiera: le dices al robot **qué** quieres y él
   resuelve el **cómo**.
2. **Mañana, en la Luna.** Entre la Tierra y la Luna la señal tarda ~1,3 s en cada sentido (~2,6 s
   ida y vuelta). Teleoperar un brazo con 2,6 s de retraso es casi imposible. La solución es
   **autonomía supervisada**: desde la Tierra se marca el objetivo (un punto) y el robot ejecuta en
   local. Un punto láser es justo eso, una orden de alto nivel que aguanta el retraso.
3. **Sin electrónica extra.** Bastan un puntero láser de 5 €, la cámara del puesto y el brazo. Toda la
   inteligencia está en la política aprendida y en la visión.

## Guion de 5 minutos (encaja con el vídeo)

| Tiempo | Qué pasa | Qué se dice |
| --- | --- | --- |
| 0:00–0:30 | Vídeo: zona restringida | «Hay materiales que ninguna mano humana debería tocar. Hoy se manejan con guantes a través de un cristal o con brazos maestro-esclavo que requieren meses de formación.» |
| 0:30–0:50 | Plano del láser | «Nuestra propuesta: tú apuntas, el robot hace el resto.» |
| 0:50–2:00 | **Demo en vivo**: coger el contenedor y llevarlo al punto del láser | Narrar poco. Señalar el mapa en pantalla: «el robot ve el punto y lo sitúa en la mesa en centímetros». |
| 2:00–3:30 | Cómo está hecho | SO-101 + LeRobot. Políticas ACT por imitación, en dos habilidades: *coger* y *llevar al láser*. 50 demostraciones grabadas aquí, 20 000 pasos de entrenamiento en un portátil (3 h). Filtro de visión propio: el láser ocupa 2–3 píxeles y lo convertimos en una marca que la red sí ve. **Tasa de éxito: X/10** (de la tabla del diario). |
| 3:30–4:30 | Qué falló y cómo lo arreglamos | 1.ª versión: 1 de 5 aciertos y temblaba (15 demos largas) → más y mejores demos. El filtro confundía el láser con la base naranja y con el propio brazo → detector de picos (top-hat) y descarte de manchas grandes: 0 falsos en 935 fotogramas. FFmpeg incompatible, voltaje del leader… (de `DIARIO.md`). |
| 4:30–5:00 | Vídeo: la Luna | «Hoy, en un laboratorio. Mañana, en la Luna, donde no se puede teleoperar con 2,6 s de retraso. Tú apuntas. El robot hace el resto. Equipo PTI.» |

## Atrezo y vocabulario de la demo
- El bote de tapa blanca es el **«contenedor de muestra»**. Se le puede pegar un trébol radiactivo
  **impreso en negro o amarillo, nunca rojo ni naranja** (el filtro lo tomaría por el láser).
- El soporte es el **«almacén blindado»** y el destino es la **«zona de análisis»**, marcada con cinta negra.
- Ningún material real, obviamente. Aviso en la diapositiva: *concepto; el contenedor está vacío*.

## Preguntas probables del jurado
- **¿Por qué no un brazo programado con coordenadas?** Porque el destino cambia cada vez y lo elige una
  persona en el momento. Una cámara más un láser es la interfaz más simple que existe, y la política
  aprendida tolera variaciones (posición del bote, luz) que con un script fijo romperían la tarea.
- **¿Funciona con otro objeto?** Con unas 50 demostraciones nuevas sí: es imitación, no programación.
- **¿Y si el láser apunta a un sitio peligroso?** → Zonas prohibidas en el mapa (ver la siguiente
  sección).

## Utilidades extra (baratas y sin mover el brazo)
1. **Zonas prohibidas:** en el mapa se dibuja en rojo una zona donde no se puede dejar el contenedor
   (por ejemplo, junto al operador). Si el láser apunta ahí, el robot **no obedece** y lo avisa en
   pantalla. Es solo software sobre el mapa y responde a la pregunta de seguridad.
2. **Registro de trazabilidad:** cada movimiento queda apuntado (hora, origen, destino en cm y
   resultado). En la industria nuclear la contabilidad del material es obligatoria, así que esto le da
   cara de producto.
3. **Confirmar antes de mover:** al ver el láser, la pantalla muestra «destino (x, y) cm, ¿confirmar?»
   y el operador pulsa una tecla. Es la autonomía *supervisada* del discurso.
