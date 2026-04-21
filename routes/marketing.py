import os
from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, Publicidad, QuejaSugerencia

marketing_bp = Blueprint('marketing', __name__, url_prefix='/gerencia/marketing')

ALLOWED_AD_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'mp4', 'mov', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AD_EXTENSIONS

@marketing_bp.route('/publicidad', methods=['GET', 'POST'])
@login_required
def admin_publicidad():
    if current_user.role not in ['admin', 'dueno']:
        flash('⛔ Acceso denegado', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        modo = request.form.get('modo')

        if modo == 'subir':
            archivos = request.files.getlist('archivos')
            titulo = request.form.get('titulo', 'Publicidad').strip()
            descripcion = request.form.get('descripcion', '').strip()
            
            carpeta_destino = os.path.join(current_app.root_path, 'static', 'publicidad')
            os.makedirs(carpeta_destino, exist_ok=True)
            
            exitos = 0
            for archivo in archivos:
                if archivo and archivo.filename:
                    if allowed_file(archivo.filename):
                        ext = archivo.filename.rsplit('.', 1)[1].lower()
                        nombre_seguro = secure_filename(f"ad_{int(datetime.now().timestamp())}_{archivo.filename}")
                        ruta_archivo = os.path.join(carpeta_destino, nombre_seguro)
                        archivo.save(ruta_archivo)
                        
                        tipo_media = 'video' if ext in ['mp4', 'mov', 'webm'] else 'imagen'
                        
                        nueva_publi = Publicidad(
                            titulo=titulo,
                            descripcion=descripcion,
                            archivo_url=nombre_seguro,
                            tipo=tipo_media,
                            activo=True
                        )
                        db.session.add(nueva_publi)
                        exitos += 1
            
            if exitos > 0:
                db.session.commit()
                flash(f'✅ Se subieron {exitos} archivos correctamente.', 'success')
            else:
                flash('⚠️ No se subió ningún archivo válido (se aceptan fotos o videos).', 'warning')
                
        elif modo == 'cambiar_estado':
            publi_id = request.form.get('publi_id')
            publi = Publicidad.query.get(publi_id)
            if publi:
                publi.activo = not publi.activo
                db.session.commit()
                flash('✅ Se cambió el estado de la publicidad.', 'success')

        elif modo == 'eliminar':
            publi_id = request.form.get('publi_id')
            publi = Publicidad.query.get(publi_id)
            if publi:
                try: # Opcional: borrar el archivo fisico
                    ruta = os.path.join(current_app.root_path, 'static', 'publicidad', publi.archivo_url)
                    if os.path.exists(ruta):
                        os.remove(ruta)
                except:
                    pass
                db.session.delete(publi)
                db.session.commit()
                flash('🗑️ Publicidad eliminada.', 'success')

        return redirect(url_for('marketing.admin_publicidad'))

    anuncios = Publicidad.query.order_by(Publicidad.fecha_creacion.desc()).all()
    return render_template('marketing/admin_publicidad.html', anuncios=anuncios)


@marketing_bp.route('/quejas', methods=['GET', 'POST'])
@login_required
def admin_quejas():
    if current_user.role not in ['admin', 'dueno']:
        flash('⛔ Acceso denegado', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        queja_id = request.form.get('queja_id')
        queja = QuejaSugerencia.query.get(queja_id)
        if queja:
            queja.leido = True
            db.session.commit()
            flash('✅ Queja/Sugerencia marcada como leída.', 'success')
            return redirect(url_for('marketing.admin_quejas'))

    quejas = QuejaSugerencia.query.order_by(QuejaSugerencia.fecha.desc()).all()
    return render_template('marketing/admin_quejas.html', quejas=quejas)
