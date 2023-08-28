from jwt.exceptions import ExpiredSignatureError
from flask import Flask, render_template, request, jsonify,make_response
from flask_mail import Mail, Message
import sqlite3
from werkzeug.local import Local
from functools import wraps
from flask_jwt_extended import JWTManager,jwt_required
import jwt
import datetime

app = Flask(__name__)

app.config['SECRET_KEY'] = '01f210f05f874915ad4e1598ce7f6454'

def get_db(db_name='error_logs.db'):
    if not hasattr(db, 'conn'):
        db.conn = sqlite3.connect(db_name)
        # The connection will be automatically closed at the end of the request
        app.teardown_appcontext(close_connection)
    return db.conn

def create_error_logs_table():
    conn = get_db()  # Use the error_logs.db database
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS error_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            invalid_token TEXT,
            sub_claim TEXT,
            name_claim TEXT,
            error_message TEXT
        )
    ''')
    conn.commit()
    
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        print("Inside token_required decorator")
        authorization_header = request.headers.get('Authorization')
        
        if not authorization_header:
            return jsonify({'message': 'Authorization header is missing.'}), 401
        
        parts = authorization_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({'message': 'Invalid Authorization header format.'}), 401
        
        token = parts[1]  # Remove "Bearer" prefix
        print("Token extracted:", token)
        
        try:
            decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            print("Valid token")
            # Continue with regular token verification logic
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError as expired_err:
            # Log expired token error
            print("Expired token error:", str(expired_err))
            log_error_to_db(token, None, None, str(expired_err))
            return jsonify({'message': 'Expired token.'}), 403
        except jwt.InvalidTokenError as invalid_err:
            # Log invalid token error
            print("Invalid token error:", str(invalid_err))
            log_error_to_db(token, None, None, str(invalid_err))
            return jsonify({'message': 'Invalid token.'}), 403
        except Exception as e:
            # Log other exceptions
            print("Other exception:", str(e))
            log_error_to_db(token, None, None, str(e))
            return jsonify({'message': 'An error occurred.'}), 500
    return decorated

def log_error_to_db(invalid_token, sub_claim, name_claim, error_message):
    try:
        conn = get_db()
        query = '''
            INSERT INTO error_logs (invalid_token, sub_claim, name_claim, error_message)
            VALUES (?, ?, ?, ?)
        '''
        conn.execute(query, (invalid_token, sub_claim, name_claim, error_message))
        conn.commit()
    except Exception as db_error:
        print("Database error:", db_error)



@app.route('/unprotected')
def unprotected():
    return jsonify({'message':'Anyone can view this!'})

@app.route('/protected')
@token_required
def protected():
    return jsonify({'message':'This is only availabe for people with valid token.'})

# def login():
#     auth = request.authorization
#     if auth and auth.password == 'password':
#         token = create_access_token(identity=auth.username, expires_delta=datetime.timedelta(minutes=30))
#         return jsonify({'token': token})
#     return make_response('Could not verify!', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

# Initialize Flask-Mail
mail = Mail(app)


db = Local()

def get_db(db_name='email_logs.db'):
    if not hasattr(db, 'conn'):
        db.conn = sqlite3.connect(db_name)
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

# Secure routes with JWT
@app.route('/send_message', methods=["GET", "POST"])  # Allow only POST method
@token_required
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
# @token_required
def email_logs():
    conn = get_db()
    cursor = conn.execute("SELECT * FROM email_logs")
    logs = cursor.fetchall()
    return render_template('email_logs.html', logs=logs)

@app.route('/error_logs')
# @token_required
def error_logs():
    conn = get_db()
    cursor = conn.execute("SELECT * FROM error_logs")  # Use the correct table name
    logs = cursor.fetchall()
    return render_template('error_logs.html', logs=logs)


@app.route('/result')
def result():
    return render_template('result.html')

if __name__ == '__main__':
    create_table()
    create_error_logs_table()  # Call the function to create the error_logs table
    app.run(debug=True)


def close_connection(exception):
    conn = getattr(db, 'conn', None)
    if conn is not None:
        conn.close()

app.teardown_appcontext(close_connection)