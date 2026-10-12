# Diseno de ventas_app

- **SRP**: `validator.validar_ventas` solo valida y separa filas; `loader` lee,
  `metrics` agrega y `cli` coordina y exporta.
- **OCP**: se pueden agregar funciones a `metrics.py` sin cambiar la carga ni
  las reglas del validador.
- **DIP**: `cli.main` usa el contrato `SalesRepository`. `CsvSalesRepository`
  implementa la lectura concreta. Es el patron Protocol del ejemplo de clase
  `1_programacion_avanzada_python/03_oop_clean_code_solid.py`.
