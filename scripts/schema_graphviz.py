import shlex

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

with open('schema.sql', 'r') as f:
    for line in f:
        lexer = shlex.shlex(line)
        if lexer.get_token().lower() == 'create':
            if lexer.get_token().lower() == 'table':
                table_name = lexer.get_token()
                dot_lines.append("""    %s[label=<
<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">
    <TR><TD BORDER="0" COLSPAN="20" ALIGN="left">%s</TD></TR>
    <TR>""" % (table_name, table_name))
                assert lexer.get_token() == '('
                while True:
                    tok = lexer.get_token()
                    if tok.lower() == 'foreign':
                        assert lexer.get_token().lower() == 'key'
                        assert lexer.get_token() == '('
                        foreign_child_column = lexer.get_token()
                        assert lexer.get_token() == ')'
                        assert lexer.get_token().lower() == 'references'
                        foreign_parent_table = lexer.get_token()
                        assert lexer.get_token() == '('
                        foreign_parent_column = lexer.get_token()
                        assert lexer.get_token() == ')'

                        edge_lines.append("""    %s:%s:n -> %s:%s:s;""" % \
                            (table_name, foreign_child_column,
                            foreign_parent_table, foreign_parent_column))

                        foreign_options = []
                        tok = lexer.get_token()
                        while tok != ';' and tok != ',':
                            foreign_options.append(tok)
                            tok = lexer.get_token()
                    elif tok.lower() == 'primary':
                        assert lexer.get_token().lower() == 'key'
                        tok = lexer.get_token()
                        if tok == '(':
                            while tok != ')':
                                tok = lexer.get_token()
                        tok = lexer.get_token()
                        assert tok == ',' or tok == ')'
                    elif tok != '':
                        column_name = tok
                        dot_lines.append('        <TD PORT="%s">%s</TD>'%\
                            (column_name, column_name))
                        column_options = []
                        tok = lexer.get_token()
                        while tok != ',' and tok != ')':
                            column_options.append(tok)
                            tok = lexer.get_token()
                        if tok == ')':
                            tok = lexer.get_token()
                            assert tok == ';'
                            break
                    else:
                        break

                dot_lines.append("""    </TR>
</TABLE>>];""")

dot_lines.extend(edge_lines)
dot_lines.append('}')

with open('schema.dot', 'w') as outf:
    outf.writelines('\n'.join(dot_lines))
