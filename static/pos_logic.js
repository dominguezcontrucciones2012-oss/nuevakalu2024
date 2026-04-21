// --- CEREBRO DEL POS KALU 2.0 ---
let carrito = [];
const buscador = document.getElementById("buscador_producto");
const cuerpoCarrito = document.getElementById("cuerpo_carrito");
const totalUsdDisplay = document.getElementById("total_usd");
const totalBsDisplay = document.getElementById("total_bs");

// 1. BUSCADOR INTELIGENTE
buscador.addEventListener("input", (e) => {
  const busqueda = e.target.value.trim().toLowerCase();
  if (busqueda.length < 2) return;

  // Filtrar productos que coincidan con nombre o código
  const coincidencias = PRODUCTOS_DB.filter(p =>
    p.nombre.toLowerCase().includes(busqueda) ||
    p.codigo.toLowerCase().includes(busqueda)
  );

  // Si hay una coincidencia exacta por código (pistola de barras), agregar de una
  const exacto = coincidencias.find(p => p.codigo.toLowerCase() === busqueda);

  if (exacto) {
    agregarAlCarrito(exacto);
    e.target.value = "";
  }
  // Nota: Aquí podrías implementar un desplegable visual si hay muchas coincidencias
  else if (coincidencias.length === 1 && busqueda.length > 5) {
    agregarAlCarrito(coincidencias[0]);
    e.target.value = "";
  }
});

// 2. AGREGAR AL CARRITO
function agregarAlCarrito(producto) {
  const existe = carrito.find((item) => item.id === producto.id);

  if (existe) {
    if (existe.cantidad < producto.stock) {
      existe.cantidad++;
    } else {
      alert("⚠️ ¡No hay más stock de este producto!");
    }
  } else {
    carrito.push({
      id: producto.id,
      nombre: producto.nombre,
      precio: producto.precio,
      cantidad: 1
    });
  }
  renderizarCarrito();
}

// 3. DIBUJAR LA TABLA Y CALCULAR TOTALES
function renderizarCarrito() {
  if (!cuerpoCarrito) return;
  cuerpoCarrito.innerHTML = "";
  let totalUsd = 0;

  carrito.forEach((item, index) => {
    const subtotal = item.precio * item.cantidad;
    totalUsd += subtotal;

    cuerpoCarrito.innerHTML += `
            <tr>
                <td class="fw-bold">${item.nombre}</td>
                <td>
                    <input type="number" class="form-control form-control-sm w-75" 
                           value="${item.cantidad}" min="0.01" step="0.01"
                           onchange="actualizarCantidad(${index}, this.value)">
                </td>
                <td class="text-primary fw-bold">$${item.precio.toFixed(2)}</td>
                <td class="fw-bold">$${subtotal.toFixed(2)}</td>
                <td>
                    <button class="btn btn-outline-danger btn-sm border-0" onclick="eliminarItem(${index})">
                        <i class="fas fa-times"></i>
                    </button>
                </td>
            </tr>
        `;
  });

  const totalBs = totalUsd * (typeof tasa_dia !== 'undefined' ? tasa_dia : 1);
  totalUsdDisplay.innerText = totalUsd.toFixed(2);
  totalBsDisplay.innerText = totalBs.toLocaleString("es-VE", {
    minimumFractionDigits: 2,
  });

  // Actualizamos el vuelto cada vez que cambia el carrito
  actualizarVuelto();
}

function actualizarCantidad(index, nuevaCant) {
  const cant = parseFloat(nuevaCant);
  if (isNaN(cant) || cant <= 0) return;
  carrito[index].cantidad = cant;
  renderizarCarrito();
}

function eliminarItem(index) {
  carrito.splice(index, 1);
  renderizarCarrito();
}

