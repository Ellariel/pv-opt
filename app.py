from main import *
from flask import *
from flask_login import *
#from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from flask_httpauth import HTTPBasicAuth
#from flask.ext.login import LoginManager
from flask import render_template
from werkzeug.utils import secure_filename
#from werkzeug.datastructures import FileStorage
import jwt

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.sqlite3'
app.config['SECRET_KEY'] = 'secret_key'
app.config['UPLOAD_FOLDER'] = './uploaded'
app.config['MAX_CONTENT_PATH'] = 1000000
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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

@app.route('/api/v1.0/upload')
#@auth.login_required
def upload_file():
   return render_template('./upload.html')
	
@app.route('/api/v1.0/uploader', methods = ['GET', 'POST'])
#@auth.login_required
def uploader_file():
   if request.method == 'POST':
      f = request.files['file']
      f.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f.filename)))
      return 'File uploaded successfully'

#########################################################################

@app.route('/api/v1.0/create_agent', methods=['POST'])
@auth.login_required
def api_create_agent():
    try:
        args = request.get_json()
        args['user_id'] = g.user.get_id()
        print(args)
        result = create_agent(**args)
        if type(result) == str:
            return jsonify(result), 201
        return jsonify({'id': result._name,
                        'name': result.label[0],
                        'description': result.comment[0],
                        'karma': result.hasKarma,
                        'predictions': [x._name for x in result.hasPrediction],
                        'created_by': result.createdBy,
                        'is_user': result.isUser}), 201
    except Exception as e:
        return jsonify({'exception': str(e)}), 400

@app.route('/api/v1.0/get_agent', methods=['GET'])
def api_get_agent():
    try:
        args = request.args
        result = get_agent(**args)
        if not result:
            return jsonify('Agent is not found'), 201
        return jsonify({'id': result._name,
                        'name': result.label[0],
                        'description': result.comment[0],
                        'karma': result.hasKarma,
                        'predictions': [x._name for x in result.hasPrediction],
                        'created_by': result.createdBy,
                        'is_user': result.isUser}), 201
    except Exception as e:
        return jsonify({'exception': str(e)}), 400

@app.route('/api/v1.0/create_subject', methods=['POST'])
@auth.login_required
def api_create_subject():
    try:
        args = request.get_json()
        args['user_id'] = g.user.get_id()
        result = create_subject(**args)
        if type(result) == str:
            return jsonify(result), 201
        return jsonify({'id': result._name,
                        'name': result.label[0],
                        'url': result.isDefinedBy[0],
                        'created_by': result.createdBy}), 201
    except Exception as e:
        return jsonify({'exception': str(e)}), 400

@app.route('/api/v1.0/get_subject', methods=['GET'])
def api_get_subject():
    try:
        args = request.args
        result = get_subject(**args)
        if not result:
            return jsonify('Subject is not found'), 201
        return jsonify({'id': result._name,
                        'name': result.label[0],
                        'url': result.isDefinedBy[0],
                        'created_by': result.createdBy}), 201
    except Exception as e:
        return jsonify({'exception': str(e)}), 400

@app.route('/api/v1.0/create_domain', methods=['POST'])
@auth.login_required
def api_create_domain():
    try:
        args = request.get_json()
        args['user_id'] = g.user.get_id()
        result = create_domain(**args)
        if type(result) == str:
            return jsonify(result), 201
        return jsonify({'id': result._name,
                        'name': result.label[0],
                        'url': result.hasURL,
                        'created_by': result.createdBy}), 201
    except Exception as e:
        return jsonify({'exception': str(e)}), 400

@app.route('/api/v1.0/get_domain', methods=['GET'])
def api_get_domain():
    try:
        args = request.args
        result = get_domain(**args)
        if not result:
            return jsonify('Domain is not found'), 201
        return jsonify({'id': result._name,
                        'name': result.label[0],
                        'url': result.hasURL,
                        'created_by': result.createdBy}), 201
    except Exception as e:
        return jsonify({'exception': str(e)}), 400

@app.route('/api/v1.0/create_prediction', methods=['POST'])
@auth.login_required
def api_create_prediction():
    try:
        args = request.get_json()
        args['user_id'] = g.user.get_id()
        result = create_prediction(**args)
        if type(result) == str:
            return jsonify(result), 201
        return jsonify({'id': result._name,
                        'name': result.label[0],
                        'agent': result.hasAgent._name,
                        'subject': result.hasSubject._name,
                        'date': result.hasDate,
                        'outcome': result.hasPredictedOutcome,
                        'created_by': result.createdBy}), 201
    except Exception as e:
        return jsonify({'exception': str(e)}), 400

@app.route('/api/v1.0/get_prediction', methods=['GET'])
def api_get_prediction():
    try:
        args = request.args
        result = get_prediction(**args)
        if not result:
            return jsonify('Prediction is not found'), 201
        return jsonify({'id': result._name,
                        'name': result.label[0],
                        'agent': result.hasAgent._name,
                        'subject': result.hasSubject._name,
                        'date': result.hasDate,
                        'predicted_outcome': result.hasPredictedOutcome,
                        'real_outcome': result.hasRealOutcome,
                        'created_by': result.createdBy}), 201
    except Exception as e:
        return jsonify({'exception': str(e)}), 400

@app.route('/api/v1.0/update_prediction', methods=['POST'])
@auth.login_required
def api_update_prediction():
    try:
        args = request.get_json()
        result = update_prediction(**args)
        if type(result) == str:
            return jsonify(result), 201
        return jsonify({'id': result._name,
                        'name': result.label[0],
                        'karma': result.hasKarma}), 201
    except Exception as e:
        return jsonify({'exception': str(e)}), 400

if __name__ == "__main__":
    app.run(debug=True)
