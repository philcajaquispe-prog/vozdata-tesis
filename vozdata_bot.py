import os
import secrets
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
import io
import pandas as pd
import re
from datetime import datetime
import webbrowser
import uvicorn
import threading

app = FastAPI(
    title="VOZDATA",
    version="8.9",
    description="Sistema ERP inteligente y control por voz con diseño desplegable para bodegas peruanas."
)

# PIN de acceso de 4 dígitos
PIN_ACCESO = os.getenv("VOZDATA_PIN", "2026")
TOKEN_SESION = secrets.token_hex(16)
NOMBRE_COOKIE = "vozdata_pin_ok"

# Base de datos en memoria
inventario_negocio = {
    "gaseosa": {"stock": 45, "precio": 3.50, "costo": 2.50, "categoria": "Bebidas", "stock_minimo": 10},
    "agua": {"stock": 30, "precio": 2.00, "costo": 1.20, "categoria": "Bebidas", "stock_minimo": 8},
    "galleta": {"stock": 25, "precio": 1.50, "costo": 0.90, "categoria": "Snacks", "stock_minimo": 5},
    "arroz": {"stock": 100, "precio": 4.20, "costo": 3.40, "categoria": "Abarrotes", "stock_minimo": 15}
}

historial_ventas = []

class ComandoVoz(BaseModel):
    texto: str

class ProductoNuevo(BaseModel):
    nombre: str
    categoria: str
    stock: int
    precio: float
    costo: float

class PinAcceso(BaseModel):
    pin: str

def esta_autorizado(request: Request) -> bool:
    return request.cookies.get(NOMBRE_COOKIE) == TOKEN_SESION

HTML_PIN = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acceso - VOZDATA</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f0f7ff;
            color: #333;
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 85vh;
        }
        .pin-card {
            width: 100%;
            max-width: 360px;
            background: #ffffff;
            padding: 28px;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0, 123, 255, 0.12);
            text-align: center;
        }
        h2 {
            color: #0056b3;
            margin-top: 0;
            margin-bottom: 8px;
        }
        p {
            font-size: 13px;
            color: #555;
            margin-bottom: 18px;
        }
        input {
            width: 100%;
            padding: 12px;
            font-size: 24px;
            letter-spacing: 12px;
            text-align: center;
            border: 1px solid #b8d4fa;
            border-radius: 8px;
            box-sizing: border-box;
            margin-bottom: 14px;
        }
        button {
            width: 100%;
            background-color: #007bff;
            color: white;
            border: none;
            padding: 12px;
            font-size: 15px;
            font-weight: bold;
            border-radius: 8px;
            cursor: pointer;
        }
        button:hover {
            background-color: #0056b3;
        }
        #msgPin {
            margin-top: 12px;
            font-size: 13px;
            color: #c62828;
            min-height: 18px;
        }
    </style>
</head>
<body>
    <div class="pin-card">
        <h2>🎙️ VOZDATA</h2>
        <p>Ingresa tu código de acceso de 4 dígitos</p>
        <form onsubmit="validarPin(event)">
            <input type="password" id="pinInput" maxlength="4" minlength="4" pattern="[0-9]{4}" inputmode="numeric" autocomplete="off" placeholder="••••" required autofocus>
            <button type="submit">Ingresar</button>
        </form>
        <div id="msgPin"></div>
    </div>

    <script>
        async function validarPin(e) {
            e.preventDefault();
            const pin = document.getElementById('pinInput').value.trim();
            const msg = document.getElementById('msgPin');
            msg.innerText = "";

            const res = await fetch('/verificar-pin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin })
            });
            const data = await res.json();

            if (res.ok && data.status === "success") {
                location.reload();
            } else {
                msg.innerText = data.mensaje || "PIN incorrecto.";
                document.getElementById('pinInput').value = "";
                document.getElementById('pinInput').focus();
            }
        }
    </script>
