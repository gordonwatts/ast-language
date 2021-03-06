from . import linq_util

import lark

import ast
import os

grammar_pathname = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'grammar.lark')

with open(grammar_pathname) as grammar_file:
    parser = lark.Lark(grammar_file.read(), start='record')


class TextASTToPythonAST(lark.Transformer):
    def record(self, children):
        if (len(children) == 0
           or isinstance(children[0], lark.Token) and children[0].type == 'WHITESPACE'):
            return ast.Module(body=[])
        return ast.Module(body=[ast.Expr(value=children[0])])

    def expression(self, children):
        for child in children:
            if not (isinstance(child, lark.Token) and child.type == 'WHITESPACE'):
                return child
        raise SyntaxError('Expression does not contain a node')

    def atom(self, children):
        child = children[0]
        if child.type == 'IDENTIFIER':
            return ast.Name(id=child.value, ctx=ast.Load())
        elif child.type == 'STRING_LITERAL':
            return ast.Str(s=ast.literal_eval(child.value))
        elif child.type == 'NUMERIC_LITERAL':
            return ast.Num(n=ast.literal_eval(child.value))
        else:
            raise Exception('Unknown atom child type: ' + str(child.type))

    def composite(self, children):
        fields = []
        for child in children:
            if isinstance(child, lark.Token):
                if child.type == 'NODE_TYPE':
                    node_type = child.value
                else:
                    pass
            elif isinstance(child, ast.AST):
                fields.append(child)
            else:
                pass

        if node_type == 'list':
            return ast.List(elts=fields, ctx=ast.Load())

        elif node_type == 'attr':
            if len(fields) != 2:
                raise SyntaxError('Attribute node must have two fields; found ' + len(fields))
            if not isinstance(fields[1], ast.Str):
                raise SyntaxError('Attribute name must be a string; found ' + type(fields[1]))
            return ast.Attribute(value=fields[0], attr=fields[1].s, ctx=ast.Load())

        elif node_type == 'call':
            if len(fields) < 1:
                raise SyntaxError('Call node must have at least one field; found ' + len(fields))
            return ast.Call(func=fields[0], args=fields[1:], keywords=[])

        elif node_type == 'lambda':
            if len(fields) != 2:
                raise SyntaxError('Lambda node must have two fields; found ' + len(fields))
            if not isinstance(fields[0], ast.List):
                raise SyntaxError('Lambda arguments must be in a list; found ' + type(fields[0]))
            for arg in fields[0].elts:
                if not isinstance(arg, ast.Name):
                    raise SyntaxError('Lambda arguments must variable names; found ' + type(arg))
            return ast.Lambda(args=ast.arguments(args=[ast.arg(arg=name.id, annotation=None)
                                                       for name in fields[0].elts],
                                                 vararg=None,
                                                 kwonlyargs=[],
                                                 kw_defaults=[],
                                                 kwarg=None,
                                                 defaults=[]),
                              body=fields[1])

        elif node_type == 'Select':
            if len(fields) != 2:
                raise SyntaxError('Select node must have two fields; found ' + len(fields))
            if not isinstance(fields[1], ast.Lambda):
                raise SyntaxError('Select selector must be a lambda; found ' + type(fields[1]))
            if len(fields[1].args.args) != 1:
                raise SyntaxError('Select selector must have exactly one argument; found '
                                  + len(fields[1].args.args))
            return linq_util.Select(source=fields[0], selector=fields[1])

        else:
            raise SyntaxError('Unknown composite node type: ' + node_type)


class PythonASTToTextAST(ast.NodeVisitor):
    def visit_Module(self, node):
        n_children = len(node.body)
        if n_children == 0:
            return ''
        elif n_children == 1:
            return self.visit(node.body[0])
        else:
            raise SyntaxError('A record must contain zero or one expressions; found '
                              + str(n_children))

    def visit_Expr(self, node):
        return self.visit(node.value)

    def visit_Name(self, node):
        return node.id

    def visit_Num(self, node):
        return repr(node.n)

    def visit_Str(self, node):
        return repr(node.s)

    @staticmethod
    def make_composite_node_string(node_type, *fields):
        return '(' + node_type + ''.join([' ' + field for field in fields]) + ')'

    def visit_List(self, node):
        return self.make_composite_node_string('list',
                                               *[self.visit(element) for element in node.elts])

    def visit_Tuple(self, node):
        return self.visit_List(node)

    def visit_Attribute(self, node):
        return self.make_composite_node_string('attr', self.visit(node.value), repr(node.attr))

    def visit_Call(self, node):
        return self.make_composite_node_string('call',
                                               self.visit(node.func),
                                               *[self.visit(arg) for arg in node.args])

    def visit_Lambda(self, node):
        return self.make_composite_node_string('lambda',
                                               self.visit(node.args),
                                               self.visit(node.body))

    def visit_arguments(self, node):
        return self.visit(ast.List(elts=node.args))

    def visit_arg(self, node):
        return node.arg

    def visit_Select(self, node):
        return self.make_composite_node_string('Select',
                                               self.visit(node.source),
                                               self.visit(node.selector))

    def generic_visit(self, node):
        raise SyntaxError('Unsupported node type: ' + str(type(node)))


def text_ast_to_python_ast(text_ast):
    tree = parser.parse(text_ast)
    return TextASTToPythonAST().transform(tree)


def python_ast_to_text_ast(python_ast):
    return PythonASTToTextAST().visit(python_ast)


def python_source_to_text_ast(python_source):
    python_ast = ast.parse(python_source)
    return PythonASTToTextAST().visit(python_ast)
