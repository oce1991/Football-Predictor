# ⚽ Predictor de Apuestas DC+EV

Predictor profesional de apuestas de fútbol con modelo Dixon-Coles, EV para todos los mercados, Kelly Criterion, cuotas en vivo y actualización automática diaria.

## 🚀 Instalación en 5 minutos

### 1. Crear repositorio en GitHub
1. Ve a [github.com](https://github.com) → **New repository**
2. Nombre: `predictor-futbol`
3. Visibilidad: **Public** (necesario para Netlify gratis)
4. Pulsa **Create repository**

### 2. Subir los archivos
Sube todos estos archivos al repositorio:
- `generate_data.py`
- `build_app.py`
- `template.html`
- `data.json`
- `manifest.json`
- `sw.js`
- `netlify.toml`
- `.github/workflows/update.yml`

### 3. Conectar con Netlify
1. Ve a [netlify.com](https://netlify.com) → **Add new site**
2. Selecciona **Import from Git** → GitHub
3. Selecciona tu repositorio `predictor-futbol`
4. Build command: (vacío)
5. Publish directory: `.`
6. Pulsa **Deploy**

¡Tu app ya está en línea en `https://tuusuario.netlify.app`!

### 4. Activar actualización automática
El archivo `.github/workflows/update.yml` ya está configurado para ejecutarse cada día a las 00:05 UTC.

GitHub Actions descargará automáticamente el xlsx de football-data.co.uk, regenerará `data.json` e `index.html`, y hará push al repositorio. Netlify detectará el cambio y redesplegarará la app automáticamente.

**No necesitas hacer nada más.** Cada mañana la app tendrá los datos del día anterior.

### 5. Instalar en el móvil
1. Abre la URL de Netlify en Chrome (Android) o Safari (iOS)
2. Chrome: menú ⋮ → **Añadir a pantalla de inicio**
3. Safari: botón compartir → **Añadir a pantalla de inicio**

## 📱 Funcionalidades

- **Modelo Dixon-Coles** con ρ calibrado en datos reales
- **xG proxy** para lambdas más estables
- **EV para todos los mercados**: 1X2, Over/Under, BTTS, corners, tarjetas
- **EV por tiempos**: primer tiempo y segundo tiempo por separado
- **Hándicap Asiático** con soporte de líneas de cuarto
- **Cuotas en vivo** via The Odds API (500 peticiones/mes gratis)
- **Monte Carlo** (10.000 simulaciones)
- **Head to Head** histórico
- **Racha de forma** visual (G/E/P)
- **Patrones de gol**: marca primero, portería a cero, remontadas...
- **Alertas automáticas** de valor al predecir
- **Comparador** de dos partidos
- **Historial de apuestas** con yield, ROI, stats por mercado
- **Exportar CSV** del historial
- **Clasificaciones** en tiempo real de 16 ligas

## 🔄 Actualización manual
Si quieres actualizar los datos manualmente sin esperar a las 00:05:
1. Ve a tu repositorio en GitHub
2. **Actions** → **Actualizar datos diariamente** → **Run workflow**

## ⚙️ Configuración

### Cambiar temporada
Edita `generate_data.py`, línea:
```python
DATA_URL = "https://www.football-data.co.uk/mmz4281/2526/all-euro-data-2025-2026.xlsx"
```
Cambia `2526` por la temporada correspondiente.

### Añadir más ligas
En `generate_data.py`, añade a `SHEET_MAP`:
```python
'T1': 'Süper Lig',
'G1': 'Super League Greece',
```

## 📊 Datos
Fuente: [football-data.co.uk](https://www.football-data.co.uk) — datos gratuitos de resultados y estadísticas de las principales ligas europeas.
