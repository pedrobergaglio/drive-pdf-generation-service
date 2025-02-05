from flask import Flask, request
from fpdf import FPDF
import os
import json
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials

# Definir el alcance (scope) de la API de Google Drive
scope = ["https://www.googleapis.com/auth/drive"]

# Configurar la autenticación
gauth = GoogleAuth()
gauth.auth_method = 'service'
gauth.credentials = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
drive = GoogleDrive(gauth)

app = Flask(__name__)

OUTPUT_FOLDER = "generated_pdfs"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

class PDF(FPDF):
    def header(self):
        pass  # No generamos encabezado porque la hoja preimpresa ya lo tiene
    
    def footer(self):
        pass  # No generamos pie de página por la misma razón

def generate_remito(data, output_path):
    try:
        pdf = PDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        
        # Posiciones ajustables (medidas en mm)
        x_cliente, y_cliente = 40, 75
        x_cuit, y_cuit = 150, 100
        x_fecha, y_fecha = 145, 40
        x_cond_pago, y_cond_pago = 50, 110
        x_direccion, y_direccion = 40, 85
        x_cond_iva, y_cond_iva = 40, 100
        x_productos, y_productos = 10, 135
        x_numero_remito, y_numero_remito = 150, 110
        
        # Datos del cliente
        required_fields = ['cliente', 'remito_numero', 'cuit', 'fecha', 'condicion_pago', 
                         'direccion', 'condicion_iva', 'productos_pedidos']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        pdf.set_xy(x_cliente, y_cliente)
        pdf.cell(0, 10, data['cliente'], ln=True)

        pdf.set_xy(x_numero_remito, y_numero_remito)
        pdf.cell(0, 10, f"{data['remito_numero']}", ln=True)
        
        pdf.set_xy(x_cuit, y_cuit)
        pdf.cell(0, 10, data['cuit'], ln=True)
        
        pdf.set_xy(x_fecha, y_fecha)
        pdf.cell(0, 10, data['fecha'], ln=True)
        
        pdf.set_xy(x_cond_pago, y_cond_pago)
        pdf.cell(0, 10, f"Pago a {data['condicion_pago']} días" if data['condicion_pago']=="" else "", ln=True)
        
        pdf.set_xy(x_direccion, y_direccion)
        pdf.cell(0, 10, data['direccion'], ln=True)
        
        pdf.set_xy(x_cond_iva, y_cond_iva)
        pdf.cell(0, 10, data['condicion_iva'], ln=True)
        
        # Productos
        y_offset = y_productos
        for producto in data['productos_pedidos']:
            pdf.set_xy(x_productos, y_offset)
            pdf.cell(15, 5, str(producto.get('cantidad', '')), border=0)
            pdf.cell(25, 5, str(producto.get('product_id', '')), border=0)
            pdf.multi_cell(100, 5, producto.get('product', ''))
            y_offset = pdf.get_y()
            pdf.set_xy(x_productos + 140, y_offset - 5)
            pdf.cell(30, 5, f"N° serie {producto.get('n_serie', '')}" if producto.get('n_serie', '') == "" else "", border=0)
            y_offset = pdf.get_y() + 5

        pdf.output(output_path)
    except Exception as e:
        raise Exception(f"Error generating PDF: {str(e)}")

def validate_numeric_fields(data):
    numeric_fields = {
        'validez_oferta': 'Validez de oferta',
        'plazo_estimado_entrega': 'Plazo estimado de entrega'
    }
    
    for field, label in numeric_fields.items():
        try:
            if not str(data[field]).replace('.', '').isdigit():
                raise ValueError(f"{label} debe ser un número válido")
        except KeyError:
            raise ValueError(f"Falta el campo {label}")

def validate_option_data(option):
    try:
        float(option['descuento_gral'])
        if not option.get('productos_pedidos'):
            raise ValueError("La opción debe contener al menos un producto")
        
        for producto in option['productos_pedidos']:
            float(producto['precio_siva_unitario'])
            float(producto['precio_siva_total'])
            if int(producto['cantidad']) <= 0:
                raise ValueError("La cantidad debe ser mayor a 0")
    except (KeyError, ValueError, TypeError) as e:
        raise ValueError(f"Datos de opción inválidos: {str(e)}")