// 5. ✅ CONTROL DEL BOTÓN (El que estaba flojo)
function actualizarVuelto() {
  const totalUsdDisplay = document.getElementById("total_usd");
  const totalVentaUsd = parseFloat(totalUsdDisplay ? totalUsdDisplay.innerText : 0) || 0;
  const current_tasa = typeof tasa_dia !== 'undefined' ? tasa_dia : 1;

  // 1. Capturamos todos los montos con los IDs correctos que están en pos.html
  const pUsd = parseFloat(document.getElementById("pago_usd")?.value) || 0;
  const pBs = parseFloat(document.getElementById("pago_bs_efec")?.value) || 0;
  const pPm = parseFloat(document.getElementById("pago_pm")?.value) || 0;
  const pTr = parseFloat(document.getElementById("pago_debito")?.value) || 0;
  const pBio = parseFloat(document.getElementById("pago_bio")?.value) || 0;

  // 2. Cálculos en Bolívares usando la tasa del día
  const totalDebeBs = Math.round((totalVentaUsd * current_tasa) * 100) / 100;
  const totalPagadoBs = Math.round(((pUsd * current_tasa) + pBs + pPm + pTr + pBio) * 100) / 100;
  const diferenciaBs = Math.round((totalPagadoBs - totalDebeBs) * 100) / 100;

  // Sincronizamos con los IDs de los botones del modal y la vista
  const btnCobrar = document.getElementById("btn_finalizar") || document.getElementById("btn_cobrar");
  const divVuelto = document.getElementById("estado_pago") || document.getElementById("div_vuelto");

  if (!btnCobrar) return;

  // --- EL CANDADO DE SEGURIDAD ---
  if (diferenciaBs < 0) {
    // ❌ FALTA DINERO: Botón Gris y Bloqueado
    btnCobrar.disabled = true;
    btnCobrar.classList.remove("btn-success");
    btnCobrar.classList.add("btn-secondary");

    if (divVuelto) {
      divVuelto.className = "alert alert-danger mt-2 fw-bold text-center";
      divVuelto.innerHTML = `<i class="fas fa-times-circle"></i> FALTAN: Bs. ${Math.abs(diferenciaBs).toFixed(2)}`;
    }
  } else {
    // ✅ PAGO COMPLETO O VUELTO: Botón Verde y Activo
    btnCobrar.disabled = false;
    btnCobrar.classList.remove("btn-secondary");
    btnCobrar.classList.add("btn-success");

    if (divVuelto) {
      divVuelto.className = "alert alert-success mt-2 fw-bold text-center";
      divVuelto.innerHTML = `<i class="fas fa-check-circle"></i> VUELTO: Bs. ${diferenciaBs.toFixed(2)}`;
    }
  }
}

