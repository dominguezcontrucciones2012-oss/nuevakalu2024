from app import app
from models import db, CuentaContable

def cargar_base_contable():
    with app.app_context():
        # Definición del Plan de Cuentas (Estructura Venezolana)
        cuentas = [
            # CODIGO, NOMBRE, TIPO, NATURALEZA, ES_DETALLE
            ('1', 'ACTIVO', 'Activo', 'Deudora', False),
            ('1.1', 'ACTIVO CORRIENTE', 'Activo', 'Deudora', False),
            ('1.1.01', 'CAJA Y BANCOS', 'Activo', 'Deudora', False),
            ('1.1.01.01', 'CAJA PRINCIPAL (USD)', 'Activo', 'Deudora', True),
            ('1.1.01.02', 'CAJA PRINCIPAL (BS)', 'Activo', 'Deudora', True),
            ('1.1.02', 'CUENTAS POR COBRAR', 'Activo', 'Deudora', False),
            ('1.1.02.01', 'CLIENTES (FIADO)', 'Activo', 'Deudora', True),
            ('1.1.03', 'INVENTARIOS', 'Activo', 'Deudora', False),
            ('1.1.03.01', 'MERCANCIA PARA LA VENTA', 'Activo', 'Deudora', True),
            
            ('4', 'INGRESOS', 'Ingreso', 'Acreedora', False),
            ('4.1', 'VENTAS', 'Ingreso', 'Acreedora', False),
            ('4.1.01', 'VENTAS DE MERCANCIA', 'Ingreso', 'Acreedora', True),
            
            ('5', 'EGRESOS', 'Egreso', 'Deudora', False),
            ('5.1', 'COSTOS DE VENTAS', 'Egreso', 'Deudora', False),
            ('5.1.01', 'COSTO DE MERCANCIA VENDIDA', 'Egreso', 'Deudora', True),
        ]

        print("⏳ Cargando Plan de Cuentas...")
        for cod, nom, tipo, nat, detalle in cuentas:
            existe = CuentaContable.query.filter_by(codigo=cod).first()
            if not existe:
                nueva = CuentaContable(
                    codigo=cod, 
                    nombre=nom, 
                    tipo=tipo, 
                    naturaleza=nat, 
                    es_detalle=detalle
                )
                db.session.add(nueva)
        
        db.session.commit()
        print("✅ PLAN DE CUENTAS CARGADO EXITOSAMENTE")

if __name__ == '__main__':
    cargar_base_contable()