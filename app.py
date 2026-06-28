import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import requests

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Fase Final - Operaciones 2026", page_icon="🏆", layout="wide")
st.title("🏆 Quiniela Fase Final - Mundial 2026")
st.markdown("Reglas: El marcador válido es el de **90 minutos + Tiempos Extra**. Los penales NO cuentan para el marcador exacto (se considera Empate). Cierre automático 15 min antes del juego.")

# 2. CARGAR PARTIDOS (ELIMINATORIAS)
archivo_excel = "eliminatorias.xlsx"

if not os.path.exists(archivo_excel):
    st.error(f"❌ No se encontró el archivo '{archivo_excel}'.")
    st.stop()

df_partidos = pd.read_excel(archivo_excel)
df_partidos['goles_l_real'] = df_partidos['goles_l_real'].astype(object).where(df_partidos['goles_l_real'].notnull(), None)
df_partidos['goles_v_real'] = df_partidos['goles_v_real'].astype(object).where(df_partidos['goles_v_real'].notnull(), None)

PARTIDOS = {}
for _, row in df_partidos.iterrows():
    PARTIDOS[int(row['id'])] = {
    "fase": str(row['fase']).strip(),
    "local": str(row['local']).strip(),
    "visita": str(row['visita']).strip(),
    "fecha_hora": str(row['fecha_hora']).strip()[:16], 
    "goles_l_real": row['goles_l_real'],
    "goles_v_real": row['goles_v_real']
}

# 3. CONEXIÓN A LAS BÓVEDAS
BIN_ID = st.secrets["BIN_ID_ELIMINATORIAS"]
BIN_ID_PASSWORDS = st.secrets["BIN_ID_PASSWORDS"]
API_KEY = st.secrets["API_KEY"]

URL_BIN = f"https://api.jsonbin.io/v3/b/{BIN_ID}"
URL_PASS = f"https://api.jsonbin.io/v3/b/{BIN_ID_PASSWORDS}"

def cargar_datos(url):
    headers = {"X-Master-Key": API_KEY}
    try:
        req = requests.get(url, headers=headers)
        if req.status_code == 200:
            return req.json().get("record", {})
    except:
        return {}
    return {}

def guardar_datos(url, datos):
    headers = {"Content-Type": "application/json", "X-Master-Key": API_KEY}
    try:
        requests.put(url, json=datos, headers=headers)
    except:
        pass

# 4. CONTROL DE TIEMPO (Hora Central CST)
hora_actual = datetime.utcnow() - timedelta(hours=6)
st.sidebar.markdown(f"**🕒 Hora actual:**\n`{hora_actual.strftime('%Y-%m-%d %H:%M:%S')}`")

# 5. INTERFAZ Y PESTAÑAS
tab1, tab2, tab3 = st.tabs(["📝 Ingresar Pronósticos", "🏆 Ranking Eliminatorias", "⚙️ Admin"])

