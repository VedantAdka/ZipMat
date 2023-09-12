from jwt.exceptions import ExpiredSignatureError
from flask import Flask, render_template, request, jsonify,make_response
from flask_mail import Mail, Message
import sqlite3
from werkzeug.local import Local
from functools import wraps
from flask_jwt_extended import JWTManager,jwt_required
import jwt
import datetime
from dotenv import load_dotenv 
import os
import redis


app = Flask(__name__)
load_dotenv()

# Initialize Redis client
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

def get_invalid_token_db():
    if not hasattr(db, 'invalid_token_conn'):
        db.invalid_token_conn = sqlite3.connect('invalid_token_logs.db')
    return db.invalid_token_conn

def deduplicate_request(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Generate a unique hash based on the email address in the request
        email = request.form.get('email', '')  # Assuming the email is in the form data
        request_hash = hash(email)

        # Check if the hash exists in Redis (indicating a duplicate request)
        if redis_client.exists(request_hash):
            return jsonify({'message': 'Duplicate request.'}), 400

        # Store the hash in Redis with an expiration of 15 minutes
        redis_client.setex(request_hash, 900, 1)

        # Proceed with the decorated function
        return f(*args, **kwargs)

    return decorated

# Decorator for rate limiting
def rate_limit(limit, window):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Get the JWT token from the request
            jwt_token = request.headers.get('Authorization')

            # Check if the JWT token is in Redis
            if jwt_token:
                jwt_token_count = redis_client.incr(jwt_token)

                # Set an expiry for the token if it doesn't exist in Redis
                if jwt_token_count == 1:
                    redis_client.expire(jwt_token, window)

                # Check if the request limit has been exceeded
                if jwt_token_count > limit:
                    return jsonify({'message': 'Rate limit exceeded.'}), 429

            # Proceed with the decorated function
            return f(*args, **kwargs)

        return decorated

    return decorator

def create_invalid_token_logs_table():
    conn = get_invalid_token_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invalid_token_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            invalid_token TEXT,
            sub_claim TEXT,
            name_claim TEXT,
            error_message TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_invalid_token_to_db(invalid_token, sub_claim, name_claim, error_message):
    try:
        print("Inside log_invalid_token_to_db function")
        print("Invalid Token:", invalid_token)
        print("Sub Claim:", sub_claim)
        print("Name Claim:", name_claim)
        print("Error Message:", error_message)
        
        conn = get_invalid_token_db()
        query = '''
            INSERT INTO invalid_token_logs (invalid_token, sub_claim, name_claim, error_message)
            VALUES (?, ?, ?, ?)
        '''
        conn.execute(query, (invalid_token, sub_claim, name_claim, error_message))
        conn.commit()
        print("Invalid token logged to database")
    except Exception as db_error:
        print("Database error:", db_error)
        import traceback
        traceback.print_exc()

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
        
        sub_claim = None  # Initialize sub_claim to None
        name_claim = None  # Initialize name_claim to None
        
        try:
            decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            print("Valid token")
            
            # Extract claims from the decoded token
            sub_claim = decoded_token.get('sub')
            name_claim = decoded_token.get('name')
            
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError as expired_err:
            # Log expired token error
            print("Expired token error:", str(expired_err))
            log_invalid_token_to_db(token, sub_claim, name_claim, str(expired_err))
            return jsonify({'message': 'Expired token.'}), 403
        except jwt.InvalidTokenError as invalid_err:
            # Log invalid token error
            print("Invalid token error:", str(invalid_err))
            log_invalid_token_to_db(token, sub_claim, name_claim, str(invalid_err))
            return jsonify({'message': 'Invalid token.'}), 403
        except Exception as e:
            # Log other exceptions
            print("Other exception:", str(e))
            log_invalid_token_to_db(token, sub_claim, name_claim, str(e))
            return jsonify({'message': 'An error occurred.'}), 500
    return decorated


@app.route('/unprotected')
def unprotected():
    return jsonify({'message':'Anyone can view this!'})

@app.route('/protected')
@token_required
def protected():
    return jsonify({'message':'This is only availabe for people with valid token.'})


# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.getenv('email_address')  # Get email address from environment variable
app.config['MAIL_PASSWORD'] = os.getenv('email_password')  # Get email password from environment variable
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
            status TEXT,
            name_claim TEXT,  -- Add the name_claim column
            sub_claim TEXT    -- Add the sub_claim column
        )
    ''')






@app.route('/')
def members():
    return render_template('index.html')

# Secure routes with JWT
@app.route('/send_message', methods=["POST"])
@token_required
@deduplicate_request
@rate_limit(limit=3, window=300)  # Adjust the limit and window values as needed
def send_message():
    jwt_token = request.headers.get('Authorization')
    if jwt_token:
        try:
            decoded_token = jwt.decode(jwt_token.split()[1], app.config['SECRET_KEY'], algorithms=['HS256'])
            name_claim = decoded_token.get('name')
            sub_claim = decoded_token.get('sub')
        except jwt.ExpiredSignatureError:
            # Handle token expiration
            name_claim = None
            sub_claim = None
        except jwt.InvalidTokenError:
            # Handle invalid token
            name_claim = None
            sub_claim = None
        except Exception:
            # Handle other exceptions
            name_claim = None
            sub_claim = None
    if request.method == "POST":
        email = request.form['email']
        selected_message = request.form['message']
        subject = "Order Status: " + selected_message

        message = Message(subject, sender="email_address", recipients=[email])

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
            mail.send(message)  # Send the email

            # Set status_message and status_code for a successful email send
            status_message = 'Success'
            status_code = 200

            response_data = {
                'status': status_message,
                'message': 'Email sent successfully',
                'response_data': 'No response data'
            }

        except Exception as e:
            # Handle the case where sending the email failed
            status_message = 'Error'
            status_code = 500

            response_data = {
                'status': status_message,
                'message': 'Email send failed',
                'response_data': str(e)
            }

        conn = get_db()
    conn.execute('''
        INSERT INTO email_logs (sender_email, recipient_email, subject, body, request, response, status, name_claim, sub_claim)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (message.sender, message.recipients[0], message.subject, message.body, str(request_data), str(response_data), status_code, name_claim, sub_claim))

    conn.commit()

    if status_message == 'Success':
        success_message = "Email sent successfully"
        return render_template("result.html", success=success_message)
    else:
        error_message = "An error occurred while sending the message"
        return render_template("result.html", error=error_message)

@app.route('/email_logs')
# @token_required
def email_logs():
    conn = get_db()
    cursor = conn.execute("SELECT * FROM email_logs")
    logs = cursor.fetchall()
    return render_template('email_logs.html', logs=logs)

@app.route('/invalid_token_logs')
# @token_required
def invalid_token_logs():
    conn = get_invalid_token_db()
    cursor = conn.execute("SELECT * FROM invalid_token_logs")
    logs = cursor.fetchall()
    return render_template('invalid_token_logs.html', logs=logs)


@app.route('/result')
def result():
    return render_template('result.html')

if __name__ == '__main__':
    create_table()
    create_invalid_token_logs_table()  
    app.run(debug=True)

def close_connection(exception):
    conn = getattr(db, 'conn', None)
    if conn is not None:
        conn.close()

app.teardown_appcontext(close_connection)