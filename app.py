import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import requests

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Quiniela Mundial 2026 - Operaciones", page_icon="⚽", layout="wide")
st.title("🏆 Quiniela Completa de Operaciones - Mundial 2026")
st.markdown("Registra y consulta tus pronósticos. Cierre automático **15 minutos antes** de cada juego.")

# 2. CARGAR PARTIDOS DESDE EXCEL
archivo_excel = "partidos.xlsx"

if not os.path.exists(archivo_excel):
    st.error(f"❌ No se encontró el archivo '{archivo_excel}' en el repositorio.")
    st.stop()

df_partidos = pd.read_excel(archivo_excel)
df_partidos['goles_l_real'] = df_partidos['goles_l_real'].astype(object).where(df_partidos['goles_l_real'].notnull(), None)
df_partidos['goles_v_real'] = df_partidos['goles_v_real'].astype(object).where(df_partidos['goles_v_real'].notnull(), None)

PARTIDOS = {}
for _, row in df_partidos.iterrows():
    PARTIDOS[int(row['id'])] = {
        "fase": row['fase'],
        "local": row['local'],
        "visita": row['visita'],
        "fecha_hora": str(row['fecha_hora']).strip(),
        "goles_l_real": row['goles_l_real'],
        "goles_v_real": row['goles_v_real']
    }

# 3. CONEXIÓN A LA BÓVEDA EN LA NUBE (JSONBin)
BIN_ID = st.secrets["BIN_ID"]
API_KEY = st.secrets["API_KEY"]
URL_BIN = f"https://api.jsonbin.io/v3/b/{BIN_ID}"

def cargar_pronosticos():
    headers = {"X-Master-Key": API_KEY}
    try:
        req = requests.get(URL_BIN, headers=headers)
        if req.status_code == 200:
            datos = req.json().get("record", {})
            datos_limpios = {}
            for usuario, predicciones in datos.items():
                datos_limpios[usuario] = {int(id_p): goles for id_p, goles in predicciones.items()}
            return datos_limpios
    except Exception as e:
        st.error("Error conectando a la base de datos.")
    return {}

def guardar_pronosticos(datos):
    headers = {
        "Content-Type": "application/json",
        "X-Master-Key": API_KEY
    }
    try:
        requests.put(URL_BIN, json=datos, headers=headers)
    except Exception as e:
        st.error("Error al guardar en la nube.")

# 4. CONTROL DE BASE DE DATOS
if "pronosticos" not in st.session_state:
    st.session_state.pronosticos = cargar_pronosticos()
if "usuarios" not in st.session_state:
    st.session_state.usuarios = list(st.session_state.pronosticos.keys())

hora_actual = datetime.utcnow() - timedelta(hours=6)
st.sidebar.markdown(f"**🕒 Hora actual:**\n`{hora_actual.strftime('%Y-%m-%d %H:%M:%S')}`")

# 5. PESTAÑAS DE LA APLICACIÓN
tab1, tab2, tab3 = st.tabs(["📝 Registrar / Consultar", "📊 Tabla de Posiciones", "⚙️ Vista de Datos (Admin)"])

