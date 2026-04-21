# Plan de migración segura Alembic

1. Mover alembic.ini a la raíz del proyecto.
2. Verificar que script_location = migrations esté en la sección [alembic].
3. Ejecutar migración desde la raíz.
4. Verificar que no se afectan otras tablas ni datos.
5. Aplicar migración.
6. Confirmar que la columna pago_debito_bs aparece en la tabla ventas.

Este procedimiento es seguro y estándar para proyectos Flask/Alembic.