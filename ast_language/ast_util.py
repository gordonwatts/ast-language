import ast


def wrap_ast(node):
    return ast.Module(body=[ast.Expr(value=node)])


def unwrap_ast(node):
    return node.body[0].value


class SourceRemover(ast.NodeTransformer):
    def __init__(self, source_name):
        self.source_name = source_name

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == self.source_name:
            return ast.Name(id=node.attr)
        else:
            return self.generic_visit(node)


class PythonASTToColumns(ast.NodeVisitor):
    def __init__(self):
        self.n_selects = 0

    def generic_visit(self, node):
        raise SyntaxError('Unsupported node type: ' + str(type(node)))

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

    def visit_Attribute(self, node):
        return self.visit(node.value) + '.' + node.attr

    def visit_Call(self, node):
        return self.visit(node.func) + '()'

    def visit_Select(self, node):
        if self.n_selects != 0:
            raise SyntaxError('Nested selects are not supported')
        self.n_selects += 1
        if not isinstance(node.selector, ast.Lambda):
            raise SyntaxError('Selector must be a lambda; found ' + str(type(node.selector)))
        if len(node.selector.args.args) != 1:
            raise SyntaxError('Selector must have exactly one argument; found '
                              + str(len(node.selector.args.args)))
        source_name = node.selector.args.args[0].arg
        body = SourceRemover(source_name).visit(node.selector.body)
        if isinstance(body, ast.List) or isinstance(body, ast.Tuple):
            return ', '.join(self.visit(element) for element in body.elts)
        else:
            return self.visit(body)


def python_ast_to_columns(python_ast):
    return PythonASTToColumns().visit(python_ast)
