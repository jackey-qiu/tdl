#!/usr/bin/env python
#
# Evaluator:  main TDL language evaluation class 
#
import sys
import types
import copy

# import default library of cmds and funcs
import Help

from Expression import Expression, opcodes
from Symbol import Symbol, SymbolTable
from Util import split_delim,  find_unquoted_char, parens_matched, split_list, trimstring
from Util import EvalException, Command2Expr,PrintShortExcept

class Evaluator:
    """ main evaluation class for tdl language.
    parses  / compiles tdl statements and evaluates them:

    
    """
    EOF      = opcodes.eof
    __interrupts = ['pass','continue','break','return']
    def __init__(self,symbolTable = None, output=None,
                 interactive = False,libs=None,debug=0,GUI='TkAgg'):

        self.debug       = debug
        self.interactive = interactive

        self.output      = output      or sys.stdout

        self.help        = Help.Help()
        self.symbolTable = symbolTable or SymbolTable(libs=libs,
                                                      tdl=self,
                                                      writer=self.output)

        self.symbolTable.addBuiltin('GUI',GUI)
        self.Expression  = Expression(symbolTable=self.symbolTable,
                                      run_procedure = self.run_procedure)
        self.expr_eval   = self.Expression.eval
        self.expr_compile= self.Expression.compile
        
        self.prompt   = '... '
        self.stack = []
        self.text  = []
        self.line_buff = ''
        self.nline = 0
        self.triple_squote = False
        self.triple_dquote = False
        self.line_join     = ' '
        self.interrupt  = 0
        self.retval = None
        self.infile = '<stdin>'
        
    def set_debug(self,n):
        self.debug = n
        self.expr.set_debug(n)

    def raise_error(self,msg):
        if len(self.text)>0: msg =  "%s at line %i:\n  '%s'" % (msg,self.nline,self.text)
        raise EvalException, msg

    def load_file(self,fname):
        try:
            f = open(fname)
            l = f.readlines()
            f.close()
        except IOError:
            raise EvalException, 'cannot load file %s '% fname
        self.infile = fname
        self.text.append((self.EOF,-1,fname))
        self.load_statements(l,file=fname)

    def clear(self):
        " clear all statements "
        self.stack = []
        self.text  = []
        self.nline = 0

    def eval(self,t):
        " evaluate tdl statement or list of tdl statements"
        if type(t) != types.ListType:
            self.load_statements([t])
        else:
            self.load_statements(t)
        return self.run()

    def load_statements(self,t,file='stdin'):
        " load a list of text lines to be parsed & executed"
        s = t[:]
        n = 0
        self.infile = file
        while s:
            n = n+1
            self.text.append((s.pop().strip(),n,self.infile))

    def run(self):
        " load a chunk of text to be parsed and possibly executed"
        ret = None
        while True:
            try:
                s,nline,srcfile = self.text.pop()
            except IndexError:
                break
            if len(s)<=0: continue
            x = self.compile(s = s)
            # print 'run compilation: ', s, '=> ', x
            if x is not None:
                ret = self.interpret(x, text=s)
                self._status = True
        return ret

    def get_input(self):
        return raw_input(self.prompt)

    def get_next_textline(self):
        filename = 'stdin'
        try:
            line,nline,filename  = self.text.pop()
        except IndexError:
            if self.interactive:
                line = self.get_input()
                nline = self.nline
            else:
                return (self.EOF,-1,'')
        self.nline = self.nline + 1
        return line,nline,filename
        
    def get_next_statement(self,s = None):
        " get and pre-process next program statement"

        if s is None:  s,nline,fname = self.get_next_textline()
        # handle the case of triple quotes:
        #    join strings with a '\n' instead of ' '
        if s.find("'''")>-1   and not self.triple_dquote:
            self.triple_squote  = not self.triple_squote
        elif s.find('"""')>-1 and not self.triple_squote:
            self.triple_dquote  = not self.triple_dquote
        join = ' '            
        if self.triple_dquote or self.triple_squote: join = '\n'
        
        if self.line_buff:  s = "%s%s%s" % (self.line_buff,join,s)
        is_complete = parens_matched(s)
        while not is_complete:
            self.line_buff = s
            s,nline,fname = self.get_next_textline()
            if s == self.EOF and not self.interactive:   break
            s = "%s%s%s" % (self.line_buff,join,s)
            is_complete = parens_matched(s)
        
        #
        self.line_buff = ''
        self.triple_dquote = False
        self.triple_squote = False
        s = s.strip()
        if len(s)>1:
            # remove end-of-line comments
            jcom =find_unquoted_char(s,char='#')
            s = s[:jcom]
            # look for unquoted semi-colons (multiple statements per line)
            jsemi =find_unquoted_char(s,char=';')
            if jsemi<jcom:
                self.text.append((s[jsemi+1:],self.nline,self.infile))
                s = s[:jsemi]
            s.strip()
            # look for certain "keyword(x)" constructs:
            for j in ('if','elif', 'while', 'return', 'print'):
                if s.startswith("%s("% j): s = "%s %s" % (j,s[len(j):])
            # check for 'else:'
            if s in ('else:','try:','except:'): s = '%s :' % s[:-1]
        if len(s) < 1: s = ''
        # get first word:
        w = s.split()
        key = ''
        if len(w)>0: key = w[0].lower()
        return (s,key)


    def compile(self,s = None):
        " main parsing and compilation of tdl statements"
        # print "compile <%s>" %  s,
        s,key = self.get_next_statement(s=s)
        # print " :key <%s>" % key
        # print " :s  <%s>"  % s
        
        if s in ('','#'): return None
        if s == self.EOF: return [self.EOF]
        ret = []
        
        # these keywords can never legally occur at a top-level compilation
        # and will always be found while the appropriate (if,while,for,def)
        # block is being processed
        if key in ('else','elif','endif','endfor','endwhile','enddef','endtry'):
            raise EvalException, 'syntax error: %s' % key

        # handle if statements, including if/elif/else/endif blocks
        elif key == 'if':
            t = s[len(key):]
            status,s1,s2 = split_delim(t, delim=':')
            if status == -1:   return None
            ret = ['if']
            blockhead = self.expr_compile(s1)
            # block to execute
            if s2:   #  simple 'if x : y = x' type
                ret.append( (blockhead, [self.compile(s = s2)]))
            else:
                end = "endif"
                t = None
                block = []
                tmp   = []
                cond = [blockhead]
                else_seen = False
                while True:
                    sn,nextkey = self.get_next_statement()
                    if sn == '': continue
                    if nextkey == 'endif':
                        block.append(tmp)
                        break
                    elif nextkey == 'elif':
                        if else_seen:
                            raise EvalException, 'syntax error: elif after else'
                        t = s[len(key):]
                        status,s1,s2 = split_delim(t, delim=':')
                        if status == -1:   return None
                        blockhead = self.expr_compile(s1)
                        block.append(tmp)
                        tmp = []
                    elif nextkey == 'else':
                        else_seen = True
                        cond.append(self.expr_compile('1'))
                        block.append(tmp)
                        tmp = []
                    else:
                        t = self.compile(s=sn)
                        if t is not None:  tmp.append(t)
        
                for i in zip(cond,block):  ret.append(i)
        # try: except: endtry:
        elif key == 'try':
            t = s[len(key):]
            status,s1,s2 = split_delim(t, delim=':')
            ret = ['try']            
            blockhead = self.expr_compile('1')
            if s2:
                raise EvalException, 'syntax error: invalid try statement.'
            else:
                end = "endtry"
                t = None
                block = []
                tmp   = []
                cond = [blockhead]
                else_seen = False
                while True:
                    sn,nextkey = self.get_next_statement()
                    if sn == '': continue
                    if nextkey == 'endtry':
                        block.append(tmp)
                        break
                    elif nextkey == 'except':
                        else_seen = True
                        cond.append(self.expr_compile('1'))
                        block.append(tmp)
                        tmp = []
                    else:
                        t = self.compile(s=sn)
                        if t is not None:  tmp.append(t)
                for i in zip(cond,block):  ret.append(i)
        #
        # def, for, and while blocks
        elif key in ('def', 'for', 'while'):
            t = s[len(key):]
            # print 'This is a ', key, ' t= ', t
            status,s1,s2 = split_delim(t, delim=':')
            if status == -1: return None
            ret = [key]
            # while blockhead is the simplest of all
            if key == 'while':
                blockhead = self.expr_compile(s1)
            elif key  == 'for':
                status,r1,r2 = split_delim(s1.replace(' in ',' @ '), delim='@')
                if status == -1: return None
                j = self.expr_compile(r1, reverse=True)
                x = j.pop()
                if len(j)!=1 or x != opcodes.variable:
                    raise EvalException, 'syntax error: invalid for A statement'
                blockhead = (j.pop(), self.expr_compile(r2))

            elif key == 'def':
                # there are three forms of def:
                #   def x = expr
                # and
                #   def x(args): return expr
                # and
                #   def x(args):
                #      block
                #   enddef
                # if status (holding position of ':') is < 4,
                # it cannot be either of the last two forms

                if status <4:
                    status,s1,s2 = split_delim(t, delim='=')
                    if status<1:
                        raise EvalException, 'syntax error: invalid def statement'
                    # it's of the simple form:   def x = expr
                    stack = self.expr_compile(s1, reverse=True)
                    tok = stack.pop()
                    if tok != opcodes.variable:
                        raise EvalException, 'syntax error: invalid def statement'
                    stack.append(opcodes.symbol)

                    return ['defvar',stack, self.expr_compile(s2),s2]
                else:
                    try:
                        t = self.expr_compile(s1,  reverse=True)
                    except:
                        raise EvalException, 'syntax error: invalid def statement'

                    ftype = t.pop() ;nargs = t.pop() ;  fname = t.pop()
                    if ftype != opcodes.function:
                        raise EvalException, 'syntax error: invalid def statement'

                    n1,n2 =  s1.find('('), s1.rfind(')')
                    if n1 <1 or n2<n1:
                        raise EvalException, 'syntax error: invalid def statement'
                    # print 'n1 = ', n1, n2
                    # construct tuple and keyqords of function arguments
                    vargs = [] ; kws = {} ; iargs = 0; eq_seen = False
                    for i in split_list(s1[n1+1:n2]):
                        iargs = iargs+1
                        ieq = i.find('=')
                        if ieq == -1:
                            if eq_seen:
                                raise EvalException, 'syntax error: invalid def statement 2'
                            j = self.expr_compile(i,reverse=True)
                            if len(j)>1:
                                x = j.pop()
                                if len(j)!=1 or x != opcodes.variable:
                                    raise EvalException, 'syntax error: invalid def statement 1'
                                vargs.append(j.pop())
                            else:
                                iargs = iargs-1
                        else:
                            eq_seen = True
                            j = self.expr_compile(i[:ieq], reverse=True)
                            x = j.pop()
                            if len(j)!=1 or x != opcodes.variable:
                                raise EvalException, 'syntax error: invalid def statement 1'
                            k = j.pop()
                            v = self.expr_eval(self.expr_compile(i[ieq+1:]))
                            kws[k] = v
                    if iargs != int(nargs):
                        raise EvalException, 'syntax error: invalid def statement 5'
                blockhead = [fname, tuple(vargs), kws]
            ret.append(blockhead)
            # block to execute
            if s2:   #  simple 'for i in arange(10): print i' type
                ret.append([self.compile(s = s2)])
            else:
                end = "end%s" % key
                t = 0 ; tmp = []
                while True:
                    sn,nextkey = self.get_next_statement()
                    if sn == '': continue
                    if nextkey == end:
                        break
                    else:
                        t = self.compile(s=sn)
                        if t is not None:  tmp.append(t)
                ret.append(tmp)

        elif key in ('del','print', 'return'): # keywords that take a list
            s = s[len(key):].strip()
            for pars in (('(',')'),('[',']')):
                if (s.startswith(pars[0]) and s.endswith(pars[1])):
                    i = s.find(pars[1])
                    if i  == len(s)-1: s= s[1:len(s)-1]
            x = None
            ret.append(key.lower())
            if len(s)>0:
                ret.append( self.expr_compile("[%s]" % s))
            else:
                ret.append('')
            
        elif key in ('break', 'continue'):
            # break and continure are closely related,
            # and at parse stage do nothing.
            s = s[len(key):].strip()
            if len(s)>0:
                raise EvalException, 'syntax error: invalid %s statement' % key
            ret.append(key)

        # regular assignment / eval statement
        else:
            # check if command-like interpretation is reasonable
            if key.find('(')==-1  and key.find(',')==-1 and key.find('=')==-1:
                if self.symbolTable.hasFunc(key):
                    stack= self.expr_compile(Command2Expr(s,symtable=self.symbolTable))
                    if stack[0] != opcodes.function:
                        raise EvalException, 'syntax error: weird error with commad '
                    stack[0] = opcodes.command
                    return  ['eval', stack, s]
            # wasn't a command!
            status,s1,s2 = split_delim(s,delim='=')
            if status == -1: return None
            if s2 == '': # Eval
                return  ['eval', self.expr_compile(s1), s]
            else: # Assignment
                stack = self.expr_compile(s1)
                tok = stack.pop(0)
                if tok not in (opcodes.variable, opcodes.array):
                    raise EvalException, 'syntax error: invalid assignment statement'
                if tok ==  opcodes.variable:  stack.insert(0,0)
                stack.insert(0,opcodes.symbol)
                return ['assign', stack,  self.expr_compile(s2), s]

        return ret



    def do_assign(self,left_hs,rhs):
        """ handle assignment statements """
        lhs  = left_hs[:]
        # the symbol name for the lhs will be looked for only
        # in the 'current group' unless fully qualified
        ndim_lhs = lhs.pop()
        varname  = lhs.pop()
        sym  = self.symbolTable.getVariableCurrentGroup(varname)
        if sym is None:
            self.raise_error('Cannot make assignment to %s??' % varname)
        for i in range(len(lhs)):
            if type(lhs[i]) == types.FloatType: lhs[i] = int(lhs[i])

        if len(lhs)>0 and  sym.type=='defvar':
            self.raise_error('Cannot assign to part of defined variable %s.' % varname)

        try:
            x    = copy.deepcopy(sym.value)
        except:
            self.raise_error('Cannot make assignment %s' % sym.name)            

        if len(lhs)==0:
            x = rhs
        elif len(lhs)==1:
            x[lhs[0]] = rhs
        else:
            x[tuple(lhs)] = rhs
        if sym.constant:
            self.raise_error('cannot re-assign value of constant %s ' % varname)
        elif sym.type in ('defvar','defpro','variable'):
            sym.value  = x
            sym.code   = None
            sym.type   = 'variable'
            sym.constant = False

    def interpret(self,s,text=''):
        "interpret parsed code from compile"
        tok = s[0]
        # print 'INTERPRET ', s 
        if text != '': self.Expression.text=text
        if tok == self.EOF:
            return None
        try:
            tok=tok.lower()
        except AttributeError:
            pass
        
        if tok in self.__interrupts:
            self.interrupt = self.__interrupts.index(tok)
            if tok == 'return':
                self.retval = self.expr_eval(s[1])
                return
        elif tok == 'del':
            s[1].reverse()
            xtok = s[1].pop()
            nvar = s[1].pop()
            if xtok != opcodes.list:
                raise EvalException, 'Invalid "del" statement'
            try:
                for i in range(nvar):
                    xtok = s[1].pop()
                    vname = s[1].pop()
                    if xtok != opcodes.variable:
                        raise EvalException, 'cannot delete %s ' % vname
                    self.symbolTable.deleteSymbol(vname)
            except:
                raise EvalException, 'Invalid "del" statement'                
        elif tok == 'print':
            if len(s[1])>0:
                for i in self.expr_eval(s[1]):
                    self.output.write('%s ' % str(i))
            self.output.write('\n')
        elif tok == 'defvar':
            if len(s[1]) != 2 or s[1][1] != opcodes.symbol:
                raise EvalException, 'Invalid "def" statement'
            x = self.symbolTable.setDefVariable(s[1][0], s[2], s[3])
        elif tok == 'assign':
            lhs = self.expr_eval(s[1])
            rhs = self.expr_eval(s[2])
            self.do_assign(lhs,rhs)
        elif tok == 'eval':
            return self.expr_eval(s[1])
        elif tok == 'try':
            do_except = False
            for sx in  s[1][1]:
                try:
                    ret = self.interpret(sx)
                except:
                    do_except = True
                    break
            if do_except:
                for sx in s[2][1]:
                    ret = self.interpret(sx)

        elif tok == 'if':
            self.interrupt = 0
            found = False
            ret = None
            for i in s[1:] :
                cond,block = i[0],i[1]
                if self.expr_eval(cond):
                    for sx in block:
                        ret = self.interpret(sx,text)
                        if self.interrupt>0: break
                    if self.interrupt>1:  break
                    # self.interrupt = 0
                    return ret
        elif tok == 'while':
            self.interrupt = 0
            cond = self.expr_eval(s[1])
            while cond:
                for sx in s[2]:
                    ret = self.interpret(sx,text)
                    if self.interrupt>0: break
                if self.interrupt>1:  break
                self.interrupt = 0
                cond = self.expr_eval(s[1])
        elif tok == 'for':
            self.interrupt = 0
            iter_var = s[1][0]
            rhs = self.expr_eval(s[1][1])
            for x in rhs:
                self.symbolTable.setVariable(iter_var,x)
                for sx in s[2]:
                    ret = self.interpret(sx,text)
                    if self.interrupt>0: break
                if self.interrupt>1:  break
                self.interrupt = 0
        elif tok == 'def':
            #  look for docstring
            desc = None
            code = s[2]
            tx   = s[2][0]
            if (tx[0] == 'eval' and  len(tx[1])==2 and tx[1][0] == opcodes.string):
                desc = trimstring(tx[1][1])
                code = s[2][1:]

            self.symbolTable.addDefPro(s[1][0], code, desc=desc,
                                    args=s[1][1],kws=s[1][2])
        elif tok == self.EOF:
            return None
        else:
            raise EvalException, 'unknown evaluation error'

    ######

    def run_procedure(self,proc,args=None,kws=None):
        " run a user-created tdl procedure "
        if proc.type != 'defpro':
            raise EvalException, 'invalid procedure'

        name = proc.name
        if len(args) != len(proc.args):
            raise EvalException, 'not enough arguments for procedure %s' % name


        savegroup = self.symbolTable.getDataGroup()
        group = self.symbolTable.addRandomGroup(prefix=name,nlen=4)
        if group is None:
            raise EvalException, 'cannot run procedure %s (cannot create group??)' % name
        self.symbolTable.setDataGroup(group)

        for k,v in zip(proc.args,args):  self.symbolTable.setVariable(k,v)

        kvals = {}
        kvals.update(proc.kws)
        kvals.update(kws)
        
        for k,v in kvals.items():
            self.symbolTable.setVariable(k,v)

        ret = None
        # for i in  proc.code: print i
            
        try:
            for i in proc.code:
                self.interpret(i)
                if self.interrupt == 3:
                    ret = self.retval
                    self.interrupt = 0
                    break
        except:
            s = 'Error in procedure %s\n    %s' % (name, i[-1])
            PrintShortExcept(s) 

        try:
            if len(ret) == 1: ret= ret[0]
        except TypeError:
            pass

        # remove this Group, return to previous default Group
        self.symbolTable.deleteGroup(group)
        self.symbolTable.setDataGroup(savegroup)
        return ret