import os
from app import app
from models import db, Producto, Venta, DetalleVenta, Cliente, MovimientoCaja, CierreCaja, Asiento, DetalleAsiento, Proveedor, MovimientoProductor, PagoProductor, HistorialPago, Pedido, DetallePedido, PagoReportado, AuditoriaInventario, Compra, CompraDetalle, CuentaPorPagar, AbonoCuentaPorPagar

def limpiar_base_de_datos():
    with app.app_context():
        print("🧹 Iniciando limpieza completa de la base de datos...")
        
        # Lista de tablas a limpiar (excepto User para no perder el acceso admin)
        tablas = [
            DetalleVenta, Venta, DetallePedido, Pedido, 
            DetalleAsiento, Asiento, MovimientoCaja, CierreCaja,
            AbonoCuentaPorPagar, CuentaPorPagar, CompraDetalle, Compra,
            MovimientoProductor, PagoProductor, HistorialPago, PagoReportado,
            AuditoriaInventario, Producto, Cliente, Proveedor
        ]
        
        try:
            for tabla in tablas:
                db.session.query(tabla).delete()
            
            db.session.commit()
            print("✨ ¡Base de datos limpia! Se han borrado ventas, inventario, clientes y proveedores.")
            print("🔒 Los usuarios se mantienen intactos (incluyendo el Admin y Cajeros).")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error al limpiar: {str(e)}")

if __name__ == "__main__":
    limpiar_base_de_datos()
