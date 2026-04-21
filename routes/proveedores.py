from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from routes.decorators import staff_required
from decimal import Decimal
from datetime import datetime
from models import db, Proveedor, CuentaPorPagar, AbonoCuentaPorPagar, MovimientoCaja, TasaBCV
from utils import seguro_decimal
from routes.usuarios import crear_acceso_sistema
import logging

proveedores_bp = Blueprint('proveedores', __name__)
logger = logging.getLogger('KALU.proveedores')

# ========== LISTA DE PROVEEDORES ==========
@proveedores_bp.route('/proveedores')
@login_required
@staff_required
def lista_proveedores():
    todos = Proveedor.query.all()
    return render_template('proveedores.html', proveedores=todos)

# ========== GUARDAR PROVEEDOR ==========
@proveedores_bp.route('/guardar_proveedor', methods=['POST'])
@login_required
@staff_required
def guardar_proveedor():
    try:
        nombre = request.form.get('nombre')
        rif = request.form.get('rif')
        
        if not nombre or not rif:
            flash("Nombre y RIF son obligatorios", "danger")
            return redirect(url_for('proveedores.lista_proveedores'))
            
        nuevo = Proveedor(
            nombre=nombre,
            rif=rif,
            telefono=request.form.get('telefono'),
            direccion=request.form.get('direccion'),
            vendedor_nombre=request.form.get('vendedor_nombre'),
            vendedor_telefono=request.form.get('vendedor_telefono'),
            es_productor=True if request.form.get('es_productor') else False,
            es_obrero=True if request.form.get('es_obrero') else False
        )
        db.session.add(nuevo)
        db.session.flush() # Obtener ID para el enlace de usuario
        
        # Generar acceso automático si es productor
        if nuevo.es_productor:
            crear_acceso_sistema(nuevo, 'productor')

        db.session.commit()
        flash("✅ Proveedor y Acceso al Portal guardado con éxito", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al guardar: {str(e)}", "danger")
    return redirect(url_for('proveedores.lista_proveedores'))

# ========== EDITAR PROVEEDOR ==========
@proveedores_bp.route('/editar_proveedor/<int:id>', methods=['POST'])
@login_required
@staff_required
def editar_proveedor(id):
    try:
        prov = Proveedor.query.get_or_404(id)
        prov.rif               = request.form.get('rif')
        prov.nombre            = request.form.get('nombre')
        prov.telefono          = request.form.get('telefono')
        prov.direccion         = request.form.get('direccion')
        prov.vendedor_nombre   = request.form.get('vendedor_nombre')
        prov.vendedor_telefono = request.form.get('vendedor_telefono')
        prov.es_productor      = True if request.form.get('es_productor') else False
        prov.es_obrero         = True if request.form.get('es_obrero') else False
        db.session.commit()
        flash("✅ Proveedor actualizado con éxito", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al editar: {str(e)}", "danger")
    return redirect(url_for('proveedores.lista_proveedores'))

# ========== ELIMINAR PROVEEDOR ==========
@proveedores_bp.route('/eliminar_proveedor/<int:id>', methods=['POST'])
@login_required
@staff_required
def eliminar_proveedor(id):
    try:
        prov = Proveedor.query.get_or_404(id)
        db.session.delete(prov)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# Nota: Se eliminó lista_cuentas_por_pagar para usar la de compras_bp (compras.py) 
# que maneja correctamente la tasa de cambio y el flujo premium.

# Nota: Se eliminó pagar_factura de este blueprint para centralizar en compras_bp.abonar_pago 
# (AJAX) que registra correctamente en caja y contabilidad.

# ========== HISTORIAL DE PAGOS A PROVEEDORES ==========
@proveedores_bp.route('/historial_pagos_proveedores')
@login_required
@staff_required
def historial_pagos_proveedores():
    pagos = AbonoCuentaPorPagar.query.order_by(
        AbonoCuentaPorPagar.fecha.desc()
    ).all()
    return render_template('historial_pagos_proveedores.html', pagos=pagos)