</body>
</html>"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VOZDATA - Control Inteligente para Bodegas</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f0f7ff;
            color: #333;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: #ffffff;
            padding: 25px;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0, 123, 255, 0.1);
        }
        h1 {
            color: #0056b3;
            text-align: center;
            margin-bottom: 5px;
        }
        .subtitle {
            text-align: center;
            color: #555;
            font-size: 14px;
            margin-bottom: 20px;
        }
        .status-box {
            background-color: #e3f2fd;
            border-left: 5px solid #007bff;
            padding: 10px 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-weight: bold;
            color: #0d47a1;
            font-size: 13px;
        }
        .card {
            background: #f8fbff;
            border: 1px solid #d0e1fd;
            padding: 18px;
            border-radius: 12px;
            margin-bottom: 15px;
        }
        .card h3 {
            margin-top: 0;
            color: #0056b3;
            font-size: 16px;
        }
        .btn {
            display: block;
            width: 100%;
            background-color: #007bff;
            color: white;
            border: none;
            padding: 11px;
            font-size: 14px;
            font-weight: bold;
            border-radius: 8px;
            cursor: pointer;
            text-align: center;
            text-decoration: none;
            margin-top: 8px;
            transition: background 0.3s;
        }
        .btn:hover {
            background-color: #0056b3;
        }
        .btn-excel {
            background-color: #28a745;
        }
        .btn-excel:hover {
            background-color: #218838;
        }
        .btn-mic {
            background-color: #dc3545;
        }
        .btn-mic:hover {
            background-color: #c82333;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 8px;
        }
        th, td {
            border: 1px solid #d0e1fd;
            padding: 7px;
            text-align: left;
            font-size: 13px;
        }
        th {
            background-color: #e3f2fd;
            color: #0d47a1;
        }
        th.col-accion, td.col-accion {
            width: 45px;
            text-align: center;
            padding: 4px;
        }
        .btn-tacho {
            background: #dc3545;
            color: white;
            border: none;
            padding: 4px 6px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }
        .log-box {
            background: #1e1e1e;
            color: #00ff66;
            padding: 10px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 12px;
            margin-top: 8px;
            min-height: 35px;
        }
        details {
            background: #ffffff;
            border: 1px solid #bce8f1;
            border-radius: 8px;
            padding: 10px 15px;
            margin-top: 10px;
        }
        summary {
            font-weight: bold;
            color: #0056b3;
            cursor: pointer;
            font-size: 14px;
        }
        .form-control {
            width: 100%;
            padding: 7px;
            margin-top: 5px;
            margin-bottom: 8px;
            border: 1px solid #d0e1fd;
            border-radius: 6px;
            box-sizing: border-box;
            font-size: 13px;
        }
        .metric-box {
            background: #ffffff;
            border: 1px solid #d0e1fd;
            padding: 10px;
            border-radius: 6px;
            font-size: 13px;
            margin-bottom: 6px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎙️ VOZDATA</h1>
        <div class="subtitle">Sistema Inteligente de Control por Voz y Gestión para Bodegas</div>
        
        <div class="status-box">
            🟢 Estado del Servidor: Operativo en Red Local
        </div>

        <div class="card" style="border-color: #ffcdd2; background-color: #fff5f5;">
            <h3 style="color: #c62828;">🔴 Control por Voz en Vivo (IA en Red Local)</h3>
            <p style="font-size: 13px; color: #555; margin-bottom: 8px;">Haz clic en el botón y di tu orden (ej. <i>"vender dos gaseosas"</i>, <i>"tres aguas"</i>):</p>
            <button id="btnGrabar" class="btn btn-mic" onclick="toggleEscucha()">🎙️ Iniciar Reconocimiento de Voz</button>
            <div id="estadoGrabacion" class="log-box">Micrófono listo. Presiona el botón y habla...</div>
        </div>

        <div class="card">
            <h3>📦 Inventario Actual</h3>
            <div style="max-height: 180px; overflow-y: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>Producto</th>
                            <th>Categoría</th>
                            <th>Stock</th>
                            <th>Precio</th>
                            <th class="col-accion">Acción</th>
                        </tr>
                    </thead>
                    <tbody id="tablaInventario">
                        REPLACE_FILAS_INVENTARIO
                    </tbody>
                </table>
            </div>

            <details>
                <summary>➕ Agregar nuevo producto al inventario</summary>
                <form onsubmit="agregarProducto(event)" style="margin-top: 10px;">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                        <input type="text" id="nuevoNombre" placeholder="Nombre (ej. Leche)" required class="form-control">
                        <input type="text" id="nuevaCat" placeholder="Categoría (ej. Lácteos)" required class="form-control">
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px;">
                        <input type="number" id="nuevoStock" placeholder="Stock" required class="form-control" step="1">
                        <input type="number" id="nuevoPrecio" placeholder="Precio S/." required class="form-control" step="0.1">
                        <input type="number" id="nuevoCosto" placeholder="Costo S/." required class="form-control" step="0.1">
                    </div>
                    <button type="submit" class="btn" style="background-color: #17a2b8; margin-top: 4px;">Guardar Producto</button>
                </form>
            </details>
        </div>

        <div class="card">
            <h3>📊 Ventas del Día</h3>
            <div style="font-size: 13px; color: #666; margin-bottom: 4px;">Últimas transacciones registradas:</div>
            <div id="listaVentas" style="background: #fff; border: 1px solid #d0e1fd; padding: 8px; border-radius: 8px; height: 90px; overflow-y: auto; font-size: 12px; margin-bottom: 10px;">
                <span style="color: #888;">No hay ventas registradas en esta sesión.</span>
            </div>

            <details>
                <summary>💰 Ver Ventas Totales y Cantidad Vendida</summary>
                <div id="panelFinanciero" style="margin-top: 10px;">
                    <div class="metric-box">🛒 <b>Cantidad Total Vendida:</b> 0 un.</div>
                    <div class="metric-box">💵 <b>Ventas Totales del Día:</b> S/. 0.00</div>
                </div>
            </details>

            <br>
            <a href="/descargar-excel" class="btn btn-excel">📥 Descargar Reporte General en Excel</a>
        </div>
    </div>

    <script>
        let recognition;
        let escuchando = false;

        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.lang = 'es-PE';
            recognition.continuous = false;
            recognition.interimResults = false;

            recognition.onresult = async function(event) {
                const textoTranscrito = event.results[0][0].transcript;
                document.getElementById('estadoGrabacion').innerText = "🗣️ Dijiste: \\"" + textoTranscrito + "\\". Procesando...";
                
                try {
                    const response = await fetch('/procesar-voz-texto/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ texto: textoTranscrito })
                    });
                    const resultado = await response.json();

                    if (resultado.status === "success") {
                        document.getElementById('estadoGrabacion').innerText = "✅ " + resultado.mensaje;
                        actualizarTodoUI(resultado);
                    } else {
                        document.getElementById('estadoGrabacion').innerText = "⚠️ " + resultado.mensaje;
                    }
                } catch (e) {
                    document.getElementById('estadoGrabacion').innerText = "❌ Error de conexión.";
                }
                restaurarBoton();
            };

            recognition.onerror = function(event) {
                document.getElementById('estadoGrabacion').innerText = "❌ Error de voz: " + event.error;
                restaurarBoton();
            };

            recognition.onend = function() {
                if (escuchando) restaurarBoton();
            };
        }

        function toggleEscucha() {
            const btn = document.getElementById('btnGrabar');
            const logBox = document.getElementById('estadoGrabacion');
            if (!escuchando) {
                try {
                    recognition.start();
                    escuchando = true;
                    btn.style.backgroundColor = "#6c757d";
                    btn.innerText = "Escuchando...";
                    logBox.innerText = "🔴 Escuchando orden de venta...";
                } catch (e) {
                    recognition.stop();
                    restaurarBoton();
                }
            } else {
                recognition.stop();
                restaurarBoton();
            }
        }

        function restaurarBoton() {
            escuchando = false;
            const btn = document.getElementById('btnGrabar');
            btn.style.backgroundColor = "#dc3545";
            btn.innerText = "🎙️ Iniciar Reconocimiento de Voz";
        }

        async function agregarProducto(e) {
            e.preventDefault();
            const nombre = document.getElementById('nuevoNombre').value;
            const categoria = document.getElementById('nuevaCat').value;
            const stock = document.getElementById('nuevoStock').value;
            const precio = document.getElementById('nuevoPrecio').value;
            const costo = document.getElementById('nuevoCosto').value;

            const response = await fetch('/producto/agregar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nombre, categoria, stock: parseInt(stock), precio: parseFloat(precio), costo: parseFloat(costo) })
            });
            const res = await response.json();
            if (res.status === "success") location.reload();
        }

        async function eliminarProducto(nombre) {
            if (confirm("¿Eliminar " + nombre + "?")) {
                const response = await fetch('/producto/eliminar/' + nombre, { method: 'DELETE' });
                const res = await response.json();
                if (res.status === "success") location.reload();
            }
        }

        function actualizarTodoUI(resultado) {
            const tbody = document.getElementById('tablaInventario');
            tbody.innerHTML = "";
            for (const [prod, info] of Object.entries(resultado.inventario)) {
                let alerta = "";
                if (info.stock <= 0) alerta = " <span style='color: red; font-weight: bold;'>(¡AGOTADO!)</span>";
                else if (info.stock <= info.stock_minimo) alerta = " <span style='color: #e65100; font-weight: bold;'>(¡Stock Bajo!)</span>";
                
                tbody.innerHTML += `
                    <tr>
                        <td><b>${prod.charAt(0).toUpperCase() + prod.slice(1)}</b>${alerta}</td>
                        <td>${info.categoria}</td>
                        <td><b>${info.stock}</b> un.</td>
                        <td>S/. ${info.precio.toFixed(2)}</td>
                        <td class="col-accion"><button class="btn-tacho" onclick="eliminarProducto('${prod}')" title="Eliminar">🗑️</button></td>
                    </tr>
                `;
            }

            const hist = document.getElementById('listaVentas');
            hist.innerHTML = "";
            resultado.historial_completo.slice().reverse().forEach(v => {
                hist.innerHTML += `<div style="border-bottom: 1px solid #eee; padding: 2px 0;">🕒 <b>[${v.fecha_hora}]</b> 🛍️ ${v.producto}: <b>${v.cantidad} un.</b> (S/. ${v.total.toFixed(2)})</div>`;
            });

            actualizarFinancieroUI(resultado.finanzas);
        }

        function actualizarFinancieroUI(f) {
            document.getElementById('panelFinanciero').innerHTML = `
                <div class="metric-box">🛒 <b>Cantidad Total Vendida:</b> ${f.cantidad_total_unidades} un.</div>
                <div class="metric-box">💵 <b>Ventas Totales del Día:</b> S/. ${f.total_ventas.toFixed(2)}</div>
            `;
        }
    </script>
