from flask import Flask , render_template , request
from flask_mail import Mail,Message

app = Flask(__name__)


app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT']= 465
app.config['MAIL_USERNAME']='kaushikshetty6979@gmail.com'
app.config['MAIL_PASSWORD']='mktuxahxuajpueno'
app.config['MAIL_USE_TLS']=False 
app.config['MAIL_USE_SSL']=True

mail= Mail(app)



@app.route('/')
def members():
  return render_template('index.html')


@app.route('/send_message',methods=["GET","POST"])
def send_message():
    if request.method=="POST":
        email = request.form['email']
        msg=request.form['message']
        subject=request.form['subject']

        message = Message(subject , sender="kaushikshetty6979@gmail.com" , recipients=[email])

        message.body =msg 
        mail.send(message)
        success = "Message sent"
        return render_template("result.html" , success=success)

if  __name__== '__main__' :
     app.run(debug=True)