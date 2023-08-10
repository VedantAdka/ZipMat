from flask import Flask, render_template, request
from flask_mail import Mail, Message
import sqlite3
from werkzeug.local import Local, LocalProxy
from dotenv import load_dotenv
import os
email_address = os.getenv("email_address")
email_password = os.getenv("email_password")

load_dotenv()
app = Flask(__name__)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = email_address
app.config['MAIL_PASSWORD'] = email_password
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

mail = Mail(app)

db = Local()

def get_db():
    if not hasattr(db, 'conn'):
        db.conn = sqlite3.connect('email_logs.db')
    return db.conn

def create_table():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS email_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sender_email TEXT,
            recipient_email TEXT,
            subject TEXT,
            body TEXT,
            request TEXT,
            response TEXT,
            status TEXT
        )
    ''')

@app.route('/')
def members():
    return render_template('index.html')

@app.route('/send_message', methods=["POST"])
def send_message():
    if request.method == "POST":
        email = request.form['email']
        selected_message = request.form['message']
        subject = "Order Status: " + selected_message

        message = Message(subject, sender="kaushikshetty6979@gmail.com", recipients=[email])

        if selected_message == "Order Delivered":
            order_id_delivered = request.form.get('order_id_delivered', '')
            product_name_delivered = request.form.get('product_name_delivered', '')
            delivery_date = request.form.get('delivery_date', '')

            message.body = f"Your order has been delivered.\nOrder ID: {order_id_delivered}\nProduct Name: {product_name_delivered}\nDelivery Date: {delivery_date}"
        elif selected_message == "Order Confirmed":
            order_id = request.form.get('order_id', '')
            product_name = request.form.get('product_name', '')

            message.body = f"Your order has been confirmed.\nOrder ID: {order_id}\nProduct Name: {product_name}"
        else:
            message.body = "This is a default email content."

        request_data = {
            'email': email,
            'message': selected_message,
            'order_id': order_id if selected_message == "Order Confirmed" else '',
            'product_name': product_name if selected_message == "Order Confirmed" else '',
            'order_id_delivered': order_id_delivered if selected_message == "Order Delivered" else '',
            'product_name_delivered': product_name_delivered if selected_message == "Order Delivered" else '',
            'delivery_date': delivery_date if selected_message == "Order Delivered" else '',
        }

        try:
            response = mail.send(message)

            response_data = {
                'status': 'Success',
                'message': 'Email sent successfully',
                'response_data': 'No response data'
            }

            status_code = 200
            success_message = "Email sent successfully"

            conn = get_db()
            conn.execute('''
                INSERT INTO email_logs (sender_email, recipient_email, subject, body, request, response, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (message.sender, message.recipients[0], message.subject, message.body, str(request_data), str(response_data), status_code))

            conn.commit()

            return render_template("result.html", success=success_message)

        except Exception as e:
            conn = get_db()
            conn.execute('''
                INSERT INTO email_logs (sender_email, recipient_email, subject, body, request, response, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (message.sender, message.recipients[0], message.subject, message.body, str(request_data), str(e), 'Error'))

            conn.commit()

            error_message = "An error occurred while sending the message"
            return render_template("result.html", error=error_message)

@app.route('/email_logs')
def email_logs():
    conn = get_db()
    cursor = conn.execute("SELECT * FROM email_logs")
    logs = cursor.fetchall()
    return render_template('email_logs.html', logs=logs)

if __name__ == '__main__':
    create_table()
    app.run(debug=True)

def close_connection(exception):
    conn = getattr(db, 'conn', None)
    if conn is not None:
        conn.close()

app.teardown_appcontext(close_connection)
