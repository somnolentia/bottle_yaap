#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
Yet Another Auth Plugin (for Bottle).

Users and matching sessions stored in Sqlite DB.
"""
import sqlite3
from contextlib import contextmanager
from collections import namedtuple
from urllib.parse import quote_plus
from secrets import token_urlsafe
from passlib.context import CryptContext
from passlib.hash import argon2
import bottle
from bottle import request, response, abort, view, redirect, template


# TODO: implement AuthPlugin.create AuthPlugin.update and AuthPlugin.delete
# TODO: logging
# TODO: documentation

# passlib crypt config
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
# user data container
User = namedtuple('User', ['username', 'email', 'groups'])


# DATABASE
@contextmanager
def atomic(dbfile):
    connection = sqlite3.connect(dbfile)
    connection.execute('PRAGMA foreign_keys = ON;')
    cursor = connection.execute('BEGIN TRANSACTION')
    yield cursor
    try:
        connection.commit()
    except connection.Error:
        connection.rollback()
    finally:
        connection.close()


def create_tables(cursor):
    """ create user, usergroup and group tables """
    cursor.execute("""
        CREATE TABLE users(
            userid      INTEGER PRIMARY KEY,
            username    TEXT NOT NULL,
            password    TEXT NOT NULL,
            email       TEXT NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE groups(
            groupid     INTEGER PRIMARY KEY,
            name        TEXT NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE usergroups(
            userid     INTEGER,
            groupid    INTEGER,
            PRIMARY KEY (userid, groupid)
            FOREIGN KEY (userid) REFERENCES users (userid)
            ON DELETE CASCADE ON UPDATE NO ACTION
            FOREIGN KEY (groupid) REFERENCES groups (groupid)
            ON DELETE CASCADE ON UPDATE NO ACTION
        );
    """)
    cursor.execute("""
        CREATE TABLE settings(
            key     TEXT PRIMARY KEY,
            value
        );
    """)
    cursor.execute("""
        CREATE TABLE sessions(
            userid   INTEGER PRIMARY KEY,
            key      TEXT NOT NULL,
            started  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (userid) REFERENCES users (userid)
            ON DELETE CASCADE ON UPDATE NO ACTION
        );
    """)
    cursor.execute("CREATE UNIQUE INDEX idx_groups_name ON groups (name)")
    cursor.execute(
        "CREATE UNIQUE INDEX idx_users_username ON users (username)"
    )


def get_conf(cursor):
    conf = {
        'allow_registration': None,
        'cookie_key': 'bottle_yaap',
        'cookie_secret': 'sneakyyaapi'
    }
    for key, value in cursor.execute("SELECT key, value FROM settings"):
        conf[key] = value
    return conf


def get_userid(cursor, username):
    try:
        return next(cursor.execute(
            "SELECT userid FROM users WHERE username = ?", (username,),
        ))[0]
    except TypeError: 
        raise LookupError(f"No user with username {username!r}")


def get_email(cursor, username):
    try:
        return next(cursor.execute(
            "SELECT email FROM users WHERE username = ?",
            (username,))
        )[0]
    except StopIteration:
        raise LookupError(f"No user with username {username!r}")


def get_usergroups(cursor, username):
    groups = cursor.execute("""
        SELECT name
        FROM groups
        INNER JOIN usergroups ON usergroups.groupid = groups.groupid
        INNER JOIN users ON users.userid = usergroups.userid
        WHERE users.username = ?
        """, (username,)
    )
    return {g[0] for g in groups}


def get_user(cursor, username):
    return User(username, get_email(cursor, username),
                get_usergroups(cursor, username))


def create_user(cursor, username, password, email, groups=None):
    """ create a user, return user_id """
    groups = groups or []
    cursor.execute(
        "INSERT INTO users ('username', 'password', 'email') VALUES(?, ?, ?)",
        (username, argon2.hash(password), email)
    )
    for group in groups:
        create_usergroup(cursor, username, group)


def create_usergroup(cursor, username, group):
    userid = get_userid(cursor, username)

    try:
        groupid = next(cursor.execute(
            "SELECT groupid FROM groups WHERE name = ?", (group,)))[0]
    except StopIteration:
        cursor.execute(
            "INSERT INTO groups ('name') VALUES (?)", (group,)
        )
        groupid = cursor.lastrowid

    # finally create usergroup
    cursor.execute(
        "INSERT INTO usergroups ('userid', 'groupid') VALUES(?, ?)",
        (userid, groupid)
    )


def remove_user(cursor, username):
    """ remove the user and all groups without a user """
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    cursor.execute("""
        DELETE
        FROM groups
        WHERE NOT EXISTS(
            SELECT
                NULL
            FROM
                usergroups ug
            WHERE
                ug.groupid = groupid
            )
        """)


def remove_usergroup(cursor, username, group):
    cursor.execute("""
        DELETE
        FROM usergroups
        WHERE
            userid = (SELECT userid FROM users WHERE username = ?)
            AND
            groupid = (SELECT groupid FROM groups WHERE name = ?)
    """, (username, group))


def update_user(cursor, username, attr, value):
    """
    Update user username, email, password or groups.

    Note: value has to be of correct type, i.e. a set for groups or a string 
    for username/password.
    """
    if attr not in ['username', 'password', 'email', 'groups']:
        raise ValueError(f"{attr!r} is not a valid user attribute")
    if attr == 'password':
        value = argon2.hash(value)
    elif attr == 'groups':
        current = get_usergroups(cursor, username)
        for group in current.difference(value):
            remove_usergroup(cursor, username, group)
        for group in value.difference(current):
            create_usergroup(cursor, username, group)
        return 

    cursor.execute(f"""
        UPDATE users
        SET
            {attr} = ?
        WHERE
            username = ?
    """, (value, username))


def configure(cursor, key, value):
    """ set YAAP configuration option """
    allowed_keys = {'registration', 'cookie_key', 'cookie_secret'}
    if key not in allowed_keys:
        raise ValueError(f"{key!r} is not a valid settings key")

    cursor.execute(
        "REPLACE INTO settings ('key', 'value') VALUES (?, ?)",
        (key, value)
    )


def logout_user(cursor, username):
    cursor.execute("""
        DELETE FROM sessions
        WHERE
            userid = (SELECT userid FROM users WHERE username = ?)
        """, (username,))


def login_user(cursor, username):
    """ create new session for user with username, return session key """
    userid = get_userid(cursor, username)
    key = token_urlsafe()
    cursor.execute(
        "REPLACE INTO sessions ('userid', 'key') VALUES (?, ?)",
        (userid, key)
    )
    return key


#########
# MODEL #
#########
class AuthPlugin(object):
    ''' Session based access control plugin.'''

    name = 'auth'
    api = 2

    def __init__(self,):
        self.app = None
        self.conf = None
        self.tpls = bottle.BaseTemplate.defaults

    def setup(self, app):
        self.app = app
        self.conf = app.config
        # grab settings from app config
        self.conf.setdefault('auth.dbfile', 'yaap.db')
        try:
            with atomic(self.conf['auth.dbfile']) as cursor:
                conf = get_conf(cursor)
        except sqlite3.OperationalError:
            raise ValueError("You need to init the database or tell the yaap "
                             "plugin where to find your database by specifying"
                             " auth.dbfile in the bottle app config")

        self.conf.setdefault('auth.allow_registration',
                             conf['allow_registration'])
        self.conf.setdefault('auth.cookie_secret', conf['cookie_secret'])
        self.conf.setdefault('auth.cookie_key', conf['cookie_key'])
        self.conf.setdefault('auth.login', '/login/')
        self.conf.setdefault('auth.logout', '/logout/')
        self.conf.setdefault('auth.register', '/register/')
        self.conf.setdefault('auth.reset', '/reset/')
        self.conf.setdefault('auth.user', '/user/')

        self.tpls['auth_user'] = self.conf['auth.user']

    def get_user(self):
        """return the currently logged in user associated with this request"""
        session_key = request.get_cookie(
            self.conf['auth.cookie_key'],
            secret=self.conf['auth.cookie_secret']
        )
        if session_key:
            with atomic(self.conf['auth.dbfile']) as cursor:
                try:
                    username, email = next(cursor.execute("""
                        SELECT username, email
                        FROM sessions
                        INNER JOIN users ON users.userid = sessions.userid
                        WHERE sessions.key = ?
                        AND sessions.started <= (SELECT
                                                 datetime('now', '+3 hour'))
                        """, (session_key,)))
                except StopIteration:
                    return
                else:
                    return User(username, email, get_usergroups(cursor, 
                                                                username))

    def login(self, username, password):
        """try logging in user, raise ValueError if unsuccessful"""
        # check whether user + pw match
        with atomic(self.conf['auth.dbfile']) as cursor:
            try:
                pw_hash = next(cursor.execute(
                    "SELECT password FROM users WHERE username = ?",
                    (username,)))[0]
            except StopIteration:
                pass
            else:
                if pwd_context.verify(password, pw_hash):
                    session_key = login_user(cursor, username)
                    response.set_cookie(
                        self.conf['auth.cookie_key'], session_key,
                        secret=self.conf['auth.cookie_secret'], path='/'
                    )
                    return
        raise ValueError('Invalid username or password.')

    def logout(self):
        """ log out currently logged in user """
        user = self.get_user()
        if user:
            with atomic(self.conf['auth.dbfile']) as cursor:
                logout_user(cursor, user.username)
        request.user = self.tpls['user'] = None
        response.set_cookie(self.conf['auth.cookie_key'], '',
                            secret=self.conf['auth.cookie_secret'], path='/')

    def create(self, username, password, email):
        """ create/register a new user """
        pass

    def update(self, username, attr, value):
        """ update user information """
        pass

    def delete(self, username, password, email):
        """ delete user """
        pass

    def apply(self, callback, context):
        """ apply YAAP magic to the route """
        def wrapper(*args, **kwargs):
            request.user = self.tpls['user'] = self.get_user()

            # provide login/logout links to bottle templates
            if request.params.get('from_url'):
                url = request.params.get('from_url')
            else:
                url = request.url
            from_url = '?from_url=%s' % quote_plus(url)
            self.tpls['auth_login'] = self.conf['auth.login'] + from_url
            self.tpls['auth_logout'] = self.conf['auth.logout'] + from_url
            if self.conf['auth.allow_registration']:
                self.tpls['auth_register'] = (self.conf['auth.register']
                                              + from_url)

            # check whether authorization is needed
            groups = context.config.get('auth', None)
            if groups is not None:
                if not request.user:
                    # need to authorize but not logged in: redirect to login
                    redirect(self.tpls['auth_login'], 302)
                elif groups and not groups.intersection(request.user.groups):
                    # logged in but not authorized
                    abort(403, 'You do not have sufficient access rights.')

            # render route as normal
            return callback(*args, **kwargs)
        return wrapper


def json_app(config):
    """
    Example json REST API app.

    :config: dict
    """
    app = bottle.Bottle()
    app.config.load_dict(config)
    auth = AuthPlugin()
    app.install(auth)

    @app.post('/login/')
    def login():
        username = request.json['username']
        password = request.json['password']
        try: 
            auth.login(username, password)
        except ValueError:
            response.status = 401

    @app.post('/logout/', method=['POST'])
    def logout():
        auth.logout()

    return app


def html_app(config):
    """
    Example html app.

    :config: dict
    """
    app = bottle.Bottle()
    app.config.load_dict(config)
    auth = AuthPlugin()
    app.install(auth)

    @app.get('/login/')
    @view(TPL['base'])
    def login_get():
        if request.user:
            return {'title': 'Sign in', 'body': template(TPL['logout']),
                    'aside': template('You are already logged in as'
                                      " '{{user.username}}'.")}
        else:
            return {'title': 'Sign in', 'body': template(TPL['login'])}

    @app.post('/login/')
    @view(TPL['base'])
    def login_post():
        try:
            auth.login(request.forms.username, request.forms.password)
        except ValueError as e:
            # unsuccessful login => render form with error shown
            return {'title': 'Sign in', 'error': True, 'aside': str(e),
                    'body': template(TPL['login'])}
        else:
            # successful login => redirect to from_url
            redirect(getattr(request.params, 'from_url',
                             auth.conf['auth.user']))

    @app.post('/logout/')
    @view(TPL['base'])
    def logout_post():
        auth.logout()
        # response 
        from_url = getattr(request.params, 'from_url', None)
        if from_url:
            redirect(from_url)
        return {'title': 'Logged out', 'aside': 'Logged out successfully.',
                'body': template(TPL['login'])}

    @app.get('/logout/')
    @view(TPL['base'])
    def logout_get():
        if not request.user:
            return {'title': 'You are currently not logged in.',
                    'body': template(TPL['login'])}
        return {'title': 'Confirm log out', 'body': template(TPL['logout'])}

    @app.get('/user/', auth=set())
    @view(TPL['base'])
    def user():
        # implement edit username/email
        return {'title': 'Profile', 'body': template(TPL['user'])}

    return app


TPL = {
    'base': """ 
% setdefault('aside', None)
% setdefault('error', False)
<!DOCTYPE html>
<html><head> <meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{title}}</title>
<link rel="stylesheet" 
href="https://unpkg.com/purecss@0.6.2/build/pure-min.css" 
integrity="sha384-UQiGfs9ICog+LwheBSRCt1o5cbyKIHbwjWscjemyBMT9YCUMZffs6UqUTd0hObXD" 
crossorigin="anonymous">
<!--[if lte IE 8]>
    <link rel="stylesheet" 
    href="https://unpkg.com/purecss@0.6.2/build/grids-responsive-old-ie-min.css">
<![endif]-->
<!--[if gt IE 8]><!-->
    <link rel="stylesheet" 
    href="https://unpkg.com/purecss@0.6.2/build/grids-responsive-min.css">
<!--<![endif]-->
<style>
body {max-width: 48em; margin: 1em auto 2em auto; background-color: #fff; 
color: #777; line-height: 1.6;}
h1, h2, h3, h4, h5, h6 {font-weight: bold; color: rgb(75, 75, 75);}
h3 {font-size: 1.25em;}
h4 {font-size: 1.125em;}
a {color: #3b8bba; /* block-background-text-normal */ text-decoration: none;}
dt {font-weight: bold;}
dd {margin: 0 0 10px 0;}
aside {
    background: #4CAF50; /* same color as selected state on site menu */
    margin: 1em 0;
    padding: 0.3em 1em;
    border-radius: 3px;
    color: #fff;
}
    aside a, aside a:visited {
        color: inherit;
        border-bottom: 1px solid;
    }
.green {color: #4CAF50;}
.yellow {color: yellow;}
.bg-yellow {background-color: #ffd;}
.red {color: rgb(233, 50, 45);}
.bg-red {background-color: rgb(233, 50, 45);}
</style>
</head>
<body><h1>{{title}}</h1>
%if aside:
  <aside {{!'class="bg-red"' if error else ''}}>{{aside}}</aside>
%end
{{!body}}</body></html>
""",
    'user': """
 <dl>
  <dt>Username</dt>
  <dd>{{user.username}}</dd>
  <dt>Email</dt>
  <dd>{{user.email}}</dd>
</dl> 
<form class="pure-form pure-form-aligned" method="post"
action="{{auth_logout}}">
    <fieldset>
        <input type="submit" class="pure-button pure-button-primary"
        value="log out"/> 
    </fieldset>
</form>
""",
    'login': """
<form class="pure-form pure-form-aligned" method="post"
action="{{auth_login}}">
<fieldset>
    <legend>{{'Please sign in to continue'}}:</legend>
    <input name="username" type="text" placeholder="{{'Username'}}" value=""/>
    <input name="password" type="password" placeholder="{{'Password'}}"
    value=""/>
    <input type="submit" class="pure-button pure-button-primary"
    value="{{'Sign in'}}"/> 
</fieldset></form>
""",
    'logout': """
<form class="pure-form pure-form-aligned" method="post"
action="{{auth_logout}}">
    <fieldset>
        <input type="submit" class="pure-button pure-button-primary"
        value="log out"/> 
    </fieldset>
</form>
""",
    'demo': """
<ul>
<li><a href="/required/">Page with login required</a>
(visible to any logged in user)</li>
<li><a href="/special/">Page restricted to special users</a>
(visible to all users part of the 'special' group)</li>
<li><a href="{{auth_user}}">User profile</a></li>
<li><a href="{{auth_login}}">Login</a></li>
<li><a href="{{auth_logout}}">Logout</a></li>
</ul>
"""
}

try:
    import click
except ImportError:
    def cli(*args, **kwargs):
        print("Could not import click.")
else:
    @click.group()
    @click.option('--dbfile', '-db', default='yaap.db', help="database file")
    @click.pass_context
    def cli(ctx, dbfile):
        """ edit YAAP database """
        ctx.obj = dbfile

    @cli.command('init')
    @click.option('--demo/--empty', default=False)
    @click.pass_obj
    def cli_init(dbfile, demo):
        """ initialize a new YAAP sqlite database """
        with atomic(dbfile) as cursor:
            create_tables(cursor)
            if demo:
                create_user(cursor, 'tester', 'pw', 'tester@somnolentia.net')
                create_user(cursor, 'special_tester', 'pw',
                            'special_tester@somnolentia.net',
                            groups=['special'])



    @cli.command('configure')
    @click.argument('key')
    @click.argument('value')
    @click.pass_obj
    def cli_configure(dbfile, key, value):
        """ configure YAAP """
        value = None if value == 'NULL' else value
        with atomic(dbfile) as cursor:
            configure(cursor, key, value)

    @cli.command('create')
    @click.argument('username')
    @click.argument('email')
    @click.option('--password', '-pw', default=lambda: token_urlsafe(8))
    @click.option('--group', '-g', multiple=True)
    @click.pass_obj
    def cli_create(dbfile, username, email, password, group):
        """ create a new user """
        with atomic(dbfile) as cursor:
            create_user(cursor, username=username, password=password, 
                        email=email, groups=group)
        click.echo(f"Created user {username!r} with password {password!r}")

    @cli.command('remove')
    @click.argument('username')
    @click.pass_obj
    def cli_remove(dbfile, username):
        """ remove existing user """
        with atomic(dbfile) as cursor:
            remove_user(cursor, username=username)
        click.echo(f"Deleted user {username!r}")

    @cli.command('update')
    @click.argument('username')
    @click.argument('attr')
    @click.argument('value', nargs=-1)
    @click.pass_obj
    def cli_update(dbfile, username, attr, value):
        """ delete existing user """
        if attr == 'groups':
            value = set(value)
        elif not value:
            value = None
        else:
            value = value[0]

        with atomic(dbfile) as cursor:
            update_user(cursor, username, attr, value)
        click.echo(f"Updated user {username!r}")

    @cli.command('logout')
    @click.argument('username')
    @click.pass_obj
    def cli_logout(dbfile, username):
        """ log out user """
        with atomic(dbfile) as cursor:
            logout_user(cursor, username)
        click.echo(f"User {username!r} is now logged out.")

    @cli.group('show')
    @click.pass_obj
    def cli_show(dbfile):
        """ show various information """
        pass

    @cli_show.command('settings')
    @click.pass_obj
    def cli_show_settings(dbfile):
        """ show current settings """
        with atomic(dbfile) as cursor:
            print(get_conf(cursor))

    @cli.command('demo')
    @click.pass_obj
    def cli_demo(dbfile):
        """ run demo web app """
        bottle.debug(True)
        config = {'auth': {'dbfile': dbfile}}
        app = html_app(config)

        @app.get('/')
        @view(TPL['base'])
        def root():
            return {'title': 'YAAP Demo APP',
                    'aside': (
                        "Login with username 'tester' or 'special_tester'"
                        " and password 'pw'."
                    ),
                    'body': template(TPL['demo'])}

        @app.get('/required/', auth=set())
        @view(TPL['base'])
        def required():
            return {'title': template('Hey {{user.username}}!'),
                    'body': ('<p>You can see this page because you '
                             'are logged in.</p>'
                             '<p><a href="/">Go back</a></p>')}

        @app.get('/special/', auth={'special'})
        @view(TPL['base'])
        def special():
            return {'title': 'Shh!',
                    'body': ('<p>You can see this page because '
                             'you are logged in and belong to the '
                             'special group.</p>'
                             '<p><a href="/">Go back</a></p>')}

        # jsonapp = json_app(config)
        # app.mount('/api/', jsonapp)
        bottle.run(app, reloader=True, port="8000")