# ==========================================
# PESTAÑA 1: REGISTRO Y CONSULTA DE PRONÓSTICOS
# ==========================================
with tab1:
    st.header("Introduce o Modifica tus Predicciones")
    st.info("💡 **Paso 1:** Escribe tu nombre y presiona **Enter** para cargar tu quiniela.")
    nombre_input = st.text_input("Tu Nombre Completo:", placeholder="Ej. ERICK PAIZ").strip().upper()
    st.divider()
    
    if nombre_input:
        fases_disponibles = sorted(list(set([info["fase"] for info in PARTIDOS.values()])))
        fase_seleccionada = st.selectbox("Filtrar por Grupo o Fase:", fases_disponibles)
        
        pronosticos_usuario = st.session_state.pronosticos.get(nombre_input, {})
        
        with st.form("form_pronosticos"):
            st.write(f"### Quiniela de {nombre_input} - {fase_seleccionada}")
            nuevos_pronosticos_temp = {}
            
            for id_partido, info in PARTIDOS.items():
                if info["fase"] != fase_seleccionada:
                    continue
                    
                hora_partido = datetime.strptime(info["fecha_hora"], "%Y-%m-%d %H:%M")
                hora_limite_cierre = hora_partido + timedelta(minutes=15)
                
                if hora_actual >= hora_limite_cierre:
                    deshabilitado = True
                    estado_texto = f"🔒 (Bloqueado)"
                else:
                    deshabilitado = False
                    estado_texto = f"🟢 (Abierto)"
                
                st.markdown(f"**Partido {id_partido}: {info['local']} vs {info['visita']}** | {estado_texto}")
                col1, col2 = st.columns(2)
                
                valores_previos = pronosticos_usuario.get(id_partido, (0, 0))
                
                with col1:
                    goles_l = st.number_input(f"Goles {info['local']}", min_value=0, max_value=15, value=int(valores_previos[0]), key=f"l_{id_partido}", disabled=deshabilitado)
                with col2:
                    goles_v = st.number_input(f"Goles {info['visita']}", min_value=0, max_value=15, value=int(valores_previos[1]), key=f"v_{id_partido}", disabled=deshabilitado)
                
                nuevos_pronosticos_temp[id_partido] = (goles_l, goles_v)
                st.markdown("---")
                
            boton_enviar = st.form_submit_button("Guardar / Actualizar Pronósticos")
            
        if boton_enviar:
            # 1. DESCARGAR VERSIÓN FRESCA DE LA NUBE AL INSTANTE
            datos_actualizados_nube = cargar_pronosticos()
            
            # 2. INYECTAR SOLO LOS DATOS DEL USUARIO ACTUAL
            if nombre_input not in datos_actualizados_nube:
                datos_actualizados_nube[nombre_input] = {}
                
            datos_actualizados_nube[nombre_input].update(nuevos_pronosticos_temp)
            
            # 3. SUBIR LA VERSIÓN CORRECTA A LA BÓVEDA
            guardar_pronosticos(datos_actualizados_nube)
            
            # 4. ACTUALIZAR MEMORIA LOCAL
            st.session_state.pronosticos = datos_actualizados_nube
            if nombre_input not in st.session_state.usuarios:
                st.session_state.usuarios.append(nombre_input)
                
            st.success(f"¡Pronósticos de {nombre_input} blindados y sincronizados sin errores!")
    else:
        st.warning("⚠️ Debes ingresar tu nombre arriba para poder ver y editar los partidos.")

# ==========================================
# PESTAÑA 2: TABLA DE POSICIONES
# ==========================================
with tab2:
    st.header("🏆 Ranking del Equipo de Operaciones")
    if not st.session_state.usuarios:
        st.info("Aún no hay participantes registrados.")
    else:
        tabla_puntos = []
        for usuario in st.session_state.usuarios:
            puntos_totales = 0
            pronosticos_usuario = st.session_state.pronosticos.get(usuario, {})
            
            for id_partido, info in PARTIDOS.items():
                hora_partido = datetime.strptime(info["fecha_hora"], "%Y-%m-%d %H:%M")
                if hora_actual >= hora_partido and info["goles_l_real"] is not None and not pd.isna(info["goles_l_real"]):
                    gl_real = int(info["goles_l_real"])
                    gv_real = int(info["goles_v_real"])
                    
                    if id_partido in pronosticos_usuario:
                        gl_pron, gv_pron = pronosticos_usuario[id_partido]
                        if gl_real == gl_pron and gv_real == gv_pron:
                            puntos_totales += 5
                        elif gl_real == gv_real and gl_pron == gv_pron:
                            puntos_totales += 3
                        elif gl_real > gv_real and gl_pron > gv_pron:
                            puntos_totales += 3
                        elif gl_real < gv_real and gl_pron < gv_pron:
                            puntos_totales += 3
            
            tabla_puntos.append({"Participante": usuario, "Puntos Totales": puntos_totales})
        
        df_leaderboard = pd.DataFrame(tabla_puntos).sort_values(by="Puntos Totales", ascending=False)
        df_leaderboard.reset_index(drop=True, inplace=True)
        df_leaderboard.index += 1
        st.table(df_leaderboard)

# ==========================================
# PESTAÑA 3: VISTA DE DATOS (ADMIN)
# ==========================================
with tab3:
    st.header("⚙️ Control de Datos de Excel")
    st.write("Lista de partidos actual:")
    st.dataframe(df_partidos)
