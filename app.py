from flask import Flask, render_template, request
from requests import HTTPError
from flask_mail import Mail, Message
import sqlite3
from werkzeug.local import Local, LocalProxy
from dotenv import load_dotenv
import os
# we did the branching and pull requset 

load_dotenv()
app = Flask(__name__)
email_address=os.getenv("email_address")
email_password=os.getenv("email_password")
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = email_address
app.config['MAIL_PASSWORD'] = email_password
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

mail = Mail(app)

# Create a LocalProxy for the SQLite connection
db = Local()
def get_db():
    if not hasattr(db, 'conn'):
        db.conn = sqlite3.connect('email_logs.db')
    return db.conn

# Create a table for logging API requests and responses
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

@app.route('/send_message', methods=["GET", "POST"])
def send_message():
    if request.method == "POST":
        email = request.form['email']
        msg = request.form['message']
        subject = request.form['subject']

        message = Message(subject, sender="kaushikshetty6979@gmail.com", recipients=[email])

        message.body = msg

        # Capture the request data
        request_data = {
            'email': email,
            'message': msg,
            'subject': subject
        }

        try:
            # Send the email via API
            response = mail.send(message)

            # Create a response_data dictionary without status code
            response_data = {
                'status': 'Success',
                'message': 'Email sent successfully',
                'response_data': 'No response data'
            }

            # Infer the status code based on the success
            status_code = 200  # Assuming a success status code
            success_message = "Email sent successfully"

            # Insert the request and response data into the database
            conn = get_db()
            conn.execute('''
                INSERT INTO email_logs (sender_email, recipient_email, subject, body, request, response, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (message.sender, message.recipients[0], message.subject, message.body, str(request_data), str(response_data), status_code))

            # Commit the changes to the database
            conn.commit()

            return render_template("result.html", success=success_message)

        except Exception as e:
            # Log any exceptions that occur during email sending
            conn = get_db()
            conn.execute('''
                INSERT INTO email_logs (sender_email, recipient_email, subject, body, request, response, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (message.sender, message.recipients[0], message.subject, message.body, str(request_data), str(e), 'Error'))

            # Commit the changes to the database
            conn.commit()

            error_message = "An error occurred while sending the message"
            return render_template("result.html", error=error_message)


@app.route('/email_logs')
def email_logs():
    # Retrieve all email logs from the database
    conn = get_db()
    cursor = conn.execute("SELECT * FROM email_logs")
    logs = cursor.fetchall()
    return render_template('email_logs.html', logs=logs)

if __name__ == '__main__':
    create_table()
    app.run(debug=True)

# Close the database connection
def close_connection(exception):
    conn = getattr(db, 'conn', None)
    if conn is not None:
        conn.close()

app.teardown_appcontext(close_connection)
