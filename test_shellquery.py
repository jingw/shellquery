# coding: utf-8
from __future__ import absolute_import, print_function, unicode_literals
import io
import os.path
import random
import re
import sqlite3
import sre_constants
import subprocess
import sys
import unittest

import mock

import shellquery


if sys.version_info[0] < 3:
    # monkey patch for python 2 compatibility
    unittest.TestCase.assertCountEqual = unittest.TestCase.assertItemsEqual


class TestShellQuery(unittest.TestCase):
    def test_read_columns(self):
        lines = ['a 1\n', 'b . 3', 'c', '\n', '']
        rows = [['a', '1'], ['b', '.', '3'], ['c'], [], []]
        self.assertEqual(
            list(shellquery.read_columns(lines, ' ', 99, False)),
            rows
        )
        self.assertEqual(
            list(shellquery.read_columns(lines, ' ', 99, True)),
            rows
        )
        self.assertEqual(
            list(shellquery.read_columns(lines, '.', 99, False)),
            [[''] * 4, [''] * 6, [''] * 2, [], []]
        )
        self.assertEqual(
            list(shellquery.read_columns(lines, '.', 99, True)),
            [['a 1'], ['b ', ' 3'], ['c'], [], []]
        )

    def test_read_columns_capturing_group(self):
        self.assertEqual(
            list(shellquery.read_columns(['_ab_ab_'], '(a|b)+', 99, False)),
            [['_', '_', '_']],
        )

    def test_read_columns_empty(self):
        self.assertEqual(list(shellquery.read_columns([], ' ', 99, True)), [])

    def test_read_columns_max_columns(self):
        self.assertEqual(
            list(shellquery.read_columns(['a b c d'], ' ', 2, True)),
            [['a', 'b c d']]
        )
        self.assertEqual(
            list(shellquery.read_columns(['a b c d'], ' ', 1, True)),
            [['a b c d']]
        )

    def test_load_rows(self):
        def do_test():
            connection = sqlite3.connect(':memory:')
            data = [[], [1], [1, 2], [0], [2], [1, 2, 3, 4, 5], [], []]

            shellquery.load_rows(connection, 'x', data)
            cursor = connection.cursor()
            cursor.execute('SELECT * FROM x')
            self.assertCountEqual(cursor.fetchall(), [
                (None,) * 5,
                ('1',) + (None,) * 4,
                ('1', '2') + (None,) * 3,
                ('0',) + (None,) * 4,
                ('2',) + (None,) * 4,
                ('1', '2', '3', '4', '5'),
                (None,) * 5,
                (None,) * 5,
            ])

        do_test()
        with mock.patch.object(shellquery, 'LOAD_ROWS_MAX_BUFFER', 1):
            do_test()
        with mock.patch.object(shellquery, 'LOAD_ROWS_MAX_BUFFER', 0):
            do_test()

    def test_load_rows_ugly_name(self):
        connection = sqlite3.connect(':memory:')
        # Omit the end quote character
        table_name = r"""`~!@#$%^&*()-_=+{}[]|\;:',<.>/? 中文"""
        data = []

        shellquery.load_rows(connection, table_name, data)
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM {}'.format(shellquery.quote_identifier(table_name)))
        self.assertFalse(cursor.fetchall())

    def test_load_rows_empty(self):
        connection = sqlite3.connect(':memory:')
        shellquery.load_rows(connection, 'x', [])
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM x')
        self.assertEqual(cursor.fetchall(), [])

    def test_quote_identifier(self):
        self.assertEqual(shellquery.quote_identifier('foo'), '"foo"')
        self.assertEqual(shellquery.quote_identifier('`]'), '"`]"')
        self.assertEqual(shellquery.quote_identifier('`"'), '[`"]')
        self.assertEqual(shellquery.quote_identifier('"]'), '`"]`')
        self.assertEqual(shellquery.quote_identifier('"`['), '["`[]')
        self.assertRaises(ValueError, lambda: shellquery.quote_identifier('"`]'))

    def test_add_from_clause(self):
        self.assertEqual(
            shellquery.add_from_clause('c1', 'table'),
            'c1 FROM "table" '
        )
        self.assertEqual(
            shellquery.add_from_clause('c1 from x', 'table'),
            'c1 from x'
        )
        self.assertEqual(
            shellquery.add_from_clause('c1 where true', 'table'),
            'c1 FROM "table" where true'
        )
        self.assertEqual(
            shellquery.add_from_clause('c1 where true group by c1 order by c1', 'table'),
            'c1 FROM "table" where true group by c1 order by c1'
        )
        self.assertEqual(
            shellquery.add_from_clause('[group] order by c1', 'table'),
            '[group] FROM "table" order by c1'
        )
        self.assertEqual(
            shellquery.add_from_clause('c1 limit 1', 'table'),
            'c1 FROM "table" limit 1'
        )

    def test_add_select(self):
        self.assertEqual(
            shellquery.add_select('x from a'),
            'SELECT x from a'
        )
        self.assertEqual(
            shellquery.add_select(' select x from a'),
            ' select x from a'
        )

    def _run_main_test(self, args, stdin=None):
        """Return the output of running main against the given arguments and standard input"""
        with mock.patch('sys.argv', [''] + args):
            stdin = io.StringIO(stdin)
            stdout = io.StringIO()
            with mock.patch('sys.stdin', stdin), mock.patch('sys.stdout', stdout):
                shellquery.main()
            return stdout.getvalue()

    def test_main(self):
        """Test the whole main method in a complex example"""
        query = """
        select c1, c2 from [test_data/中 文]
        union select c1, c2 from "test_data/].txt" union
        select c1, c2 from `test_data/].log`
        union select 0, null
        """
        cwd = os.getcwd()
        try:
            os.chdir(os.path.dirname(__file__))
            output = self._run_main_test([query])
        finally:
            os.chdir(cwd)
        self.assertCountEqual(
            output.splitlines(),
            ['中文\t1', 'a\t2', 'This\tfile', 'screw\tyou', '0\tNULL']
        )

    def test_stdin(self):
        """Test reading from stdin"""
        output = self._run_main_test(['*'], 'boring value')
        self.assertEqual(output, 'boring\tvalue\n')

    def test_unicode_stdin(self):
        """Test unicode on stdin, full stack"""
        with open(os.path.join(os.path.dirname(__file__), 'test_data', '中 文')) as data:
            output = subprocess.check_output(
                [sys.executable, shellquery.__file__, 'c1'],
                # In a terminal, Python infers the output encoding, but in a test it uses ASCII.
                env={'PYTHONIOENCODING': 'utf-8'},
                stdin=data,
            )
        self.assertEqual(output.decode('utf-8'), '中文\na\n')

    def test_header(self):
        """Test the --output-header option"""
        output = self._run_main_test(["'中' AS 文", '--output-header'], 'a')
        self.assertEqual(output.splitlines(), ['文', '中'])

        # No rows to putput
        output = self._run_main_test(["9 as colname", '-H'])
        self.assertEqual(output.splitlines(), ['colname'])

    def test_examples(self):
        """Verify the examples in the argparse help text"""
        progname = sys.executable + ' ' + shellquery.__file__
        for _name, cmd, expected in shellquery.EXAMPLES:
            output = subprocess.check_output(
                # echo might be a shell builtin without support for the -e option
                cmd.replace('echo', '/bin/echo').format(name=progname),
                shell=True,
                cwd=os.path.join(os.path.dirname(__file__), 'test_data'),
            )
            self.assertEqual(output.decode('utf-8'), expected)

    def test_readme(self):
        """Verify the examples in the README"""
        examples = []
        with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as f:
            # Scan through the README for code blocks beginning with a $
            # Translate these to command, output pairs
            indent = ' ' * 4
            cmd_start = indent + '$ '
            command = None
            output_lines = []
            for line in f:
                if line.startswith(cmd_start):
                    command = line[len(cmd_start):]
                elif line.startswith(indent) and command is not None:
                    output_lines.append(line[len(indent):])
                else:
                    if command is not None:
                        # Done reading a block, so flush out to examples
                        examples.append((command, ''.join(output_lines)))
                        command = None
                        output_lines = []

        for command, expected in examples:
            output = subprocess.check_output(
                command.replace('shq', sys.executable + ' ' + shellquery.__file__),
                shell=True,
                cwd=os.path.join(os.path.dirname(__file__), 'test_data'),
            )
            self.assertEqual(output.decode('utf-8'), expected)

    def test_re_split_randomly(self):
        """Test re_split against re.split by generating random test cases"""

        def random_string(choices, maxlength):
            length = random.randint(0, maxlength)
            return ''.join(random.choice(choices) for _ in range(length))

        string_choices = 'ab'
        re_choices = 'ab|?*+()'
        for _ in range(10 * 1000):
            string = random_string(string_choices, 10)
            try:
                # Replace '(' to get a non-capturing group
                regex = re.compile(random_string(re_choices, 10).replace('(', '(?:'))
            except sre_constants.error:
                # ignore malformed regexes
                continue
            maxsplit = random.randint(1, 10)
            self.assertEqual(
                regex.split(string, maxsplit),
                shellquery.re_split(regex, string, maxsplit),
                "string={}, regex={}, maxsplit={}".format(string, regex, maxsplit)
            )

    def test_re_split(self):
        test_cases = [
            ('', '', 1),
            ('a', 'a', 1),
            ('a', '', 1),
            ('aaa', 'a', 1),
            ('aaa', '', 1),
            ('aaa', 'a', 9),
            ('aaa', '', 9),
            ('aaa', 'a*', 9),
            ('aaa', 'a+', 9),
            ('abcabc', 'a|b', 9),
            ('abcabc', '(?:a|b)', 9),
        ]
        for string, regex, maxsplit in test_cases:
            compiled = re.compile(regex)
            self.assertEqual(
                compiled.split(string, maxsplit),
                shellquery.re_split(compiled, string, maxsplit)
            )
