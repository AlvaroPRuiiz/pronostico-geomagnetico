# Entorno y kernel de DSIA

El entorno local esta en `.venv-dsia` y utiliza Python 3.12.

En VS Code, abre un notebook y selecciona **Seleccionar kernel > Entornos de Python > .venv-dsia** (o **Python (Desarrollo de Soluciones de IA)** en la lista de kernels de Jupyter).

Para abrir JupyterLab desde PowerShell en esta carpeta:

```powershell
.\.venv-dsia\Scripts\python.exe -m jupyterlab
```

Para instalar de nuevo las dependencias:

```powershell
py -3.12 -m venv .venv-dsia
.\.venv-dsia\Scripts\python.exe -m pip install -r requirements-dsia.txt
.\.venv-dsia\Scripts\python.exe scripts/configurar_kernel_dsia.py
```

Incluye las dependencias del proyecto, JupyterLab, Notebook, ipykernel, NumPy, SciPy, Matplotlib, Seaborn, scikit-learn, requests y openpyxl.

El kernel configurado para este proyecto abre las sesiones en la raiz del repositorio, para que funcionen los imports de `src` y las rutas `data/...`.

`notebooks/pruebas.ipynb` contiene celdas de experimentacion que provocan errores intencionados y otras con imports o nombres que necesitan correccion. Disponer del kernel no corrige esas celdas.

