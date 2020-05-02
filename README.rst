==========
ShellQuery
==========

Ever piped together some awful combination of ``grep``, ``sed``, ``awk``, ``sort`` to run a quick-and-dirty analysis? Now you can do those same awful transformations using SQL! Many studies |weaselwords|_ have shown that the aforementioned tools are difficult to use, and moreover, most people prefer SQL |citationneeded|_.

ShellQuery (``shq``) is a command line tool for running SQL against plain text. It lets you express logic in SQL instead of stringing together bash commands.

Usage
=====

Suppose you're running a web server, and you want to get some quick stats on your traffic. Your logs look something like the following::

    [pid: 2302|app: 0|req: 12/60] 127.0.0.1 () {38 vars in 569 bytes} [Sat Dec  6 21:19:12 2014] GET /posts/new => generated 5851 bytes in 960 msecs (HTTP/1.1 200) 4 headers in 124 bytes (1 switches on core 0)
    [pid: 2304|app: 0|req: 18/61] 127.0.0.1 () {36 vars in 530 bytes} [Sat Dec  6 21:19:10 2014] GET /posts => generated 631 bytes in 3779 msecs (HTTP/1.1 200) 4 headers in 123 bytes (1 switches on core 0)
    [pid: 2305|app: 0|req: 8/62] 127.0.0.1 () {36 vars in 538 bytes} [Sat Dec  6 21:19:17 2014] GET /posts/123 => generated 7757 bytes in 294 msecs (HTTP/1.1 200) 4 headers in 124 bytes (1 switches on core 0)

Awful bash to get requests by total time spent for all lines saying "generated *X* bytes in *T* msecs"::

    $ grep generated webserver.log | awk '{ sum[$18] += $24 } END { for (k in sum) { print sum[k], k; } }' | sort -n | tail
    29 /error/style/black.css
    535 /posts/9
    609 /posts/99
    720 /posts/1
    737 /posts/123
    806 /posts/3
    1157 /posts/5
    7579 /posts/new
    7933 /posts/a
    56594 /posts

Less awful SQL to do the same thing::

    $ grep generated webserver.log | shq 'SUM(c24) AS s, c18 GROUP BY c18 ORDER BY s DESC LIMIT 10'
    56594	/posts
    7933	/posts/a
    7579	/posts/new
    1157	/posts/5
    806	/posts/3
    737	/posts/123
    720	/posts/1
    609	/posts/99
    535	/posts/9
    29	/error/style/black.css

Note that you may omit the ``SELECT`` and ``FROM`` clauses.

See ``shq -h`` for additional usage information.

Installing
==========

- With pip: ``sudo pip install shellquery``
- Manually: ``curl -o ~/bin/shq https://raw.githubusercontent.com/jingw/shellquery/master/shellquery.py && chmod +x ~/bin/shq``

Python 3 is required.

Development testing
===================

.. image:: https://travis-ci.org/jingw/shellquery.svg?branch=master
    :target: https://travis-ci.org/jingw/shellquery

.. image:: http://codecov.io/github/jingw/shellquery/coverage.svg?branch=master
    :target: http://codecov.io/github/jingw/shellquery?branch=master

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black

Commands::

    python -m venv env
    source env/bin/activate
    pip install -r dev_requirements.txt
    pytest

.. |weaselwords| replace:: :sup:`[weasel words]`
.. _weaselwords: https://en.wikipedia.org/wiki/Wikipedia:Manual_of_Style/Words_to_watch#Unsupported_attributions

.. |citationneeded| replace:: :sup:`[citation needed]`
.. _citationneeded: https://en.wikipedia.org/wiki/Wikipedia:Citation_needed