</body>
</html>"""

@app.post("/verificar-pin")
def verificar_pin(data: PinAcceso, response: Response):
    if data.pin.strip() == PIN_ACCESO:
        response.set_cookie(
            key=NOMBRE_COOKIE,
            value=TOKEN_SESION,
            httponly=True,
            samesite="lax"
        )
        return {"status": "success"}
    raise HTTPException(status_code=401, detail="PIN incorrecto")

@app.get("/", response_class=HTMLResponse)
def inicio_web(request: Request):
    if not esta_autorizado(request):
        return HTMLResponse(content=HTML_PIN)

    filas_inventario = ""
    for prod, info in inventario_negocio.items():
        estado_alerta = ""
        if info["stock"] <= 0:
            estado_alerta = " <span style='color: red; font-weight: bold;'>(¡AGOTADO!)</span>"
        elif info["stock"] <= info["stock_minimo"]:
            estado_alerta = " <span style='color: #e65100; font-weight: bold;'>(¡Stock Bajo!)</span>"
            
        filas_inventario += f"""
            <tr>
                <td><b>{prod.capitalize()}</b>{estado_alerta}</td>
                <td>{info['categoria']}</td>
                <td><b>{info['stock']}</b> un.</td>
                <td>S/. {info['precio']:.2f}</td>
                <td class="col-accion">
                    <button class="btn-tacho" onclick="eliminarProducto('{prod}')" title="Eliminar">🗑️</button>
                </td>
            </tr>
        """
    
    html_final = HTML_TEMPLATE.replace("REPLACE_FILAS_INVENTARIO", filas_inventario)
    return HTMLResponse(content=html_final)

@app.post("/producto/agregar")
def agregar_producto(p: ProductoNuevo, request: Request):
    if not esta_autorizado(request):
        raise HTTPException(status_code=401, detail="No autorizado")
    key = p.nombre.lower().strip()
    inventario_negocio[key] = {
        "stock": p.stock,
        "precio": p.precio,
        "costo": p.costo,
        "categoria": p.categoria,
        "stock_minimo": 5
    }
    return {"status": "success"}

@app.delete("/producto/eliminar/{nombre}")
def eliminar_producto(nombre: str, request: Request):
    if not esta_autorizado(request):
        raise HTTPException(status_code=401, detail="No autorizado")
    key = nombre.lower().strip()
    if key in inventario_negocio:
        del inventario_negocio[key]
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="No encontrado")

def calcular_finanzas():
    total_ventas = sum(v["total"] for v in historial_ventas)
    cantidad_total_unidades = sum(v["cantidad"] for v in historial_ventas)
    return {"total_ventas": total_ventas, "cantidad_total_unidades": cantidad_total_unidades}

@app.post("/procesar-voz-texto/")
def procesar_voz_texto(data: ComandoVoz, request: Request):
    if not esta_autorizado(request):
        raise HTTPException(status_code=401, detail="No autorizado")
    texto = data.texto.lower()
    mapa_numeros = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10}
    
    cantidad = 1
    match_numero = re.search(r'\d+', texto)
    if match_numero:
        cantidad = int(match_numero.group())
    else:
        for palabra, num in mapa_numeros.items():
            if palabra in texto:
                cantidad = num
                break

    producto_detectado = None
    palabras_texto = texto.split()
    
    for palabra in palabras_texto:
        palabra_limpia = palabra
        if palabra.endswith("es"):
            palabra_limpia = palabra[:-2]
        elif palabra.endswith("s"):
            palabra_limpia = palabra[:-1]
            
        if palabra_limpia in inventario_negocio:
            producto_detectado = palabra_limpia
            break
        elif palabra in inventario_negocio:
            producto_detectado = palabra
            break

    if not producto_detectado:
        return {"status": "error", "mensaje": f"No reconocí producto en: '{texto}'. Prueba diciendo 'vender dos gaseosas'."}

    item = inventario_negocio[producto_detectado]
    if item["stock"] < cantidad:
        return {"status": "error", "mensaje": f"Stock insuficiente para {producto_detectado}."}

    item["stock"] -= cantidad
    ingreso_total = cantidad * item["precio"]
    fecha_hora_actual = datetime.now().strftime("%d/%m/%Y %H:%M")

    venta_info = {
        "fecha_hora": fecha_hora_actual,
        "producto": producto_detectado.capitalize(),
        "cantidad": cantidad,
        "total": ingreso_total
    }
    historial_ventas.append(venta_info)

    return {
        "status": "success",
        "mensaje": f"Registrado: {cantidad} {producto_detectado}(s). S/. {ingreso_total:.2f}",
        "inventario": inventario_negocio,
        "historial_completo": historial_ventas,
        "finanzas": calcular_finanzas()
    }

@app.get("/descargar-excel")
def descargar_excel(request: Request):
    if not esta_autorizado(request):
        raise HTTPException(status_code=401, detail="No autorizado")
    data_inv = []
    for p, info in inventario_negocio.items():
        data_inv.append({
            "Producto": p.capitalize(),
            "Categoría": info["categoria"],
            "Stock Actual": info["stock"],
            "Stock Mínimo": info["stock_minimo"],
            "Precio Venta (S/.)": info["precio"],
            "Precio Costo (S/.)": info["costo"]
        })
    df_inv = pd.DataFrame(data_inv)
    df_ventas = pd.DataFrame(historial_ventas) if historial_ventas else pd.DataFrame(columns=["fecha_hora", "producto", "cantidad", "total"])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_inv.to_excel(writer, sheet_name='Inventario General', index=False)
        df_ventas.to_excel(writer, sheet_name='Historial Ventas', index=False)
    output.seek(0)

    headers = {'Content-Disposition': 'attachment; filename="Reporte_General_VozData.xlsx"'}
    return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == "__main__":
    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:8000")).start()
    uvicorn.run(app, host="127.0.0.1", port=8000)