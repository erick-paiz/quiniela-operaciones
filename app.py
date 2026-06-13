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

# 3. CONEXIÓN A LAS BÓVEDAS EN LA NUBE (JSONBin)
BIN_ID = st.secrets["BIN_ID"]
API_KEY = st.secrets["API_KEY"]
BIN_ID_PASSWORDS = st.secrets["BIN_ID_PASSWORDS"]

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

# 4. CONTROL DE TIEMPO
hora_actual = datetime.utcnow() - timedelta(hours=6)
st.sidebar.markdown(f"**🕒 Hora actual:**\n`{hora_actual.strftime('%Y-%m-%d %H:%M:%S')}`")

# 5. PESTAÑAS DE LA APLICACIÓN
tab1, tab2, tab3 = st.tabs(["📝 Registrar / Consultar", "📊 Tabla de Posiciones", "⚙️ Vista de Datos (Admin)"])

# ==========================================
# PESTAÑA 1: REGISTRO Y CONSULTA DE PRONÓSTICOS
# ==========================================
with tab1:
    st.header("Acceso Seguro a la Quiniela")
    
    col1, col2 = st.columns(2)
    with col1:
        nombre_input = st.text_input("Tu Nombre Completo (Ej. ERICK PAIZ):").strip().upper()
    with col2:
        clave_input = st.text_input("Tu Clave de Acceso:", type="password").strip()
    st.divider()
    
    if nombre_input and clave_input:
        # Autenticación en tiempo real
        credenciales = cargar_datos(URL_PASS)
        acceso_permitido = False
        
        if nombre_input in credenciales:
            if credenciales[nombre_input] == clave_input:
                acceso_permitido = True
            else:
                st.error("❌ Clave incorrecta. Revisa el mensaje que te enviaron o contacta al administrador.")
        else:
            # Registrar nuevo usuario
            credenciales[nombre_input] = clave_input
            guardar_datos(URL_PASS, credenciales)
            acceso_permitido = True
            st.success(f"✅ ¡Nuevo usuario registrado! Tu clave ha sido guardada.")

        if acceso_permitido:
            # Cargar pronósticos solo si el acceso fue exitoso
            pronosticos_globales = cargar_datos(URL_BIN)
            # Limpiar llaves a enteros
            datos_limpios = {}
            for usuario, predicciones in pronosticos_globales.items():
                datos_limpios[usuario] = {int(id_p): goles for id_p, goles in predicciones.items()}
            
            fases_disponibles = sorted(list(set([info["fase"] for info in PARTIDOS.values()])))
            fase_seleccionada = st.selectbox("Filtrar por Grupo o Fase:", fases_disponibles)
            
            pronosticos_usuario = datos_limpios.get(nombre_input, {})
            
            with st.form("form_pronosticos"):
                st.write(f"### Quiniela de {nombre_input} - {fase_seleccionada}")
                nuevos_pronosticos_temp = {}
                
                for id_partido, info in PARTIDOS.items():
                    if info["fase"] != fase_seleccionada:
                        continue
                        
                    hora_partido = datetime.strptime(info["fecha_hora"], "%Y-%m-%d %H:%M")
                    hora_limite_cierre = hora_partido + timedelta(minutes=45)
                    
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
                # REGLA DE ARQUITECTURA: Leer antes de escribir para evitar sobrescrituras
                datos_frescos_nube = cargar_datos(URL_BIN)
                datos_limpios_frescos = {}
                for usuario, predicciones in datos_frescos_nube.items():
                    datos_limpios_frescos[usuario] = {int(id_p): goles for id_p, goles in predicciones.items()}
                
                if nombre_input not in datos_limpios_frescos:
                    datos_limpios_frescos[nombre_input] = {}
                    
                datos_limpios_frescos[nombre_input].update(nuevos_pronosticos_temp)
                guardar_datos(URL_BIN, datos_limpios_frescos)
                
                st.success(f"¡Pronósticos blindados y sincronizados de forma segura!")

# ==========================================
# PESTAÑA 2: TABLA DE POSICIONES
# ==========================================
with tab2:
    st.header("🏆 Ranking del Equipo de Operaciones")
    pronosticos_globales = cargar_datos(URL_BIN)
    
    if not pronosticos_globales:
        st.info("Aún no hay participantes registrados.")
    else:
        tabla_puntos = []
        for usuario, predicciones in pronosticos_globales.items():
            puntos_totales = 0
            predicciones_limpias = {int(id_p): goles for id_p, goles in predicciones.items()}
            
            for id_partido, info in PARTIDOS.items():
                hora_partido = datetime.strptime(info["fecha_hora"], "%Y-%m-%d %H:%M")
                if hora_actual >= hora_partido and info["goles_l_real"] is not None and not pd.isna(info["goles_l_real"]):
                    gl_real = int(info["goles_l_real"])
                    gv_real = int(info["goles_v_real"])
                    
                    if id_partido in predicciones_limpias:
                        gl_pron, gv_pron = predicciones_limpias[id_partido]
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
