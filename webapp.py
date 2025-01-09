from flask import Flask, redirect, url_for, session, request, jsonify
from flask_oauthlib.client import OAuth
#from flask_oauthlib.contrib.apps import github #import to make requests to GitHub's OAuth
from flask import render_template
from markupsafe import Markup
from bson.objectid import ObjectId

import pymongo
import os
import sys
import pprint

app = Flask(__name__)

app.debug = False #Change this to False for production

app.secret_key = os.environ['SECRET_KEY'] #used to sign session cookies
oauth = OAuth(app)
oauth.init_app(app) #initialize the app to be able to make requests for user information

#Set up GitHub as OAuth provider
github = oauth.remote_app(
    'github',
    consumer_key=os.environ['GITHUB_CLIENT_ID'], #your web app's "username" for github's OAuth
    consumer_secret=os.environ['GITHUB_CLIENT_SECRET'],#your web app's "password" for github's OAuth
    request_token_params={'scope': 'user:email'}, #request read-only access to the user's email.  For a list of possible scopes, see developer.github.com/apps/building-oauth-apps/scopes-for-oauth-apps
    base_url='https://api.github.com/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://github.com/login/oauth/access_token',  
    authorize_url='https://github.com/login/oauth/authorize' #URL for github's OAuth login
)

connection_string = os.environ["MONGO_CONNECTION_STRING"]
usersdb_name = os.environ["MONGO_DBNAME1"]
postsdb_name = os.environ["MONGO_DBNAME2"]

client = pymongo.MongoClient(connection_string)
usersdb = client[usersdb_name]
postsdb = client[postsdb_name]
mongoUsers = usersdb['User_info']
mongoPosts = postsdb['Posts']

@app.context_processor
def inject_logged_in():
    is_logged_in = 'github_token' in session #this will be true if the token is in the session and false otherwise
    return {"logged_in":is_logged_in}

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login():   
    return github.authorize(callback=url_for('authorized', _external=True, _scheme='https'))

@app.route('/logout')
def logout():
    session.clear()
    return render_template('message.html', message='You were logged out')

@app.route('/login/authorized')
def authorized():
    resp = github.authorized_response()
    if resp is None:
        session.clear()
        message = 'Access denied: reason=' + request.args['error'] + ' error=' + request.args['error_description'] + ' full=' + pprint.pformat(request.args)
    else:
        try:
            session['github_token'] = (resp['access_token'], '') #save the token to prove that the user logged in
            session['user_data']=github.get('user').data
            session['user_login']=github.get('login').data
            username = session['user_data']['login']
            user = mongoUsers.find_one({"User":username})
            if user == None:
                doc = {"User": username, "Banned":"No", "Form":"No"}
                mongoUsers.insert_one(doc)
            message='You were successfully logged in as ' + session['user_data']['login'] + '.'
            if user["Form"] == "No":
                return render_template('question.html')
        except Exception as inst:
            session.clear()
            print(inst)
            message='Unable to login, please try again.'
    return render_template('message.html', message=message)
                
@app.route('/thechatroom', methods=['GET','POST'])
def renderTheChatRoom():
    if "user_data" not in session: 
        return github.authorize(callback=url_for('authorized', _external=True, _scheme='http'))
    username = session['user_data']['login']
    user = mongoUsers.find_one({"User":username})
    if user["Form"] == "No":
        return render_template('question.html')
    if user["Banned"] == "Yes":
        return render_template('banned.html')
    posts = ""
    for doc in mongoPosts.find():
        posts += Markup("<p>" + str(doc["User"]) + ": " + str(doc["Post"]) + "</p>" + "<br>")
    return render_template('thechatroom.html', posts=posts)
    
@app.route("/createPost", methods=['GET','POST'])
def render_post():
    content = request.form['content']
    username = session['user_data']['login']
    if "Post" not in session:
        doc = {"User": username, "Post":content}
        mongoPosts.insert_one(doc)
        session["Post"] = content
    else:
        if content != session["Post"]:
            doc = {"User": username, "Post":content}
            mongoPosts.insert_one(doc)
            session["Post"] = content
    return redirect(url_for("renderTheChatRoom"))
    
@app.route("/checkQuestion", methods=['GET','POST'])
def render_questionCheck():
    username = session['user_data']['login']
    user = mongoUsers.find_one({"User":username})
    mongoUsers.update_one({"User": username}, {'$set': {"Form":"Yes"}})
    quantity = request.form['quantity']
    if quantity <= str(100000000):
        mongoUsers.update_one({"User": username}, {'$set': {"Banned":"Yes"}})
    return redirect(url_for("renderTheChatRoom"))
    
@app.route('/googleb4c3aeedcc2dd103.html')
def render_google_verification():
    return render_template('googleb4c3aeedcc2dd103.html')

@github.tokengetter
def get_github_oauth_token():
    return session['github_token']

if __name__ == '__main__':
    app.run(debug=False)