// 7. PROCESAR LA VENTA (Enviar al Servidor)
function procesarVenta(tipo) {
  if (carrito.length === 0) {
    alert("❌ El carrito está vacío");
    return;
  }

  const totalVenta = parseFloat(totalUsdDisplay.innerText) || 0;
  const current_tasa = typeof tasa_dia !== 'undefined' ? tasa_dia : 1;
  const pUsd = parseFloat(document.getElementById("pago_usd")?.value) || 0;
  const pBs = parseFloat(document.getElementById("pago_bs_efec")?.value) || 0;
  const pPm = parseFloat(document.getElementById("pago_pm")?.value) || 0;
  const pTr = parseFloat(document.getElementById("pago_debito")?.value) || 0;
  const pBio = parseFloat(document.getElementById("pago_bio")?.value) || 0;

  const safeUUID = () => {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
    return 'kalu-' + Date.now() + '-' + Math.floor(Math.random() * 1e9);
  };

  const data = {
    cliente_id: document.getElementById("cliente_id").value,
    cliente_tipo: document.getElementById("cliente_tipo")?.value || "cliente",
    tipo_venta: tipo,
    items: carrito,
    total_usd: totalVenta,
    tasa: current_tasa,
    pago_efectivo_usd: pUsd,
    pago_efectivo_bs: pBs,
    pago_movil_bs: pPm,
    pago_transferencia_bs: pTr,
    biopago_bdv: pBio,
    transaction_token: safeUUID()
  };

  fetch("/procesar_venta", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
    .then((res) => res.json())
    .then((res) => {
      if (res.success) {
        alert("✅ ¡Venta Registrada con Éxito!");
        location.reload();
      } else {
        alert("❌ Error: " + res.message);
      }
    });
}

// --- ESTO HACE QUE EL BOTÓN REACCIONE MIENTRAS ESCRIBES ---
document.addEventListener("input", (e) => {
  const idsPagos = ["pago_usd", "pago_bs_efec", "pago_pm", "pago_debito", "pago_bio"];
  if (idsPagos.includes(e.target.id)) {
    actualizarVuelto();
  }
});

// --- FORMATEADOR DE MONEDA "KALU" (ESTILO CAJERO AUTOMÁTICO) ---
function aplicarMascaraMoneda(idCampo) {
  const input = document.getElementById(idCampo);
  if (!input) return;

  // Forzamos que sea texto para que no pelee con los puntos
  input.type = "text";
  input.style.textAlign = "right";
  if (input.value === "") input.value = "0.00";

  input.addEventListener("input", function (e) {
    // 1. Solo dejamos los números
    let valor = this.value.replace(/\D/g, "");

    // 2. Si borra todo, ponemos 0.00
    if (valor === "") {
      this.value = "0.00";
    } else {
      // 3. Convertimos a número y rodamos el punto 2 espacios
      let numero = (parseInt(valor) / 100).toFixed(2);
      this.value = numero;
    }

    // 4. ⚠️ ¡IMPORTANTE!: Llamamos a su función de cobrar para que el botón reaccione
    if (typeof actualizarVuelto === 'function') {
      actualizarVuelto();
    }
  });

  // Limpiar al entrar para escribir rápido
  input.addEventListener("focus", function () {
    if (this.value === "0.00") this.value = "";
  });

  // Poner 0.00 al salir si quedó vacío
  input.addEventListener("blur", function () {
    if (this.value === "" || this.value === ".") this.value = "0.00";
  });
}

// --- ACTIVAR EN TODOS LOS CAMPOS APENAS CARGUE ---
function activarMascaras() {
  const campos = [
    "pago_usd",
    "pago_bs_efec",
    "pago_pm",
    "pago_debito",
    "pago_bio"
  ];
  campos.forEach(id => aplicarMascaraMoneda(id));
}

// Ejecutamos de una vez
activarMascaras();

// Y por si acaso el POS tarda en cargar, re-intentamos en 1 segundo
setTimeout(activarMascaras, 1000);

// --- FUNCIÓN ABORTAR VENTA ---
function abortarVenta() {
  // 1. Verificar que haya algo en el carrito
  if (carrito.length === 0) {
    alert("⚠️ El carrito ya está vacío.");
    return;
  }

  // 2. Pedir confirmación antes de borrar todo
  const confirmar = confirm("⚠️ ¿Está seguro que desea ABORTAR esta venta?\nSe vaciará todo el carrito.");
  if (!confirmar) return;

  // 3. Limpiar el carrito
  carrito = [];
  renderizarCarrito();

  // 4. Limpiar todos los campos de pago
  const camposPago = [
    "pago_usd",
    "pago_bs_efec",
    "pago_pm",
    "pago_debito",
    "pago_bio"
  ];
  camposPago.forEach(id => {
    const campo = document.getElementById(id);
    if (campo) campo.value = "0.00";
  });

  // 5. Resetear el vuelto
  const divVuelto = document.getElementById("div_vuelto");
  if (divVuelto) {
    divVuelto.className = "alert alert-secondary mt-2 fw-bold text-center";
    divVuelto.innerHTML = `<i class="fas fa-info-circle"></i> Ingrese los montos de pago`;
  }

  // 5.5 Resetear estado de pago
  const estadoPago = document.getElementById("estado_pago");
  if (estadoPago) estadoPago.style.display = "none";

  // 6. ✅ ALERTA DE CONFIRMACIÓN CON BOTÓN OK
  alert("🚫 VENTA ABORTADA\n\nEl carrito fue vaciado exitosamente.\nPuede iniciar una nueva venta.");
}

// --- LOGICA DE PEDIDOS REMOTOS ---
function cargarPedidoEnCarrito(pedidoId) {
  if (carrito.length > 0 && !confirm("⚠️ Tienes productos en el carrito. ¿Deseas reemplazarlos con el pedido?")) return;

  fetch(`/api/pedido/${pedidoId}`)
    .then(r => r.json())
    .then(data => {
      if (!data.success) { alert(data.message); return; }

      carrito = data.items.map(item => ({
        id: item.producto_id,
        nombre: item.nombre,
        precio: item.precio,
        cantidad: item.cantidad
      }));

      // Auto-seleccionar cliente
      const clienteInput = document.getElementById("cliente_input");
      const clienteIdHidden = document.getElementById("cliente_id");
      if (data.cliente) {
        clienteInput.value = `${data.cliente.cedula} - ${data.cliente.nombre}`;
        clienteIdHidden.value = data.cliente.id;
        // Disparar evento input para activar alerta de deuda
        clienteInput.dispatchEvent(new Event('input'));
      }

      renderizarCarrito();
      alert("✅ Pedido cargado. Verifique cantidades y finalice la venta.");
      bootstrap.Modal.getInstance(document.getElementById('modalPedidos')).hide();
    });
}

// --- FUNCIONES PARA ALERTAS Y NOTIFICACIONES ---
const audioAlerta = new Audio('/static/audio/alerta.mp3'); // Asegúrate de tener este archivo de sonido
let ultimosPedidosCount = 0;
let ultimosPagosCount = 0;

async function actualizarAlertasPOS() {
  const alertaGeneralDiv = document.getElementById('alerta_general_pos');
  const badgePedidos = document.getElementById('badge_pedidos');
  const badgePagos = document.getElementById('badge_pagos');
  let hayNovedades = false;
  let mensajeAlerta = "";

  // 1. Revisar Pedidos Pendientes
  const pedidosRes = await fetch('/api/pedidos/pendientes').then(r => r.json());
  if (pedidosRes.length > 0) {
    badgePedidos.innerText = pedidosRes.length;
    badgePedidos.classList.remove('d-none');
    mensajeAlerta += `🚨 ${pedidosRes.length} PEDIDO(S) NUEVO(S) | `;
    if (pedidosRes.length > ultimosPedidosCount) hayNovedades = true;
  } else {
    badgePedidos.classList.add('d-none');
  }
  ultimosPedidosCount = pedidosRes.length;

  // 2. Revisar Pagos Reportados Pendientes
  const pagosRes = await fetch('/api/pagos_reportados/pendientes').then(r => r.json());
  if (pagosRes.length > 0) {
    badgePagos.innerText = pagosRes.length;
    badgePagos.classList.remove('d-none');
    mensajeAlerta += `💰 ${pagosRes.length} PAGO(S) REPORTADO(S)`;
    if (pagosRes.length > ultimosPagosCount) hayNovedades = true;
  } else {
    badgePagos.classList.add('d-none');
  }
  ultimosPagosCount = pagosRes.length;

  // 3. Mostrar/Ocultar Alerta General
  if (pedidosRes.length > 0 || pagosRes.length > 0) {
    alertaGeneralDiv.innerHTML = mensajeAlerta;
    alertaGeneralDiv.classList.remove('d-none');
    if (hayNovedades) {
      audioAlerta.play(); // Sonido solo si hay algo nuevo
    }
  } else {
    alertaGeneralDiv.classList.add('d-none');
  }
}

// --- MODAL DE PEDIDOS PENDIENTES ---
async function verPedidosPendientes() {
  const listaPedidosDiv = document.getElementById('lista_pedidos_pendientes');
  listaPedidosDiv.innerHTML = '<p class="text-center text-muted"><i class="fas fa-spinner fa-spin"></i> Cargando pedidos...</p>';
  const modalPedidos = new bootstrap.Modal(document.getElementById('modalPedidos'));
  modalPedidos.show();

  const pedidos = await fetch('/api/pedidos/pendientes').then(r => r.json());
  if (pedidos.length === 0) {
    listaPedidosDiv.innerHTML = '<div class="alert alert-info text-center">No hay pedidos pendientes.</div>';
    return;
  }

  listaPedidosDiv.innerHTML = pedidos.map(p => `
        <div class="card mb-2 shadow-sm">
            <div class="card-body d-flex justify-content-between align-items-center">
                <div>
                    <h6 class="mb-0 fw-bold">${p.cliente}</h6>
                    <small class="text-muted">${p.items_count} productos - ${p.fecha}</small>
                </div>
                <button class="btn btn-sm btn-primary" onclick="cargarPedidoEnCarrito(${p.id})">
                    <i class="fas fa-cart-plus"></i> Cargar
                </button>
            </div>
        </div>
    `).join('');
}

// --- MODAL DE PAGOS REPORTADOS PENDIENTES ---
async function verPagosReportadosPendientes() {
  const listaPagosDiv = document.getElementById('lista_pagos_reportados_pendientes');
  listaPagosDiv.innerHTML = '<p class="text-center text-muted"><i class="fas fa-spinner fa-spin"></i> Cargando pagos...</p>';
  const modalPagos = new bootstrap.Modal(document.getElementById('modalPagosReportados'));
  modalPagos.show();

  const pagos = await fetch('/api/pagos_reportados/pendientes').then(r => r.json());
  if (pagos.length === 0) {
    listaPagosDiv.innerHTML = '<div class="alert alert-info text-center">No hay pagos reportados pendientes.</div>';
    return;
  }

  listaPagosDiv.innerHTML = pagos.map(p => `
        <div class="card mb-2 shadow-sm">
            <div class="card-body">
                <h6 class="mb-0 fw-bold">${p.cliente} - ${p.metodo_pago}</h6>
                <p class="mb-0">Monto: $${p.monto_usd.toFixed(2)} / Bs. ${p.monto_bs.toFixed(2)}</p>
                <small class="text-muted">Reportado: ${p.fecha_reporte}</small>
            </div>
        </div>
    `).join('');
}

// Ejecutar la revisión de alertas cada 1 minuto (60000 ms)
setInterval(actualizarAlertasPOS, 60000);
actualizarAlertasPOS(); // Ejecutar al cargar la página por primera vez