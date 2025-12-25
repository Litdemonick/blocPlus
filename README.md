# Transparent Notepad (Python)

Bloc de notas con ventana transparente (opacidad), múltiples notas, estilos por nota, ordenamiento y recordatorios con notificaciones en Windows.
Incluye export/import de todo a un archivo `.bplus` para no perder tu información.

## Features
- ✅ Múltiples notas (crear/eliminar/duplicar)
- ✅ Guardado persistente en SQLite
- ✅ Ordenamiento (mover arriba/abajo) y ordenar por título o fecha
- ✅ Estilos por nota: color de texto, color de fondo, fuente y tamaño
- ✅ Transparencia de ventana (slider)
- ✅ "Siempre arriba" (Topmost)
- ✅ Recordatorios: fecha/hora + aviso X días antes (configurable) + notificación Windows
- ✅ Exportar/Importar backup `.bplus` (ZIP con JSON)

## Requisitos
- Python 3.10+ (recomendado)
- Windows para notificaciones (toast)

## Instalación
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py

Backup

Exportar crea un archivo *.bplus

Importar restaura TODO (reemplaza lo existente)