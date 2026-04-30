import operator
import re
import time

class AnchorLogicEngine:
    def __init__(self):
        self.ops = {
            '+': (operator.add, 4),
            '-': (operator.sub, 4),
            '*': (operator.mul, 5),
            '/': (operator.truediv, 5),
            '==': (self._flexible_eq, 3),
            '!=': (lambda a, b: not self._flexible_eq(a, b), 3),
            '<': (self._flexible_lt, 3),
            '>': (self._flexible_gt, 3),
            '<=': (lambda a, b: self._flexible_lt(a, b) or self._flexible_eq(a, b), 3),
            '>=': (lambda a, b: self._flexible_gt(a, b) or self._flexible_eq(a, b), 3),
            'in': (lambda a, b: a in b if isinstance(b, (list, set, dict, str)) else False, 3),
            'IN': (lambda a, b: a in b if isinstance(b, (list, set, dict, str)) else False, 3),
            '&&': (lambda a, b: bool(a and b), 2),
            'AND': (lambda a, b: bool(a and b), 2),
            '||': (lambda a, b: bool(a or b), 1),
            'OR': (lambda a, b: bool(a or b), 1),
            '=': (self._flexible_eq, 3),
            'IMPLIES': (lambda a, b: not a or b, 1),
        }
        self.unary_ops = {
            '!': lambda a: not a,
            'NOT': lambda a: not a,
            'COUNT': lambda a: len(a) if isinstance(a, (list, set, dict)) else 0,
            'length': lambda a: len(a) if isinstance(a, (list, str, dict, set)) else len(str(a)),
            'present': lambda a: a is not None and a != "",
            'HAS': lambda a: a is not None and a != "",
            'is_array': lambda a: isinstance(a, list),
            'TODAY': lambda *args: time.strftime('%Y-%m-%d'),
            'today': lambda *args: time.strftime('%Y-%m-%d'),
            'now': lambda *args: time.strftime('%Y-%m-%d'),
            'NOW': lambda *args: time.strftime('%Y-%m-%d'),
            'oracle': lambda *args: True,
        }

    def tokenize(self, expression):
        token_pattern = r'\[[^\]]*\]|\$\.[a-zA-Z0-9_.]+|[a-zA-Z_][a-zA-Z0-9_.]*|[0-9.]+|==|!=|>=|<=|>|<|&&|\|\||!|\(|\)|\[|\]|,|"(?:\\.|[^"])*"|\'[^\']*\'|\$.[a-zA-Z0-9._\[\]]+|-?[0-9.]+|[a-zA-Z_]+'
        return [t for t in re.findall(token_pattern, expression) if t.strip()]

    def evaluate(self, expression, context=None):
        if not expression: return True
        tokens = self.tokenize(expression)
        if not tokens: return True
        return self._parse_expr(tokens, context)

    def _parse_expr(self, tokens, context, min_prec=0):
        lhs = self._parse_atom(tokens, context)
        while tokens and tokens[0] in self.ops:
            op_token = tokens[0]
            op_func, prec = self.ops[op_token]
            if prec < min_prec: break
            tokens.pop(0)
            rhs = self._parse_expr(tokens, context, prec + 1)
            lhs = op_func(lhs, rhs)
        return lhs

    def _parse_atom(self, tokens, context):
        if not tokens: return None
        token = tokens.pop(0)
        
        if token in ['ALL', 'ANY', 'FORALL', 'EXISTS']:
            op_token = token
            if tokens and tokens[0] == '(':
                tokens.pop(0)
                coll_token = tokens.pop(0)
                if coll_token.startswith('[') and coll_token.endswith(']'):
                    inner = coll_token[1:-1].strip()
                    collection = [p.strip().strip("'").strip('"') for p in inner.split(',')]
                else:
                    collection = self._resolve_path(coll_token, context)
                if tokens and tokens[0] == ')': tokens.pop(0)
            else:
                collection = self._resolve_path(tokens.pop(0), context)
            
            if tokens and tokens[0] == '(':
                tokens.pop(0)
                sub_tokens = []; depth = 1
                while tokens and depth > 0:
                    t = tokens.pop(0)
                    if t == '(': depth += 1
                    elif t == ')': depth -= 1
                    if depth > 0: sub_tokens.append(t)
                
                if not isinstance(collection, list): return False
                results = []
                for item in collection:
                    new_ctx = context.copy() if context else {}
                    new_ctx['item'] = item
                    new_ctx['$.item'] = item
                    for st in sub_tokens:
                        if st.isidentifier() and st not in self.unary_ops and st not in ['AND', 'OR', 'NOT', 'item']:
                            new_ctx[st] = item
                    results.append(self.evaluate(" ".join(sub_tokens), new_ctx))
                
                if tokens and tokens[0] == ')': tokens.pop(0)
                return all(results) if op_token in ['ALL', 'FORALL'] else any(results)
            return False

        if token.lower() == 'true': return True
        if token.lower() == 'false': return False
        if token.lower() == 'null': return None

        if token.startswith('[') and token.endswith(']'):
            try:
                inner = token[1:-1].strip()
                if not inner: return []
                parts = [p.strip().strip("'").strip('"') for p in inner.split(',')]
                return parts
            except: return []

        if token == '(':
            res = self._parse_expr(tokens, context)
            if tokens and tokens[0] == ')': tokens.pop(0)
            return res
            
        if token in self.unary_ops:
            if tokens and tokens[0] == '(':
                tokens.pop(0); args = []
                while tokens and tokens[0] != ')':
                    args.append(self._parse_expr(tokens, context))
                    if tokens and tokens[0] == ',': tokens.pop(0)
                if tokens: tokens.pop(0)
                return self.unary_ops[token](*args)
            return self.unary_ops[token](self._parse_atom(tokens, context))

        if token.startswith('"') or token.startswith("'"): return token[1:-1]
        if re.match(r'^-?[0-9.]+$', token): return float(token) if '.' in token else int(token)
        
        if token.startswith('$.') or ('.' in token and not token[0].isdigit() and '(' not in token): 
            return self._resolve_path(token, context)
            
        if context:
            if token in context: return context[token]
            # Case-insensitive root lookup
            for k, v in context.items():
                if k.lower() == token.lower(): return v
        return token

    def _resolve_path(self, path, context):
        if not context: return None
        if path == '$.item' or path == 'item': return context.get('item') or context.get('$.item')
        
        if path.startswith('$.'): parts = path.split('.')[1:]
        else: parts = path.split('.')
        
        val = context
        try:
            for p in parts:
                if p == 'length' and val is not None:
                    val = len(val) if isinstance(val, (list, str, dict, set)) else 0
                elif isinstance(val, dict):
                    # Case-insensitive key lookup
                    found = False
                    if p in val:
                        val = val[p]
                        found = True
                    else:
                        for k, v in val.items():
                            if k.lower() == p.lower():
                                val = v
                                found = True
                                break
                    if not found: return None
                elif isinstance(val, list) and p.isdigit():
                    val = val[int(p)]
                else:
                    return None
            return val
        except: return None

    def _flexible_eq(self, a, b):
        if isinstance(a, str) and isinstance(b, str):
            return a.strip().lower().rstrip('.') == b.strip().lower().rstrip('.')
        return a == b

    def _flexible_lt(self, a, b):
        try: return a < b
        except: return str(a) < str(b)

    def _flexible_gt(self, a, b):
        try: return a > b
        except: return str(a) > str(b)
