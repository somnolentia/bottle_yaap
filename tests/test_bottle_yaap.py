#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import pytest
from bottle_yaap import (create_tables, atomic, create_user, create_usergroup, 
                         remove_user, remove_usergroup, update_user,
                         get_usergroups)


@pytest.fixture
def dbfile(tmpdir):
    dbfile = str(tmpdir.join('test.db'))
    with atomic(dbfile) as cursor:
        create_tables(cursor)
    return dbfile 


def test_create_user(dbfile):
    with atomic(dbfile) as cursor:
        create_user(cursor, username='pieter', password='123abc', email='p@i.org')

    with atomic(dbfile) as cursor:
        r = cursor.execute(
            "SELECT username FROM users WHERE username = 'pieter'"
        )
        assert r.fetchone()[0] == 'pieter'


def test_create_usergroup(dbfile):
    with atomic(dbfile) as cursor:
        create_user(cursor, username='pieter', password='123abc', email='p@i.org')

    with atomic(dbfile) as cursor:
        create_usergroup(cursor, 'pieter', 'testers')
        usergroups = cursor.execute("SELECT * FROM usergroups").fetchall()
        assert len(usergroups) == 1


def test_create_user_with_groups(dbfile):
    with atomic(dbfile) as cursor:
        create_user(cursor, username='pieter', password='123abc', email='p@i.org',
                 groups=['abc', '123'])

    with atomic(dbfile) as cursor:
        usergroups = cursor.execute("SELECT * FROM usergroups").fetchall()
        assert len(usergroups) == 2


def test_remove_user(dbfile):
    with atomic(dbfile) as cursor:
        create_user(cursor, username='pieter', password='123abc', 
                 email='p@i.org', groups=['testers', 'happy'])

    with atomic(dbfile) as cursor:
        usergroups = cursor.execute("SELECT * FROM usergroups").fetchall()
        assert len(usergroups) == 2
        remove_user(cursor, 'pieter')

    with atomic(dbfile) as cursor:
        r = cursor.execute("SELECT username FROM users WHERE userid = ?",
                           ('pieter',))
        assert r.fetchone() is None
        usergroups = cursor.execute("SELECT * FROM usergroups").fetchall()
        assert len(usergroups) == 0


def test_remove_usergroup(dbfile):
    with atomic(dbfile) as cursor:
        create_user(cursor, username='pieter', password='123abc', email='p@i.org',
                 groups=['testers', 'happy'])

    with atomic(dbfile) as cursor:
        usergroups = cursor.execute("SELECT * FROM usergroups").fetchall()
        assert len(usergroups) == 2
        remove_usergroup(cursor, 'pieter', 'happy')
        usergroups = cursor.execute("SELECT * FROM usergroups").fetchall()
        assert len(usergroups) == 1


def test_update_user(dbfile):
    with atomic(dbfile) as cursor:
        create_user(cursor, username='pieter', password='123abc', email='p@i.org',
                 groups=['testers', 'happy'])

    with atomic(dbfile) as cursor:
        # test setting username
        update_user(cursor, 'pieter', 'username', 'tester')
        assert cursor.execute("SELECT * FROM users WHERE username = 'tester'"
                              ).fetchone()
        # test setting email
        update_user(cursor, 'tester', 'email', 'pi@tasty.be')
        assert cursor.execute(
            "SELECT * FROM users WHERE email = 'pi@tasty.be'"
        ).fetchone()
        # test setting pw
        update_user(cursor, 'tester', 'password', 'pi')
        assert cursor.execute("SELECT password FROM users"
                              ).fetchone()[0].startswith('$argon2')
        # test setting invalid attr
        with pytest.raises(ValueError):
            update_user(cursor, 'tester', 'whatever', 'stuff')

        # test setting usergroups
        update_user(cursor, 'tester', 'groups', ['a', 'b', 'c'])
        assert get_usergroups(cursor, 'tester') == set(['a', 'b', 'c']) 
