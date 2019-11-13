Bottle YAAP
###########

.. _description:

Bottle YAAP

Yet Another Authentication Plugin for bottlepy.org (session/cookie based).

Implements access restrictions based on groups. Bottle plugin created to test 
out working with SQLite without using an ORM. Also demonstrates CLI making use 
of the Click python package.

.. _contents:

.. contents::

.. _requirements:

Requirements
=============

- python >= 3.7

.. _installation:

Installation
=============

**Bottle YAAP** should be installed using pip: ::

    pip install git+https://github.com/somnolentia/bottle_yaap.git

Install the optional requirements (cli or dev): ::

    pip install bottle_yaap cli

**Note that Bottle YAAP has only been tested on Linux**

.. _usage:

Usage
=====

Easiest way to get started is to run the demo app. This requires installing the 
optional cli requirement as mentioned in the installation instructions: ::

    pip install bottle_yaap cli

Create a directory to store the SQLite database, change into the directory and 
initialize the database with demo data: ::

    bottle-yaap init --demo

Then run the provided demo app on localhost:8000: ::

    bottle-yaap demo

To check out the other command line options run: ::
  
    bottle-yaap --help

To create another user belonging to the 'special' group with password 'pw': ::

    bottle-yaap create tester2 tester2@somedomain.net -pw pw -g special

Test out your newly created user by logging in and then checking the links.



Configuration
-------------

None at the moment.

.. _bugtracker:

Bug tracker
===========

If you have any suggestions, bug reports or
annoyances please report them to the issue tracker
at https://github.com/somnolentia/bottle_yaap/issues

.. _contributing:

Contributing
============

Development of Bottle YAAP happens at: 
https://github.com/somnolentia/bottle_yaap



License
=======

Licensed under the `MIT license`_.

.. _links:

.. _MIT license: http://www.linfo.org/mitlicense.html
.. _somnolentia: https://github.com/somnolentia