def generate_presupuesto(data, output_path):
    class PDF(FPDF):
        def header(self):
            # Page width calculations
            page_width = self.w
            margin = 10
            content_width = page_width - 2 * margin
            
            # Logo
            try:
                self.image('logo-eg.png', margin, 8, 90)
            except:
                pass
            
            # Header Right Section
            self.set_font('Arial', 'B', 12)
            self.set_text_color(0, 0, 0)
            self.set_xy(page_width - margin - 70, 10)
            self.cell(70, 8, 'Propuesta comercial N°', 0, 0, 'R')
            self.set_font('Arial', '', 12)
            self.set_xy(page_width - margin - 70, 18)
            self.cell(70, 8, f"{data.get('remito_numero', '')}", 0, 1, 'R')
            
            # Date and Validity
            self.set_xy(page_width - margin - 70, 26)
            self.set_font('Arial', 'B', 10)
            self.cell(30, 6, 'Fecha:', 0, 0)
            self.set_font('Arial', '', 10)
            self.cell(40, 6, f"{data.get('fecha', '')}", 0, 1)
            
            self.set_xy(page_width - margin - 70, 32)
            self.set_font('Arial', 'B', 10)
            self.cell(30, 6, 'Validez oferta:', 0, 0)
            self.set_font('Arial', '', 10)
            self.cell(40, 6, f"{data.get('validez_oferta', '')} días", 0, 1)
            
            # Client Section with green stroke
            self.set_draw_color(0, 150, 0)
            self.set_line_width(0.5)  # Thinner border
            self.rect(margin, 43, content_width, 20)  # Increased height
            self.set_line_width(0.2)
            self.set_draw_color(0, 0, 0)
            
            # Client info with proper spacing
            self.set_xy(margin + 2, 45)
            self.set_font('Arial', 'B', 10)
            self.cell(20, 6, 'Cliente:', 0, 0)
            self.set_font('Arial', '', 10)
            self.multi_cell(content_width - 25, 6, data.get('cliente', ''), 0, 'L')
            
            self.set_xy(margin + 2, 52)
            self.set_font('Arial', 'B', 10)
            self.cell(15, 6, 'CUIT:', 0, 0)
            self.set_font('Arial', '', 10)
            self.cell(60, 6, data.get('cuit', ''), 0, 1)
            
            # Line below header
            self.line(margin, 67, page_width - margin, 67)
            
            # Reset position for content
            self.set_y(70)

        # Remove the rounded_rect and rounded_corner methods as they're no longer needed

        def footer(self):
            # Thicker green line above footer
            self.set_draw_color(0, 150, 0)
            self.set_line_width(0.5)  # Make line thicker
            self.line(10, 270, 200, 270)
            self.set_line_width(0.2)  # Reset line width
            self.set_draw_color(0, 0, 0)
            
            # Footer text - now bold
            self.set_y(-25)
            self.set_font('Arial', 'B', 8)  # Changed to bold
            self.set_text_color(128, 128, 128)
            footer_text = 'Oran 3196 esq. colectora acceso oeste - Ituzaingo - Bs. As.\n'
            footer_text += 'CUIT: 30-71074699-7\n'
            footer_text += 'Telefono: 5263-9002 - info@energiaglobal.com.ar'
            
            self.multi_cell(0, 4, footer_text, 0, 'C')
            
            # Page number
            self.set_y(-35)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(0, 0, 0)
            self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'R')

    try:
        # Add to required fields validation
        required_fields = ['file_name', 'cliente', 'remito_numero', 'cuit', 'fecha', 
                         'validez_oferta', 'metodo_pago', 'condicion_de_pago',
                         'plazo_estimado_entrega', 'direccion', 
                         'opciones', 'observaciones']
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        validate_numeric_fields(data)
        
        pdf = PDF()
        pdf.set_auto_page_break(auto=True, margin=35)
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        
        # Options and Products - now sorted by id_opcion
        sorted_options = sorted(data['opciones'], key=lambda x: int(x['id_opcion']))
        for opcion in sorted_options:
            pdf.ln(5)
            # Option header with gray background
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font('Arial', 'B', 10)
            currency_symbol = "Dólar" in opcion['aclaracion_moneda']
            header_text = f"Opción {opcion['id_opcion']}" + (f" - {opcion['descuento_gral']}" if opcion['descuento_gral'].strip() else "") + f" - Moneda: {opcion['aclaracion_moneda']}"
            pdf.cell(0, 8, header_text, 1, 1, 'L', True)
            
            # Products header with columns
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(15, 6, 'Cant.', 1, 0, 'C')
            pdf.cell(95, 6, 'Descripción', 1, 0, 'C')
            pdf.cell(40, 6, 'Precio Unit.', 1, 0, 'C')
            pdf.cell(40, 6, 'Subtotal', 1, 1, 'C')
            
            # Products with currency symbol
            pdf.set_font('Arial', '', 9)
            currency = "U$S" if currency_symbol else "$"
            
            for producto in opcion['productos_pedidos']:
                # Calculate height based on description
                lines = len(pdf.multi_cell(95, 5, producto['producto'], split_only=True))
                height = max(6, lines * 5)
                
                # Start Y position
                start_y = pdf.get_y()
                
                # Draw all cells with same height
                pdf.cell(15, height, str(producto['cantidad']), 1, 0, 'C')
                pdf.multi_cell(95, height/lines, producto['producto'], 1, 'L')
                
                # Return to right position for prices
                pdf.set_xy(120, start_y)
                pdf.cell(40, height, f"{currency}{producto['precio_siva_unitario']}", 1, 0, 'R')
                pdf.cell(40, height, f"{currency}{producto['precio_siva_total']}", 1, 1, 'R')
            
            # Option totals with increased height
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(150, 7, 'Subtotal:', 0, 0, 'R')
            pdf.cell(40, 7, f"{currency}{opcion['precio_final_siva']}", 0, 1, 'R')
            pdf.cell(150, 7, 'IVA:', 0, 0, 'R')
            pdf.cell(40, 7, f"{currency}{opcion['iva']}", 0, 1, 'R')
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(150, 8, 'TOTAL:', 0, 0, 'R')
            pdf.cell(40, 8, f"{currency}{opcion['precio_final']}", 0, 1, 'R')
        
        # Commercial conditions with proper text wrapping
        pdf.ln(10)
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 8, 'Condiciones Comerciales', 0, 1, 'L')
        
        def add_field_with_label(label, value):
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(40, 6, label, 0, 0)
            pdf.set_font('Arial', '', 10)
            current_x = pdf.get_x()
            current_y = pdf.get_y()
            pdf.multi_cell(150, 6, str(value))
            pdf.set_xy(10, pdf.get_y() + 2)
        
        # Add fields in order
        if data.get('condicion_de_pago'):
            add_field_with_label('Condición de pago:', f"{data['condicion_de_pago']} días")
        add_field_with_label('Método de pago:', data.get('metodo_pago', ''))
        add_field_with_label('Plazo de entrega:', f"{data.get('plazo_estimado_entrega', '')} días")
        add_field_with_label('Dirección de envío:', data.get('direccion', ''))
        
        # Observations
        if data.get('observaciones'):
            pdf.ln(5)
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(0, 6, 'Observaciones:', 0, 1)
            pdf.set_font('Arial', '', 9)
            pdf.multi_cell(0, 5, data['observaciones'])
        
        # Currency disclaimer
        pdf.ln(10)
        pdf.set_font('Arial', 'I', 9)
        disclaimer = "Las cotizaciones en pesos argentinos (ARS) serán convertidas a dólares Banco Nación (USD) "
        disclaimer += "al tipo de cambio vigente al momento de su aceptación. El precio final en pesos argentinos "
        disclaimer += "se ajustará diariamente según la cotización del dólar oficial hasta la cancelación total de la deuda."
        pdf.multi_cell(0, 5, disclaimer)
        
        pdf.output(output_path)
        
    except Exception as e:
        raise Exception(f"Error generating PDF: {str(e)}")

