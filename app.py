from flask import *
#from flask_login import *
#from flask_login import UserMixin
#from flask_sqlalchemy import SQLAlchemy
#from flask_httpauth import HTTPBasicAuth
#from flask.ext.login import LoginManager
from flask import render_template
from werkzeug.utils import secure_filename
#from werkzeug.datastructures import FileStorage
#from flaskwebgui import FlaskUI
#import jwt
import random
import threading, os
#import time
#from main import *
import main

class CalculationThread(threading.Thread):
    def __init__(self, thread_id, calculation_results):
        self.thread_id = thread_id
        self.calculation_results = calculation_results
        self.calculation_results[self.thread_id] = ''
        self.progress = 0
        self.finished = False
        self.started = False
        super().__init__()

    def run(self):
        self.started = True
        print(f"{self.thread_id} - is started")
        
        # Your exporting stuff goes here ...
        # for _ in range(13):
        #     time.sleep(1) 
        #     self.progress += 10
        #     if self.progress > 100:
        #         self.progress = 0
        
        main.init_components(base_dir)
        main.calculate(base_dir)
        #time.sleep(3)    
                
        self.progress = 100
        self.calculation_results[self.thread_id] = f"{self.thread_id} - is finished\n" + main.log
        self.finished = True
        print(f"{self.thread_id} - is finished")

base_dir = './uploaded'
calculation_threads = {}
calculation_results = {}
files_types = ['consumption_file', 'production_file', 'building_file',
               'location_file', 'equipment_file', 'battery_file']

#os.environ['FLASK_RUN_PORT'] = '8000'
#os.environ['FLASK_RUN_HOST'] = "127.0.0.1"

app = Flask(__name__, template_folder='./template', static_folder='./static')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.sqlite3'
app.config['SECRET_KEY'] = '!secret_key!'
os.makedirs(base_dir, exist_ok=True)
app.config['UPLOAD_FOLDER'] = base_dir
app.config['MAX_CONTENT_PATH'] = 10 * 1000 * 1000

@app.route('/api/v1.0/upload', methods = ['GET', 'POST'])
#@auth.login_required
def upload_files():
    if request.method == 'POST':
        for ft in files_types:
            if ft in request.files:
                f = request.files[ft]
                if len(secure_filename(f.filename)):
                    print(f.filename)
                    f.save(os.path.join(base_dir, ft.split('_')[0] + '.csv'))
        return index_page(files_uploaded='\nFiles uploaded successfully!\n')

@app.route('/')
#@auth.login_required
def index_page(**args):  
    return render_template('index.html', **args)

@app.route('/api/v1.0/calculate')
#@auth.login_required
def api_calculate():
    global exporting_threads
    for thread_id in list(calculation_threads.keys()):
        if calculation_threads[thread_id].finished:
            del calculation_threads[thread_id]
            print(f"{thread_id} - is removed")
    thread_id = random.randint(0, 10000)
    calculation_threads[thread_id] = CalculationThread(thread_id, calculation_results)
    return {'task_id': thread_id, 'exception': ''}

@app.route('/api/v1.0/results/<int:thread_id>')
#@auth.login_required
def api_results(thread_id):
    global calculation_results
    print('results are requested')
    if thread_id in calculation_results:
        results = calculation_results[thread_id]
        return jsonify({'task_id': thread_id, 'results': results, 'exception': ''})
    else:
        return jsonify({'task_id': thread_id, 'results': '', 'exception': 'No such results!'})
    
@app.route('/api/v1.0/progress/<int:thread_id>')
#@auth.login_required
def api_progress(thread_id):
    global calculation_threads
    if thread_id in calculation_threads:
        thread = calculation_threads[thread_id]
        if not thread.is_alive() and not thread.started:
            thread.start()
        return jsonify({'task_id': thread_id, 'progress': thread.progress, 'finished': thread.finished, 'exception': ''})
    else:
        return jsonify({'task_id': thread_id, 'exception': 'Wrong task_id!'})

#########################################################################

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5003, debug=True)

'''

login_manager = LoginManager()
login_manager.init_app(app)

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)

    def verify_password(self, password):
        return self.password == password

    def generate_auth_token(self, expires_in = 600):
        return jwt.encode(
            {'id': self.id, 'exp': time.time() + expires_in},
            app.config['SECRET_KEY'], algorithm = 'HS256')

    @staticmethod
    def verify_auth_token(token):
        try:
            data = jwt.decode(token,
                              app.config['SECRET_KEY'],
                              algorithms=['HS256'])
        except:
            return
        return User.query.get(data['id'])

db.init_app(app)
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    user = None
    token = request.headers.get('Authorization')
    if token:
        user = User.verify_auth_token(token)
    if not user:
        user = User.query.filter_by(username = username).first()
        if not user or not user.verify_password(password):
            return False
    g.user = user
    return True

@app.route('/api/v1.0/register/', methods=['POST'])
def register():
    try:
        args = request.get_json()
        name = args.get('name')
        pwd = args.get('password')
        user = User.query.filter_by(username=name).first()
        if user:
            return jsonify('Username already registered'), 201
        user = User(username = name, password = pwd)
        db.session.add(user)
        db.session.commit()
        return jsonify({'name': user.username }), 201
    except Exception as e:
        return jsonify({'exception': str(e)}), 400
        
@app.route('/api/v1.0/login/', methods=['POST'])
def login():
    try:
        args = request.get_json()
        name = args['name']
        pwd = args['password']
        user = User.query.filter_by(username=name).first()
        if not user:
            return jsonify('User is not registered'), 400
        if user.password == pwd:
            login_user(user)
            return jsonify({'name': user.username }), 200
        else:
            return jsonify('Password is incorrect'), 400
    except Exception as e:
        return jsonify({'exception': str(e)}), 400

@app.route('/api/v1.0/get_token/')
@auth.login_required
def get_token():
    try: 
        token = g.user.generate_auth_token()
        return jsonify({'token': token})
    except Exception as e:
        return jsonify({'exception': str(e)}), 400

@app.route('/api/v1.0/logout/', methods=['POST'])
@auth.login_required
def logout():
    try: 
        logout_user()
        return jsonify('Logged out'), 200
    except Exception as e:
        return jsonify({'exception': str(e)}), 400
'''
pass