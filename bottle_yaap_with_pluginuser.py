#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
Yet Another Auth Plugin (for Bottle).

Lightweight, persists/shares sessions/users via Sqlite database.
"""
import bottle
import urllib
from bottle import request, response, abort, view, redirect
from peewee import (Model, CharField, ForeignKeyField, DateTimeField,
                    SqliteDatabase, DoesNotExist, IntegrityError)
from playhouse.fields import ManyToManyField
from shortuuid import uuid
from datetime import datetime, timedelta
from passlib.context import CryptContext
from marshmallow import Schema, fields, validate
from bottle_cors import CorsPlugin
# crypt
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
# session configuration
COOKIE_KEY = "lu_k"
COOKIE_SECRET = "alle apen apen apen na"
COOKIE_EXPIRATION = 3600
LOGIN_URL = "{}/login/?from_url={}"
LOGOUT_URL = "{}/logout/?from_url={}"


#########
# MODEL #
#########
db = SqliteDatabase(None)


class DM(Model):
    class Meta:
        database = db


class User(DM):
    username = CharField(unique=True)
    email = CharField(unique=True)
    password = CharField(null=True)
    PluginUser = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__pu = None

    @property
    def session(self):
        # peewee does not support one-to-one
        try:
            return self._session.get()
        except DoesNotExist:
            return None

    @property
    def logged_in(self):
        if self.session:
            # also make sure session has not expired
            td = datetime.utcnow() - self.session.accessed
            seconds_passed = td / timedelta(seconds=1)
            if seconds_passed < COOKIE_EXPIRATION:
                # reset timer
                self.session.accessed = datetime.utcnow()
                self.session.save()
                return True
        return False

    def has_group(self, groups):
        """groups is a set"""
        # check whether is member of at least one group of groups
        if set([g.name for g in self.groups]).intersection(groups):
            return True
        return False

    @property
    def pu(self):
        if not self.__pu and self.PluginUser:
            # d = defaults for creating a new PluginUser
            d = {'email': self.email}
            pu, created = self.PluginUser.get_or_create(
                email=self.email, defaults=d
            )
            self.__pu = pu
        return self.__pu


class UserSchema(Schema):
    """marshmallow userschema used to validate user data"""
    username = fields.Str(required=True,
                          validate=validate.Length(min=1, max=30))
    password = fields.Str(load_only=True, required=True,
                          validate=validate.Length(min=1, max=100))


class Group(DM):
    name = CharField(unique=True)
    users = ManyToManyField(User, related_name='groups')


class Session(DM):
    user = ForeignKeyField(User, primary_key=True, related_name="_session")
    key = CharField(default=uuid, unique=True)
    accessed = DateTimeField(default=datetime.utcnow)


class LoginError(Exception):
    pass


class AuthPlugin(object):
    ''' Session based access control plugin.'''

    name = 'auth'
    api = 2

    def __init__(self, dbfile=':memory:', location=''):
        self.dbfile = dbfile
        self.location = location
        self.login_page = None
        self.logout_page = None
        self.User = User
        self.db = db

    def setup(self, app):
        self.app = app
        db.init(self.dbfile)
        create_tables()  # fails silently

    def _set_login_logout(self):
        from_url = urllib.parse.quote_plus(request.url)
        # lang = self.i18n.lang
        self.login_page = LOGIN_URL.format(self.location, from_url)
        self.logout_page = LOGOUT_URL.format(self.location, from_url)
        # if lang:
        #     lang = "&lang={}".format(lang)
        #     self.login_page += lang 
        #     # self.logout_page += lang
        bottle.BaseTemplate.defaults['login_page'] = self.login_page
        bottle.BaseTemplate.defaults['logout_page'] = self.logout_page

    def apply(self, callback, context):
        def wrapper(*args, **kwargs):
            # connect to database
            # db.connect() <= seems to lead to problems sometimes
            db.get_conn()
            # provide login/logout links to template
            self._set_login_logout()
            # check whether authorization is needed
            groups = context.config.get('auth', None)
            user = self._get_user()
            if type(groups) == set and not user:
                # need to authorize but not logged in: redirect to login
                redirect(self.login_page, 302)
            elif groups and not user.has_group(groups):
                # logged in but not authorized
                abort(403)
            else:
                # no authorization needed or user has authorization
                request.user = user
                bottle.BaseTemplate.defaults['user'] = user
            # close db connection
            if not db.is_closed():
                db.close()
            # render route as normal
            return callback(*args, **kwargs)
        return wrapper

    # @property
    # def i18n(self):
    #     """check whether an i18n plugin exists, if it does return its lang"""
    #     # pass desired language as param to yaac app
    #     for p in request.route.all_plugins():
    #         if p.name == 'i18n':
    #             return p
    #     i18n = namedtuple('DummyI18N', '_ lang')
    #     return i18n(lambda msg: msg, None)

    def _get_user(self):
        """return the currently logged in user associated with this request"""
        session_key = request.get_cookie(COOKIE_KEY, secret=COOKIE_SECRET)
        try:
            session = Session.get(Session.key == session_key)
        except Session.DoesNotExist:
            print("No session for sess_id: %s" % session_key)
        else:
            # make sure session has not expired
            if session.user.logged_in:
                return session.user

    def login(self, username, password):
        """try logging in user, raise ValueError if unsuccessful"""
        # check whether user + pw match
        try:
            user = User.get(User.username == username)
        except User.DoesNotExist:
            print("Could not find username '%s' in DB." % username)
        else:
            if pwd_context.verify(password, user.password):
                # update session
                if user.session:
                    user.session.delete_instance()
                session = Session.create(user=user)
                session.save()
                # set response cookie
                response.set_cookie(COOKIE_KEY, session.key,
                                    secret=COOKIE_SECRET, path='/')
                return
        raise LoginError('Invalid username or password.')


    def logout(self, user):
        # remove session; null stuff
        if user.session:
            user.session.delete_instance()
        request.user = None
        bottle.BaseTemplate.defaults['user'] = None
        # set response cookie
        response.set_cookie(COOKIE_KEY, '', secret=COOKIE_SECRET, path='/')

    def add_user(self, username, password):
        d = {'username': username, 'password': password}
        return User.get_or_create(username=username, defaults=d)


class AuthApp(bottle.Bottle):
    """ base AuthApp to handle common auth app functionality """
    def __init__(self, dbfile):
        super().__init__(self)
        # load and install plugin
        self._auth = AuthPlugin(dbfile=dbfile)
        self.install(self._auth)

    def do_login(self, data):
        data, validation_errors = UserSchema().load(data)
        if not validation_errors:
            # check the credentials 
            self._auth.login(data['username'], data['password'])

    def do_logout(self):
        self._auth.logout(request.user)


class JsonApp(AuthApp):
    """ Auth app that receives json and answers 'restfully' """
    def __init__(self, dbfile=':memory:', cors=None):
        super().__init__(dbfile)
        if cors:
            self.install(CorsPlugin('/', origin=cors))

        @self.post('/login/')
        def login():
            try: 
                self.do_login(request.json)
            except LoginError:
                response.status = 401
                ok = False
            else:
                ok = True
            return {'ok': ok}


        @self.post('/logout/', method=['POST'])
        def logout():
            self.do_logout()


class HtmlApp(AuthApp):
    """ Auth app providing classic HTML form interface """
    def __init__(self, dbfile=':memory:'):
        super().__init__(dbfile)

        @self.route('/login/', method=['GET', 'POST'])
        @view('login')
        def login():
            error = None
            if request.method == 'POST':
                error = 'Invalid username or password.'
                # validate formdata
                try:
                    self.do_login(request.forms)
                except LoginError as e:
                    # post request + error => render form with error shown
                    error = str(e)
                else:
                    # redirect to from_url
                    from_url = getattr(request.params, 'from_url') or '/user/'
                    redirect(from_url)
            # get request => render form
            return {'error': error}

        @self.post('/logout/')
        @view('base')
        def logout():
            self.do_logout()
            # response 
            from_url = getattr(request.params, 'from_url') or None
            if from_url:
                redirect(from_url)
            return {'base': '<p>' + 'Logged out successfully.' + '</p>',
                    'title': 'Logged out'}

        @self.get('/user/', auth=set())
        @view('user')
        def user():
            # implement edit username/email
            return {}

        @self.get('/test/', auth={'admin'})
        @view('base')
        def test():
            return {'base': 'Some stuff', 'title': 'stuff'}


def create_tables():
    db.create_tables([User, Session, Group, Group.users.get_through_model()],
                     True)
    # create langs 
    users = [
        {'username': 'pieter',
         'email': 'pieter@luminix.fi',
         'password': pwd_context.hash('somepass')},
        {'username': 'tester',
         'email': 'test@luminix.fi',
         'password': pwd_context.hash('pass')}
    ]
    with db.atomic():
        try:
            User.insert_many(users).execute()
        except IntegrityError:
            return
    g = Group.create(name='admin')
    g.users.add(User.get(username='pieter'))


if __name__ == '__main__':
    bottle.debug(True)
    # we use the htmlapp as the root and mount json to /api/
    app = HtmlApp('test.db') 
    jsonapp = JsonApp('test.db', cors='http://127.0.0.1:8000')
    app.mount('/api/', jsonapp)
    # i18n
    # i18n = I18NPlugin(langs=[('en', 'english'), ('fi', 'suomi')], user=None)
    # auth
    bottle.run(app, reloader=True, port="8082")
