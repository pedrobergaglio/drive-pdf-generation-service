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

folder_id = "1d8DcVWEiE67RRCJ5PKeIVvxMSNIBiKEi"

class PDF(FPDF):
    def header(self):
        pass  # No generamos encabezado porque la hoja preimpresa ya lo tiene
    
    def footer(self):
        pass  # No generamos pie de página por la misma razón

def generate_pdf(data, output_path):
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

def upload_to_drive(file_path, file_name):
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
        
        generate_pdf(data, output_path)
        drive_file_id = upload_to_drive(output_path, output_filename)
        
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
