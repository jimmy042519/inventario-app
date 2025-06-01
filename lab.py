import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import base64
import time
import sqlite3
import os
from pathlib import Path

# ---------------------------
# CONFIGURACIÓN INICIAL
# ---------------------------

# Configuración de rutas seguras
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "data" / "inventario.db"  # Guardar en subdirectorio 'data'

# Crear directorio si no existe
os.makedirs(BASE_DIR / "data", exist_ok=True)

# Configuración de la página
st.set_page_config(
    page_title="📦 Sistema de Inventario Avanzado",
    page_icon="📊",
    layout="wide"
)

# Columnas requeridas
COLUMNAS_REQUERIDAS = ["ID", "Producto", "Categoría", "Cantidad", "Precio", "Ubicación"]

# ---------------------------
# FUNCIONES DEL SISTEMA
# ---------------------------

def inicializar_base_datos():
    """Inicializa la base de datos y crea la tabla si no existe"""
    conn = None
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Crear tabla con restricciones adecuadas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventario (
                ID TEXT PRIMARY KEY,
                Producto TEXT NOT NULL,
                Categoría TEXT NOT NULL,
                Cantidad INTEGER DEFAULT 0 CHECK(Cantidad >= 0),
                Precio REAL DEFAULT 0.0 CHECK(Precio >= 0),
                Ubicación TEXT,
                UNIQUE(ID)
            )
        """)
        
        # Crear índice para búsquedas frecuentes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_producto ON inventario(Producto)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_categoria ON inventario(Categoría)")
        
        conn.commit()
    except Exception as e:
        st.error(f"Error al inicializar la base de datos: {str(e)}")
        st.stop()  # Detener la ejecución si no podemos inicializar la DB
    finally:
        if conn:
            conn.close()

def cargar_datos_desde_db():
    """Carga los datos desde la base de datos SQLite"""
    conn = None
    try:
        conn = sqlite3.connect(str(DB_PATH))
        df = pd.read_sql_query("SELECT * FROM inventario ORDER BY Producto", conn)
        return completar_columnas(df)
    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")
        return pd.DataFrame(columns=COLUMNAS_REQUERIDAS)
    finally:
        if conn:
            conn.close()

def guardar_datos_en_db(df):
    """Guarda el DataFrame en la base de datos"""
    conn = None
    try:
        # Validaciones previas
        if df.empty:
            st.warning("No hay datos para guardar")
            return False
            
        if not all(col in df.columns for col in COLUMNAS_REQUERIDAS):
            st.error("Faltan columnas requeridas en los datos")
            return False
            
        # Convertir y validar tipos de datos
        df = df.copy()
        df["Cantidad"] = pd.to_numeric(df["Cantidad"], errors="coerce").fillna(0).astype(int)
        df["Precio"] = pd.to_numeric(df["Precio"], errors="coerce").fillna(0.0).astype(float)
        
        # Validar valores negativos
        if (df["Cantidad"] < 0).any():
            st.error("Las cantidades no pueden ser negativas")
            return False
            
        if (df["Precio"] < 0).any():
            st.error("Los precios no pueden ser negativos")
            return False
            
        conn = sqlite3.connect(str(DB_PATH))
        
        # Usar transacción para mayor seguridad
        with conn:
            conn.execute("DELETE FROM inventario")
            df.to_sql("inventario", conn, if_exists="append", index=False)
            
        st.success("Datos guardados correctamente en la base de datos")
        return True
    except sqlite3.IntegrityError as e:
        st.error(f"Error de integridad en la base de datos: {str(e)}")
        return False
    except Exception as e:
        st.error(f"Error al guardar datos: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def estandarizar_columnas(df):
    """Estandariza los nombres de las columnas"""
    try:
        # Mapeo de nombres alternativos
        mapeo_columnas = {
            'Categoria': 'Categoría',
            'Cant': 'Cantidad',
            'Precio Unitario': 'Precio',
            'Locacion': 'Ubicación'
        }
        
        df.columns = [col.strip().capitalize() for col in df.columns]
        df = df.rename(columns=mapeo_columnas)
        return df
    except Exception as e:
        st.error(f"Error al estandarizar columnas: {str(e)}")
        return df

def completar_columnas(df):
    """Asegura que el DataFrame tenga todas las columnas requeridas"""
    try:
        for col in COLUMNAS_REQUERIDAS:
            if col not in df.columns:
                df[col] = "" if col in ["ID", "Producto", "Categoría", "Ubicación"] else 0
        return df[COLUMNAS_REQUERIDAS]
    except Exception as e:
        st.error(f"Error al completar columnas: {str(e)}")
        return pd.DataFrame(columns=COLUMNAS_REQUERIDAS)

def guardar_inventario_excel(df):
    """Genera un archivo Excel en memoria"""
    try:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Inventario')
            
            # Formatear el archivo Excel
            workbook = writer.book
            worksheet = writer.sheets['Inventario']
            
            # Formato para moneda
            money_format = workbook.add_format({'num_format': '$#,##0.00'})
            
            # Aplicar formatos
            worksheet.set_column('A:A', 15)  # ID
            worksheet.set_column('B:B', 30)  # Producto
            worksheet.set_column('C:C', 20)  # Categoría
            worksheet.set_column('D:D', 10)  # Cantidad
            worksheet.set_column('E:E', 12, money_format)  # Precio
            worksheet.set_column('F:F', 15)  # Ubicación
            
        return output.getvalue()
    except Exception as e:
        st.error(f"Error al generar Excel: {str(e)}")
        return None

def generar_pdf(df):
    """Genera un reporte PDF en memoria"""
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        
        # Título
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "Reporte de Inventario", 0, 1, 'C')
        pdf.ln(10)
        
        # Configuración de columnas
        page_width = pdf.w - 2 * pdf.l_margin
        col_widths = [
            page_width * 0.15,  # ID
            page_width * 0.25,  # Producto
            page_width * 0.15,  # Categoría
            page_width * 0.1,   # Cantidad
            page_width * 0.15,  # Precio
            page_width * 0.2    # Ubicación
        ]
        
        # Encabezados
        pdf.set_font("Arial", 'B', 10)
        headers = ["ID", "Producto", "Categoría", "Cantidad", "Precio", "Ubicación"]
        for header, width in zip(headers, col_widths):
            pdf.cell(width, 10, header, border=1, align='C')
        pdf.ln()
        
        # Datos
        pdf.set_font("Arial", size=8)
        for _, row in df.iterrows():
            for col, width in zip(COLUMNAS_REQUERIDAS, col_widths):
                valor = str(row[col]) if pd.notna(row[col]) else ""
                valor = (valor[:18] + '...') if len(valor) > 18 else valor
                
                # Formato especial para precios
                if col == "Precio":
                    valor = f"${float(valor):,.2f}" if valor else "$0.00"
                
                pdf.cell(width, 8, valor, border=1)
            pdf.ln()
        
        # Total
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(sum(col_widths[:3]), 8, "Total Valor Inventario:", border=1)
        pdf.cell(col_widths[3], 8, str(df["Cantidad"].sum()), border=1)
        total_valor = (df["Cantidad"] * df["Precio"]).sum()
        pdf.cell(col_widths[4], 8, f"${total_valor:,.2f}", border=1)
        pdf.cell(col_widths[5], 8, "", border=1)
        
        pdf_output = BytesIO()
        pdf.output(pdf_output)
        return pdf_output.getvalue()
    except Exception as e:
        st.error(f"Error al generar PDF: {str(e)}")
        return None

def cargar_archivo(uploaded_file):
    """Procesa un archivo Excel subido por el usuario"""
    try:
        with st.spinner(f"Cargando archivo {uploaded_file.name}..."):
            # Leer archivo Excel
            nuevo_df = pd.read_excel(uploaded_file)
            
            # Validar archivo
            if nuevo_df.empty:
                st.warning("El archivo está vacío")
                return False
                
            # Procesar datos
            nuevo_df = estandarizar_columnas(nuevo_df)
            nuevo_df = completar_columnas(nuevo_df)
            
            # Validar datos críticos
            if nuevo_df["Producto"].isnull().any():
                st.error("El campo 'Producto' no puede estar vacío")
                return False
                
            if nuevo_df["Categoría"].isnull().any():
                st.error("El campo 'Categoría' no puede estar vacío")
                return False
                
            # Generar IDs si no existen
            if nuevo_df["ID"].isnull().any():
                base_id = len(cargar_datos_desde_db()) + 1
                nuevo_df["ID"] = [f"PROD-{base_id + i:04d}" for i in range(len(nuevo_df))]
            
            # Mostrar vista previa
            with st.expander("📝 Vista previa (primeras 5 filas)", expanded=True):
                st.dataframe(nuevo_df.head())

            # Guardar en base de datos
            if guardar_datos_en_db(nuevo_df):
                st.success(f"¡Archivo cargado correctamente! ({len(nuevo_df)} registros)")
                return True
            return False
    except Exception as e:
        st.error(f"Error al cargar archivo: {str(e)}")
        return False

# ---------------------------
# INTERFAZ DE USUARIO
# ---------------------------

# Inicialización
inicializar_base_datos()
df = cargar_datos_desde_db()

# Interfaz principal
st.title("📦 Sistema de Gestión de Inventario")
status_bar = st.empty()

# Sidebar
with st.sidebar:
    st.header("Operaciones")

    # Subir archivo Excel
    uploaded_file = st.file_uploader("Subir archivo Excel", type=["xlsx", "xls"])
    if uploaded_file and cargar_archivo(uploaded_file):
        df = cargar_datos_desde_db()
        st.rerun()

    st.markdown("---")

    # Opciones de descarga
    if not df.empty:
        if st.button("📥 Descargar Excel", help="Descargar inventario en formato Excel"):
            excel_data = guardar_inventario_excel(df)
            if excel_data:
                b64 = base64.b64encode(excel_data).decode()
                st.markdown(
                    f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="inventario.xlsx">⬇️ Descargar Excel</a>',
                    unsafe_allow_html=True
                )

        if st.button("📄 Descargar PDF", help="Generar reporte PDF del inventario"):
            pdf_data = generar_pdf(df)
            if pdf_data:
                b64 = base64.b64encode(pdf_data).decode()
                st.markdown(
                    f'<a href="data:application/pdf;base64,{b64}" download="inventario.pdf">⬇️ Descargar PDF</a>',
                    unsafe_allow_html=True
                )

    st.markdown("---")
    if st.button("🔄 Actualizar vista", key="sidebar_refresh"):
        df = cargar_datos_desde_db()
        st.rerun()

# Editor principal
if not df.empty:
    st.header("Editor de Inventario")

    edited_df = st.data_editor(
        df,
        use_container_width=True,
        height=600,
        num_rows="dynamic",
        key="data_editor_main",
        column_config={
            "ID": st.column_config.TextColumn("ID", required=True),
            "Producto": st.column_config.TextColumn(
                "Producto", 
                required=True,
                max_chars=50,
                help="Nombre completo del producto"
            ),
            "Categoría": st.column_config.SelectboxColumn(
                "Categoría",
                options=["Electrónica", "Ropa", "Alimentos", "Herramientas", "Otros"],
                required=True,
                help="Seleccione una categoría"
            ),
            "Cantidad": st.column_config.NumberColumn(
                "Cantidad", 
                min_value=0, 
                default=0,
                help="Cantidad en stock"
            ),
            "Precio": st.column_config.NumberColumn(
                "Precio", 
                min_value=0.0, 
                format="%.2f", 
                default=0.0,
                help="Precio unitario"
            ),
            "Ubicación": st.column_config.TextColumn(
                "Ubicación",
                help="Ubicación en el almacén"
            )
        },
        disabled=["ID"]  # No permitir editar el ID directamente
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💾 Guardar cambios", help="Guardar todos los cambios realizados"):
            # Validar datos antes de guardar
            if edited_df["Producto"].isnull().any():
                status_bar.error("El campo 'Producto' no puede estar vacío")
            elif edited_df["Categoría"].isnull().any():
                status_bar.error("El campo 'Categoría' no puede estar vacío")
            else:
                if guardar_datos_en_db(edited_df):
                    df = cargar_datos_desde_db()
                    status_bar.success("¡Cambios guardados correctamente!")
                    time.sleep(1)
                    st.rerun()
                
    with col2:
        if st.button("🔄 Actualizar vista", help="Recargar datos desde la base de datos"):
            df = cargar_datos_desde_db()
            st.rerun()
            
    with col3:
        if st.button("🧹 Limpiar datos", help="Eliminar todos los registros", type="primary"):
            with st.popover("⚠️ Confirmar limpieza"):
                st.warning("¿Está seguro que desea eliminar TODOS los datos? Esta acción no se puede deshacer.")
                if st.button("CONFIRMAR LIMPIEZA", type="primary"):
                    guardar_datos_en_db(pd.DataFrame(columns=COLUMNAS_REQUERIDAS))
                    df = cargar_datos_desde_db()
                    status_bar.info("Datos limpiados correctamente")
                    time.sleep(1)
                    st.rerun()

else:
    st.warning("No hay datos de inventario cargados. Suba un archivo Excel para comenzar.")

# Añadir nuevo producto
with st.expander("➕ Añadir nuevo producto", expanded=False):
    with st.form("nuevo_producto_form", clear_on_submit=True):
        cols = st.columns(3)
        with cols[0]:
            nuevo_id = st.text_input(
                "ID del producto", 
                value=f"PROD-{len(df)+1:04d}",
                help="Identificador único del producto"
            )
        with cols[1]:
            nuevo_nombre = st.text_input(
                "Nombre del producto*", 
                help="Nombre descriptivo del producto",
                max_chars=50
            )
        with cols[2]:
            nueva_categoria = st.selectbox(
                "Categoría*", 
                ["Electrónica","Alimentos", "Herramientas", "Otros"],
                help="Seleccione la categoría del producto"
            )

        cols2 = st.columns(3)
        with cols2[0]:
            nueva_cantidad = st.number_input(
                "Cantidad*", 
                min_value=0, 
                value=1,
                help="Cantidad inicial en inventario"
            )
        with cols2[1]:
            nuevo_precio = st.number_input(
                "Precio unitario*", 
                min_value=0.0, 
                value=0.0, 
                step=0.01, 
                format="%.2f",
                help="Precio por unidad"
            )
        with cols2[2]:
            nueva_ubicacion = st.text_input(
                "Ubicación", 
                value="ALM-01",
                help="Ubicación en el almacén",
                max_chars=20
            )

        if st.form_submit_button("➕ Añadir producto"):
            if not nuevo_nombre:
                status_bar.error("El nombre del producto es obligatorio")
            else:
                nuevo_producto = pd.DataFrame([{
                    "ID": nuevo_id,
                    "Producto": nuevo_nombre,
                    "Categoría": nueva_categoria,
                    "Cantidad": nueva_cantidad,
                    "Precio": nuevo_precio,
                    "Ubicación": nueva_ubicacion
                }])
                
                # Verificar si el ID ya existe
                if nuevo_id in df["ID"].values:
                    status_bar.error(f"El ID {nuevo_id} ya existe")
                else:
                    df = pd.concat([df, nuevo_producto], ignore_index=True)
                    if guardar_datos_en_db(df):
                        df = cargar_datos_desde_db()
                        status_bar.success(f"Producto {nuevo_id} añadido correctamente!")
                        time.sleep(1)
                        st.rerun()

# Estadísticas
if not df.empty:
    with st.expander("📊 Análisis del Inventario", expanded=True):
        tab1, tab2, tab3 = st.tabs(["Resumen", "Distribución", "Detalles"])
        
        with tab1:
            cols = st.columns(4)
            with cols[0]:
                st.metric("Total productos", len(df))
            with cols[1]:
                st.metric("Total unidades", df["Cantidad"].sum())
            with cols[2]:
                total_valor = (df["Cantidad"] * df["Precio"]).sum()
                st.metric("Valor total", f"${total_valor:,.2f}")
            with cols[3]:
                st.metric("Categorías", df["Categoría"].nunique())

        with tab2:
            st.subheader("Distribución por categoría")
            st.bar_chart(df["Categoría"].value_counts())

            st.subheader("Top 10 productos más abundantes")
            top_productos = df.nlargest(10, "Cantidad")[["Producto", "Cantidad", "Precio"]]
            top_productos["Valor Total"] = top_productos["Cantidad"] * top_productos["Precio"]
            st.dataframe(top_productos.style.format({"Precio": "${:,.2f}", "Valor Total": "${:,.2f}"}))

            st.subheader("Productos con bajo stock (≤ 5 unidades)")
            bajo_stock = df[df["Cantidad"] <= 5][["Producto", "Cantidad", "Ubicación"]]
            st.dataframe(bajo_stock.sort_values("Cantidad"))

        with tab3:
            st.subheader("Datos completos")
            st.dataframe(df.style.format({"Precio": "${:,.2f}"}))

# Botón de actualización global
if st.button("🔄 Actualizar Todo", key="global_refresh"):
    df = cargar_datos_desde_db()
    st.rerun()
