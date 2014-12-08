==========
ShellQuery
==========

Ever piped together some awful combination of ``grep``, ``sed``, ``awk``, ``sort`` to run a quick-and-dirty analysis? Now you can do those same awful transformations using SQL! Many studies `[weasel words] <https://en.wikipedia.org/wiki/Wikipedia:Manual_of_Style/Words_to_watch#Unsupported_attributions>`_ have shown that the aforementioned tools are difficult to use, and moreover, most people prefer SQL `[citation needed] <https://en.wikipedia.org/wiki/Wikipedia:Citation_needed>`_.

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

You'll need Python 2.7 or Python 3. (Of course, you might want to double check the download to make sure I'm not giving you malware.)

Development testing
===================

.. image:: https://travis-ci.org/jingw/shellquery.svg?branch=master
    :target: https://travis-ci.org/jingw/shellquery

Python 3::

    virtualenv3 --no-site-packages env3
    source env3/bin/activate
    pip3 install -r dev_requirements.txt
    py.test

And again for Python 2 (after ``deactivate``)::

    virtualenv2 --no-site-packages env2
    source env2/bin/activate
    pip2 install -r dev_requirements.txt
    py.test