with tab1:
    st.header("Acceso de Usuario")
    
    col1, col2 = st.columns(2)
    with col1:
        nombre_input = st.text_input("Nombre (Ej. ERICK PAIZ):").strip().upper()
    with col2:
        clave_input = st.text_input("Clave Secreta:", type="password").strip()
    st.divider()
    
    if nombre_input and clave_input:
        credenciales = cargar_datos(URL_PASS)
        acceso_permitido = False
        
        if nombre_input in credenciales:
            if credenciales[nombre_input] == clave_input:
                acceso_permitido = True
            else:
                st.error("❌ Clave incorrecta.")
        else:
            st.error("❌ Usuario no registrado. Contacta al administrador para obtener tu clave de la Fase Final.")

        if acceso_permitido:
            pronosticos_globales = cargar_datos(URL_BIN)
            datos_limpios = {u: {int(i): g for i, g in p.items()} for u, p in pronosticos_globales.items()}
            
            # Filtro de fases
            fases_disponibles = []
            for info in PARTIDOS.values():
                if info["fase"] not in fases_disponibles:
                    fases_disponibles.append(info["fase"])
            
            fase_seleccionada = st.selectbox("Selecciona la Llave:", fases_disponibles)
            pronosticos_usuario = datos_limpios.get(nombre_input, {})
            
            with st.form("form_pronosticos"):
                st.write(f"### Pronósticos de {nombre_input} - {fase_seleccionada}")
                nuevos_pronosticos_temp = {}
                partidos_mostrados = 0
                
                for id_partido, info in PARTIDOS.items():
                    if info["fase"] != fase_seleccionada:
                        continue
                        
                    # Lógica Modelo B: Bloquear si los equipos aún no se definen
                    equipos_tbd = "Ganador" in info['local'] or "Por definir" in info['local']
                    
                    if equipos_tbd:
                        st.info(f"⏳ **Partido {id_partido}: {info['local']} vs {info['visita']}** | Esperando resultados anteriores para abrir pronósticos.")
                        st.markdown("---")
                        continue
                    
                    partidos_mostrados += 1
                    hora_partido = datetime.strptime(info["fecha_hora"], "%Y-%m-%d %H:%M")
                    hora_limite = hora_partido + timedelta(minutes=2000)
                    
                    if hora_actual >= hora_limite:
                        deshabilitado = True
                        estado = "🔒 (Cerrado)"
                    else:
                        deshabilitado = False
                        estado = "🟢 (Abierto)"
                    
                    st.markdown(f"**Partido {id_partido}: {info['local']} vs {info['visita']}** | {estado}")
                    col1, col2 = st.columns(2)
                    
                    valores_previos = pronosticos_usuario.get(id_partido, (0, 0))
                    
                    with col1:
                        goles_l = st.number_input(f"Goles {info['local']}", min_value=0, max_value=15, value=int(valores_previos[0]), key=f"l_{id_partido}", disabled=deshabilitado)
                    with col2:
                        goles_v = st.number_input(f"Goles {info['visita']}", min_value=0, max_value=15, value=int(valores_previos[1]), key=f"v_{id_partido}", disabled=deshabilitado)
                    
                    nuevos_pronosticos_temp[id_partido] = (goles_l, goles_v)
                    st.markdown("---")
                
                if partidos_mostrados > 0:
                    boton_enviar = st.form_submit_button("Guardar Pronósticos (120 Minutos)")
                else:
                    st.warning("No hay partidos definidos para pronosticar en esta fase aún.")
                    boton_enviar = False
                
            if boton_enviar:
                # PROTOCOLO ANTI-CONGELAMIENTO (Leer antes de escribir)
                datos_frescos = cargar_datos(URL_BIN)
                datos_limpios_frescos = {u: {int(i): g for i, g in p.items()} for u, p in datos_frescos.items()}
                
                if nombre_input not in datos_limpios_frescos:
                    datos_limpios_frescos[nombre_input] = {}
                    
                datos_limpios_frescos[nombre_input].update(nuevos_pronosticos_temp)
                guardar_datos(URL_BIN, datos_limpios_frescos)
                
                st.success(f"✅ ¡Pronósticos blindados en la nube!")

with tab2:
    st.header("🏆 Ranking de la Fase Final")
    st.markdown("*Puntos: 5 por marcador exacto (120 min), 3 por atinar al clasificado/empate.*")
    pronosticos_globales = cargar_datos(URL_BIN)
    
    if not pronosticos_globales:
        st.info("Aún no hay puntos registrados en esta fase.")
    else:
        tabla_puntos = []
        for usuario, predicciones in pronosticos_globales.items():
            puntos = 0
            pred_limpias = {int(i): g for i, g in predicciones.items()}
            
            for id_partido, info in PARTIDOS.items():
                if info["goles_l_real"] is not None and not pd.isna(info["goles_l_real"]):
                    gl_real = int(info["goles_l_real"])
                    gv_real = int(info["goles_v_real"])
                    
                    if id_partido in pred_limpias:
                        gl_pron, gv_pron = pred_limpias[id_partido]
                        
                        if gl_real == gl_pron and gv_real == gv_pron:
                            puntos += 5
                        elif (gl_real == gv_real) and (gl_pron == gv_pron):
                            puntos += 3
                        elif (gl_real > gv_real) and (gl_pron > gv_pron):
                            puntos += 3
                        elif (gl_real < gv_real) and (gl_pron < gv_pron):
                            puntos += 3
            
            tabla_puntos.append({"Participante": usuario, "Puntos Fase Final": puntos})
        
        df_leaderboard = pd.DataFrame(tabla_puntos).sort_values(by="Puntos Fase Final", ascending=False)
        df_leaderboard.reset_index(drop=True, inplace=True)
        df_leaderboard.index += 1
        st.table(df_leaderboard)

with tab3:
    st.header("⚙️ Control de Administrador")
    st.dataframe(df_partidos)
