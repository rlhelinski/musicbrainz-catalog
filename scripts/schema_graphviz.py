import shlex
from collections import OrderedDict

"""
A script to convert an SQL schema into a GraphViz diagram.
"""

dot_lines = ["""// This file was created by %s, DO NOT EDIT
digraph schema {
    rankdir="BT";
    node [shape=plaintext]
""" % __file__,
    ]
edge_lines = []

tables = list()

with open('schema.sql', 'r') as f:
    stmts = f.read()

stmts = ' '.join(stmts.split('\n'))

for stmt in stmts.split(';'):
    stmt += ';'
    lexer = shlex.shlex(stmt)
    if lexer.get_token().lower() == 'create':
        if lexer.get_token().lower() == 'table':
            table = dict()
            tables.append(table)
            table['name'] = lexer.get_token()
            table['columns'] = OrderedDict()

            assert lexer.get_token() == '('
            while True:
                tok = lexer.get_token()
                if tok.lower() == 'foreign':
                    assert lexer.get_token().lower() == 'key'
                    assert lexer.get_token() == '('
                    child_column = lexer.get_token()
                    col = table['columns'][child_column]
                    col['foreign-key'] = dict()
                    assert lexer.get_token() == ')'
                    assert lexer.get_token().lower() == 'references'
                    col['foreign-key']['parent-table'] = lexer.get_token()
                    assert lexer.get_token() == '('
                    col['foreign-key']['parent-column'] = lexer.get_token()
                    assert lexer.get_token() == ')'

                    edge_lines.append("""    %s:%s:n -> %s:%s:s;""" % \
                        (table['name'], child_column,
                        col['foreign-key']['parent-table'],
                        col['foreign-key']['parent-column']))

                    col['foreign-key']['options'] = list()
                    tok = lexer.get_token()
                    while tok != ';' and tok != ',':
                        col['foreign-key']['options'].append(tok)
                        tok = lexer.get_token()
                elif tok.lower() == 'primary':
                    assert lexer.get_token().lower() == 'key'
                    assert lexer.get_token() == '('
                    while True:
                        col = table['columns'][lexer.get_token()]
                        col['primary-key'] = True
                        tok = lexer.get_token()
                        if tok != ',':
                            break
                    assert tok == ')'
                    #tok = lexer.get_token()
                    #if tok == '(':
                        #while tok != ')':
                            #tok = lexer.get_token()
                    tok = lexer.get_token()
                    #assert tok == ',' or tok == ')'
                elif tok != '':
                    col = dict(options=[])
                    table['columns'][tok] = col
                    tok = lexer.get_token()
                    while tok != ',' and tok != ')':
                        if tok.lower() == 'primary':
                            assert lexer.get_token().lower() == 'key'
                            col['primary-key'] = True
                        col['options'].append(tok)
                        tok = lexer.get_token()
                    if tok == ')':
                        tok = lexer.get_token()
                        assert tok == ';'
                        break
                else:
                    break

for table in tables:
    dot_lines.append("""    %s[label=<
<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">
    <TR><TD BORDER="0" COLSPAN="20" ALIGN="left">%s</TD></TR>
    <TR>""" % (table['name'], table['name']))
    for column_name, col in table['columns'].items():
        dot_lines.append('        <TD PORT="%s">%s%s</TD>'%\
            (column_name, column_name, '*' if 'primary-key' in col else ''))
    dot_lines.append("""    </TR>
</TABLE>>];""")

dot_lines.extend(edge_lines)
dot_lines.append('}')

with open('schema.dot', 'w') as outf:
    outf.writelines('\n'.join(dot_lines))
