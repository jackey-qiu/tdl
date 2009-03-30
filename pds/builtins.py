#####################################################################
"""
T. Trainor (fftpt@uaf.edu), M. Newville
Builtin funcitons for pds

Modifications:
--------------
- Modified from tdl r259 - 
  for use with pds shell program

"""
#####################################################################

import os
import sys
import types
import time

from util import show_list, show_more, datalen
from util import set_path, unescape_string, list2array
from util import mod_import
from interpretor import Group

#####################################################################
class PdsBuiltins:
    #################################################################
    def __init__(self,):
        self.module_list = []

    #################################################################
    def group(self,):
        """
        create a new group
        g = group()
        """
        grp = Group()
        return grp

    #################################################################
    def ls(self,arg= '.',ncol=1,width=72):
        """
        ncol, textwidth
        """
        ret = self._ls(arg=arg)
        print show_list(ret,ncol=ncol,textwidth=width)
        print ""

    #################################################################
    def _ls(self,arg= '.'):
        " return list of files in the current directory "
        from glob import glob
        arg.strip()
        if type(arg) != types.StringType or len(arg)==0: arg = '.'
        if os.path.isdir(arg):
            ret = os.listdir(arg)
        else:
            ret = glob(arg)
        if sys.platform == 'win32':
            for j in range(len(ret)):
                ret[j] = ret[j].replace('\\','/')
        return ret

    #################################################################
    def pwd(self,):
        print self._cwd()
        print ""

    #################################################################
    def _cwd(self,x=None):
        "return current working directory"
        ret = os.getcwd()
        if sys.platform == 'win32':
            ret = ret.replace('\\','/')
        return ret

    #################################################################
    def cd(self,name=None):
        self._cd(name)
        
    #################################################################
    def _cd(self,name=None):
        "change directorty"
        if name == None:
            self.pwd()
            return
        name = name.strip()
        if name:
            try:
                os.chdir(name)
            except:
                print "Directory '%s' not found" % name
        ret = os.getcwd()
        if sys.platform == 'win32':
            ret = ret.replace('\\','/')
        return ret

    #################################################################
    def more(self,name,pagesize=24):
        "list file contents"
        try:
            f = open(name)
            l = f.readlines()
            f.close()
            show_more(l,filename=name,pagesize=pagesize)
        except IOError:
            print "cannot open file: %s." % name
            return

    #################################################################
    def path(self,pth=None,recurse=False,**kw):
        """
        modify or show python path
        """
        ret = self._path(pth=pth,recurse=recurse,**kw)
        if ret: print ret
        
    #################################################################
    def _path(self,pth=None,recurse=False,**kw):
        """
        modify or show python path
        """
        if not pth:
            return show_list(sys.path)
        else:
            set_path(pth=pth,recurse=recurse)
        return None

    #################################################################
    def mod_import(self,module=None,**kw):
        """
        Import python modules
        x = mod_import('x.py')  # imports new module x.py
        mod_import()            # re-import previously defined mods
        """
        def _import(module):
            mod = mod_import(module)
            if type(mod) == types.ModuleType:
                if mod not in self.module_list: 
                    self.module_list.append(mod)
            return mod

        if module:
            return _import(module)
        else:
            for m in self.module_list:
                mod = _import(m)
                
    #################################################################

#####################################################################
# Load the functions on import
#####################################################################
__pdsbuiltins__ = PdsBuiltins()