def upload_to_drive(file_path, file_name, folder_id):
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        query = f"title='{file_name}' and '{folder_id}' in parents and trashed=false"
        file_list = drive.ListFile({'q': query}).GetList()

        if file_list:
            file_drive = file_list[0]
            file_drive.SetContentFile(file_path)
            file_drive.Upload()
        else:
            file_drive = drive.CreateFile({'title': file_name, 'parents': [{'id': folder_id}]})
            file_drive.SetContentFile(file_path)
            file_drive.Upload()

        return file_drive['id']
    except Exception as e:
        raise Exception(f"Error uploading to Drive: {str(e)}")

@app.route("/generate", methods=["POST"])
def generate_pdf_endpoint():
    try:
        data = request.get_json()
        if not data:
            return {"error": "No JSON data received"}, 400
        
        if 'file_name' not in data:
            return {"error": "Missing file_name in request"}, 400

        output_filename = f"{data['file_name']}.pdf"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        generate_remito(data, output_path)
        drive_file_id = upload_to_drive(output_path, output_filename, folder_id="1d8DcVWEiE67RRCJ5PKeIVvxMSNIBiKEi")
        
        return {
            "message": "PDF generated and uploaded successfully", 
            "file": output_filename, 
            "drive_file_id": drive_file_id
        }, 200

    except ValueError as e:
        return {"error": str(e)}, 400
    except FileNotFoundError as e:
        return {"error": str(e)}, 404
    except Exception as e:
        return {"error": f"Internal server error: {str(e)}"}, 500

@app.route("/generate-presupuesto", methods=["POST"])
def generate_presupuesto_endpoint():
    try:
        data = request.get_json()
        if not data:
            return {"error": "No JSON data received"}, 400
        
        if 'file_name' not in data:
            return {"error": "Missing file_name in request"}, 400

        output_filename = f"{data['file_name']}.pdf"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        generate_presupuesto(data, output_path)
        drive_file_id = upload_to_drive(output_path, output_filename, folder_id="1qPtVSoeJk9D53vKnlPzj6mprt-XwsSsd")
        
        return {
            "message": "PDF generated and uploaded successfully", 
            "file": output_filename, 
            "drive_file_id": drive_file_id
        }, 200

    except ValueError as e:
        return {"error": str(e)}, 400
    except FileNotFoundError as e:
        return {"error": str(e)}, 404
    except Exception as e:
        return {"error": f"Internal server error: {str(e)}"}, 500


if __name__ == "__main__":
    app.run(port=5001, debug=False)
