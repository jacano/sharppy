# This is derived from the Pyste version of declarations.py.
# See http://www.boost.org/ for more information.

# $Id: declarations.py,v 1.19 2003-12-22 02:26:15 patrick Exp $

import copy
import re

'''
Defines classes that represent declarations found in C++ header files.
    
'''

# version indicates the version of the declarations. Whenever a declaration
# changes, this variable should be updated, so that the caches can be rebuilt
# automatically
version = '1.0'

#==============================================================================
# Declaration
#==============================================================================
class Declaration(object):
    '''Base class for all declarations.
    @ivar cxxName: The C++ name of the declaration.
    @ivar namespace: The namespace of the declaration.
    '''

    template_search = re.compile(r'^([\w:]+)<')
    template_match  = re.compile(r'^([^<]+)<\s*(.+)\s*>\s*[\*&]?\s*$')

    def __init__(self, cxxName, namespace, mustMarshal = False):
        '''
        @type name: string
        @param name: The name of this declaration
        @type namespace: string
        @param namespace: the full namespace where this declaration resides.
        '''
        self.cxx_name = cxxName

        # self.name is the language-agnostic name.  Subclasses should set this
        # themselves if special handling is required for different syntactic
        # issues.
        match_obj = self.template_match.search(cxxName)
        if None != match_obj:
            name_part, template_part = match_obj.groups()
            self.name = name_part.split('::')
            cleaner = re.compile(r"[<:>,\s\*]")
            clean_template_part = cleaner.sub("_", template_part)
            self.name[len(self.name) - 1] += "_" + clean_template_part
        else:
            self.name = cxxName.split('::')

        if namespace is None:
           self.namespace = []
        else:
           assert(type(namespace) == list)
           self.namespace = namespace

        self.location = '', -1  # (filename, line)
        self.incomplete = False
        self.is_unique = True
        # XXX: must_marshal is pretty much a failure.  It should be removed.
        self.must_marshal = mustMarshal

    def FullName(self):
        '''
        Returns the full qualified name: "boost::inner::Test"
        @rtype: string
        @return: The full name of the declaration.
        '''
        if len(self.namespace) > 0:
            ns = '::'.join(self.namespace)
            if ns != '':
                ns += '::'
        else:
            ns = ''
        return '%s%s' % (ns, self.cxx_name)

    def getCPlusPlusName(self):
        return self.cxx_name

    def _getFullName(self):
        return self.name

    def getFullNameAbstract(self):
        name = []
        name[0:0] = self._getFullName()
        if self.namespace and self.namespace[0] != '':
            name[0:0] = self.namespace
        return name

    def getCleanName(self):
        name = self.getFullNameAbstract()
        cleaner = re.compile(r"[<:>,\s]")
        for i in xrange(len(name)):
#            assert(name[i].find('<') == -1)
            name[i] = cleaner.sub("_", name[i])
        return '_'.join(name)

    def getNamespace(self):
        return self.namespace

    def getName(self):
        return self.name

    def getGenericName(self):
        return self.getCleanName()

    def accept(self, visitor):
        visitor.visit(self)

    def __repr__(self):        
        return '<Declaration %s at %s>' % (self.FullName(), id(self))

    def __str__(self):
        return 'Declaration of %s' % self.FullName()
    
    
#==============================================================================
# Class
#==============================================================================
class Class(Declaration):
    '''
    Represents a C++ class or struct. Iteration through it yields its members.

    @type abstract: bool
    @ivar abstract: if the class has any abstract methods.

    @type bases: tuple
    @ivar bases: tuple with L{Base} instances, representing the most direct
    inheritance.

    @type hierarchy: list
    @ivar hierarchy: a list of tuples of L{Base} instances, representing
    the entire hierarchy tree of this object. The first tuple is the parent 
    classes, and the other ones go up in the hierarchy.
    '''

    def __init__(self, cxxName, namespace, members, abstract):
        Declaration.__init__(self, cxxName, namespace, True)

        self.__members = members
        self.__member_names = {}
        self.abstract = abstract
        self.bases = ()
        self.hierarchy = ()
        self.operator = {}

    def __iter__(self):
        '''iterates through the class' members.
        '''
        return iter(self.__members)            

    def isInterface(self):
        '''
        Determines whether the class associated with can be considered an
        interface or not.  Being an interface means having nothing but abstract
        (pure virtual) method declarations in the class body.
        '''
        for m in self.__members:
            if type(m) == Method:
                if m.virtual and not m.abstract:
                    return False
                elif not m.virtual:
                    return False
            # NOTE: A publicly accessible constructor is not a true indication
            # of failure to be an interface, but it's close enough.
            elif type(m) == Constructor and m.visibility == Scope.public:
                return False

        return True

    def Constructors(self, publics_only=True):
        '''Returns a list of the constructors for this class.
        @rtype: list
        '''
        constructors = []
        for member in self:
            if isinstance(member, Constructor):
                if publics_only and member.visibility != Scope.public:
                    continue
                constructors.append(member)
        return constructors

    
    def HasCopyConstructor(self):
        '''Returns true if this class has a public copy constructor.
        @rtype: bool
        '''
        for cons in self.Constructors():
            if cons.IsCopy():
                return True
        return False


    def HasDefaultConstructor(self):
        '''Returns true if this class has a public default constructor.
        @rtype: bool
        '''
        for cons in self.Constructors():
            if cons.IsDefault():
                return True
        return False

    def getMembers(self):
        return self.__members

    def AddMember(self, member):
        if member.FullName() in self.__member_names:
            member.is_unique = False
            for m in self:
                if m.FullName() == member.FullName():
                    m.is_unique = False
        else:
            member.is_unique = True
        self.__member_names[member.FullName()] = 1
        self.__members.append(member)
        if isinstance(member, ClassOperator):
            self.operator[member.FullName()] = member

    def ValidMemberTypes():
        return (NestedClass, Method, Constructor, Destructor, ClassVariable, 
                ClassOperator, ConverterOperator, ClassEnumeration)   
    ValidMemberTypes = staticmethod(ValidMemberTypes)


#==============================================================================
# NestedClass
#==============================================================================
class NestedClass(Class):
    '''The declaration of a class/struct inside another class/struct.
    
    @type class: string
    @ivar class: fullname of the class where this class is contained.

    @type visibility: L{Scope} 
    @ivar visibility: the visibility of this class.
    '''

    def __init__(self, cxxName, class_, visib, members, abstract):
        Class.__init__(self, cxxName, None, members, abstract)
        assert(type(class_) == list)
        self.class_ = class_
        self.visibility = visib
        self.cxx_name = '%s::%s' % ('::'.join(class_), cxxName)

    def _getFullName(self):
        name = []
        name[0:0] = self.name
        name[0:0] = self.class_
        return name


#==============================================================================
# Scope    
#==============================================================================
class Scope:    
    '''Used to represent the visibility of various members inside a class.
    @cvar public: public visibility
    @cvar private: private visibility
    @cvar protected: protected visibility
    '''
    public = 'public'
    private = 'private'
    protected = 'protected'


#==============================================================================
# Base    
#==============================================================================
class Base(Declaration):
    '''
    Represents a base class of another class.
    @ivar _decl: the full declaration (of type Class) of the base class
    @ivar _visibility: the visibility of the derivation.
    '''

    def __init__(self, decl, visibility=Scope.public):
        Declaration.__init__(self, decl.cxx_name, decl.namespace,
                             decl.must_marshal)
        self.class_decl = decl
        self.visibility = visibility

    def getMembers(self):
        return self.class_decl.getMembers()
    
#==============================================================================
# Function    
#==============================================================================
class Function(Declaration):
    '''The declaration of a function.
    @ivar _result: instance of L{Type} or None.
    @ivar _parameters: list of L{Type} instances.
    @ivar _throws: exception specifiers or None 
    '''

    def __init__(self, name, namespace, result, params, throws=None): 
        Declaration.__init__(self, name, namespace)
        # the result type: instance of Type, or None (constructors)            
        self.result = result
        # the parameters: instances of Type
        self.parameters = []

        for i in xrange(len(params)):
            s = 'p' + str(i)
#            print params[i].name
            self.parameters.append((params[i], s))

        # the exception specification
        self.throws = throws

    def getGenericName(self):
      base_name = Declaration.getGenericName(self)
      param_types = [x[0].getCleanName() for x in self.parameters]
      return base_name + '__' +'_'.join(param_types)

    def Exceptions(self):
        if self.throws is None:
            return ""
        else:
            return " throw(%s)" % ', '.join (self.throws) 


    def PointerDeclaration(self, force=False):
        '''Returns a declaration of a pointer to this function.
        @param force: If True, returns a complete pointer declaration regardless
        if this function is unique or not.
        '''
        if self.is_unique and not force:
            return '&%s' % self.FullName()
        else:
            result = self.result.FullName()
            params = ', '.join([x.FullName() for x in self.parameters]) 
            return '(%s (*)(%s))&%s' % (result, params, self.FullName())

    
    def MinArgs(self):
        min = 0
        for arg in self.parameters:
            if arg.default is None:
                min += 1
        return min

    minArgs = property(MinArgs)
    

    def MaxArgs(self):
        return len(self.parameters)

    maxArgs = property(MaxArgs)

#==============================================================================
# Operator
#==============================================================================
class Operator(Function):
    '''The declaration of a custom operator. Its name is the same as the 
    operator name in C++, ie, the name of the declaration "operator+(..)" is
    "+".
    '''
    
    def FullName(self):
        namespace = '::'.join(self.namespace) or ''
        if not namespace.endswith('::'):
            namespace += '::'
        return namespace + 'operator' + self.name[0]

#==============================================================================
# Method
#==============================================================================
class Method(Function):
    '''The declaration of a method.
    
    @ivar _visibility: the visibility of this method.
    @ivar _virtual: if this method is declared as virtual.
    @ivar _abstract: if this method is virtual but has no default implementation.
    @ivar _static: if this method is static.
    @ivar _class: the full name of the class where this method was declared.
    @ivar _const: if this method is declared as const.
    @ivar _throws: list of exception specificiers or None
    '''

    def __init__(self, name, class_, result, params, visib, virtual, abstract,
                 static, const, throws = None):
        Function.__init__(self, name, None, result, params, throws)
        self.visibility = visib
        self.virtual = virtual
        self.abstract = abstract
        self.static = static
        self.class_ = class_
        self.const = const
        self.override = False

    def FullName(self):
        return '%s::%s' % (self.class_, self.cxx_name)

    def _getFullName(self):
        return self.class_.split('::') + Function._getFullName(self)

    def PointerDeclaration(self, force=False):
        '''Returns a declaration of a pointer to this member function.
        @param force: If True, returns a complete pointer declaration regardless
        if this function is unique or not. 
        '''
        if self.static:
            # static methods are like normal functions
            return Function.PointerDeclaration(self, force)
        if self.is_unique and not force:
            return '&%s' % self.FullName()
        else:
            result = self.result.FullName()
            params = ', '.join([x[0].FullName() for x in self.parameters]) 
            const = ''
            if self.const:
                const = 'const'            
            return '(%s (%s::*)(%s) %s%s)&%s' %\
                (result, self.class_, params, const, self.Exceptions(), self.FullName())  


#==============================================================================
# Constructor
#==============================================================================
class Constructor(Method):
    '''A class' constructor.
    '''

    def __init__(self, name, class_, params, visib):
        Method.__init__(self, name, class_, None, params, visib, False, False,
                        False, False)

    def IsDefault(self):
        '''Returns True if this constructor is a default constructor.
        '''
        return len(self.parameters) == 0 and self.visibility == Scope.public

    def IsCopy(self):
        '''Returns True if this constructor is a copy constructor.
        '''
        if len(self.parameters) != 1:
            return False
        param = self.parameters[0][0]
        class_as_param = param.cxx_name == self.class_
        param_reference = isinstance(param, ReferenceType) 
        is_public = self.visibility == Scope.public
        return param_reference and class_as_param and param.const and is_public

    def PointerDeclaration(self, force=False):
        return ''


#==============================================================================
# Destructor
#==============================================================================
class Destructor(Method):
    'The destructor of a class.'

    def __init__(self, name, class_, visib, virtual):
        Method.__init__(self, name, class_, None, [], visib, virtual, False, False, False)

    def FullName(self):
        return '::'.join(self.class_) + '::~' + self.name[0]

    def PointerDeclaration(self, force=False):
        return ''


#==============================================================================
# ClassOperator
#==============================================================================
class ClassOperator(Method):
    'A custom operator in a class.'
    
    def FullName(self):
        return '::'.join(self.class_) + '::operator ' + self.name[0]


#==============================================================================
# ConverterOperator
#==============================================================================
class ConverterOperator(ClassOperator):
    'An operator in the form "operator OtherClass()".'
    
    def _getFullName(self):
        name = [self.class_.name]
        name[1:1] = self.result._getFullName()
        return name

#    def FullName(self):
#        return self.class_ + '::operator ' + self.result.FullName()


#==============================================================================
# Type
#==============================================================================
class Type(Declaration):
    '''Represents the type of a variable or parameter.
    @ivar _const: if the type is constant.
    @ivar _default: if this type has a default value associated with it.
    @ivar _volatile: if this type was declared with the keyword volatile.
    @ivar _restricted: if this type was declared with the keyword restricted.
    @ivar _suffix: Suffix to get the full type name. '*' for pointers, for
    example.
    '''

    const_match_re = re.compile(r'^const (.*)$')

    def __init__(self, cxxName, const = False, default = None, suffix = '',
                 mustMarshal = True):
        Declaration.__init__(self, cxxName, None, mustMarshal)

        # whatever the type is constant or not
        self.const = const
        # used when the Type is a function argument
        self.default = default
        self.volatile = False
        self.restricted = False
        self.suffix = suffix

        # Ensure that the 'const' modifier does not appear in self.cxx_name.
        match_obj = self.const_match_re.match(cxxName)
        if None != match_obj:
            self.const    = 1
            self.cxx_name = match_obj.groups()[0]
            self.name     = self.cxx_name.split('::')

    def __repr__(self):
        if self.const:
            const = 'const '
        else:
            const = ''
        return '<Type ' + const + '::'.join(self.name) + '>'

    def FullName(self):
        if self.const:
            const = 'const '
        else:
            const = ''
        return const + Declaration.FullName(self) + self.suffix


#==============================================================================
# ArrayType
#==============================================================================
class ArrayType(Type):
    '''Represents an array.
    @ivar min: the lower bound of the array, usually 0. Can be None.
    @ivar max: the upper bound of the array. Can be None.
    '''

    def __init__(self, name, const, min, max):
        'min and max can be None.'
        Type.__init__(self, name, const)
        self.min = min
        self.max = max


#==============================================================================
# ReferenceType    
#==============================================================================
class ReferenceType(Type): 
    '''A reference type.'''

    def __init__(self, cxxName, const = False, default = None, expandRef = True,
                 suffix=''):
        Type.__init__(self, cxxName = cxxName, const = const, default = default,
                      mustMarshal = False)
        if expandRef:
            self.suffix = suffix + '&'


#==============================================================================
# PointerType
#==============================================================================
class PointerType(Type):
    'A pointer type.'

    def __init__(self, cxxName, const = False, default = None,
                 expandPointer = False, suffix = ''):
        Type.__init__(self, cxxName = cxxName, const = const, default = default,
                      mustMarshal = False)
        if expandPointer:
            self.suffix = suffix + '*'


#==============================================================================
# FundamentalType
#==============================================================================
class FundamentalType(Type): 
    'One of the fundamental types, like int, void, etc.'

    def __init__(self, cxxName, const = False, default = None): 
        Type.__init__(self, cxxName = cxxName, const = const, default = default,
                      mustMarshal = False)


#==============================================================================
# FunctionType
#==============================================================================
class FunctionType(Type):
    '''A pointer to a function.
    @ivar _result: the return value
    @ivar _parameters: a list of Types, indicating the parameters of the function.
    @ivar _name: the name of the function.
    '''

    def __init__(self, result, parameters):  
        # The "name" for a function type is constructed from its result and
        # its parameters.  Its name member will always be an empty list.
        Type.__init__(self, '', False, None, False)
        self.result = result
        self.parameters = parameters

    def FullName(self):
        full = '%s (*)' % self.result.FullName()
        params = [x.FullName() for x in self.parameters]
        full += '(%s)' % ', '.join(params)        
        return full


#==============================================================================
# MethodType
#==============================================================================
class MethodType(FunctionType):
    '''A pointer to a member function of a class.
    @ivar _class: The fullname of the class that the method belongs to.
    '''

    def __init__(self, result, parameters, class_):  
        self.class_ = class_
        FunctionType.__init__(self, result, parameters)


    def FullName(self):
        full = '%s (%s::*)' % (self.result.FullName(), self.class_)
        params = [x.FullName() for x in self.parameters]
        full += '(%s)' % ', '.join(params)
        return full
    
     
#==============================================================================
# Variable
#==============================================================================
class Variable(Declaration):
    '''Represents a global variable.

    @type _type: L{Type}
    @ivar _type: The type of the variable.
    '''
    
    def __init__(self, type, name, namespace):
        Declaration.__init__(self, name, namespace)
        self.type = type


#==============================================================================
# ClassVariable
#==============================================================================
class ClassVariable(Variable):
    '''Represents a class variable.

    @type _visibility: L{Scope}
    @ivar _visibility: The visibility of this variable within the class.

    @type _static: bool
    @ivar _static: Indicates if the variable is static.

    @ivar _class: Full name of the class that this variable belongs to.
    '''

    def __init__(self, type, name, class_, visib, static):
        Variable.__init__(self, type, name, None)
        self.visibility = visib
        self.static = static
        self.class_ = class_

    def FullName(self):
        return '%s::%s' % (self.class_, self.cxx_name)

    def _getFullName(self):
        return self.class_.split('::') + Variable._getFullName(self)

#    def FullName(self):
#        return self.class_ + '::' + Variable.FullName(self)


#==============================================================================
# Enumeration    
#==============================================================================
class Enumeration(Declaration):
    '''Represents an enum.

    @type _values: dict of str => int
    @ivar _values: holds the values for this enum.
    '''
    
    def __init__(self, name, namespace):
        Declaration.__init__(self, name, namespace)
        self.values = {} # dict of str => int


    def ValueFullName(self, name):
        '''Returns the full name for a value in the enum.
        '''
        assert name in self.values
        namespace = self.namespace
        if namespace:
            namespace += '::'
        return namespace + name


#==============================================================================
# ClassEnumeration
#==============================================================================
class ClassEnumeration(Enumeration):
    '''Represents an enum inside a class.

    @ivar _class: The full name of the class where this enum belongs.
    @ivar _visibility: The visibility of this enum inside his class.
    '''

    def __init__(self, name, class_, visib):
        Enumeration.__init__(self, name, None)
        self.class_ = class_
        self.visibility = visib

    def FullName(self):
        return '%s::%s' % (self.class_, self.cxx_name)

    def _getFullName(self):
       return self.class_.split('::') + Enumeration._getFullName(self)

#    def FullName(self):
#        return '%s::%s' % (self.class_, self.name)


    def ValueFullName(self, name):
        assert name in self.values
        return '%s::%s' % (self.class_, name)

    
#==============================================================================
# Typedef
#==============================================================================
class Typedef(Declaration):
    '''A Typedef declaration.

    @type _type: L{Type}
    @ivar _type: The type of the typedef.

    @type _visibility: L{Scope}
    @ivar _visibility: The visibility of this typedef.
    '''

    def __init__(self, type, name, namespace):
        Declaration.__init__(self, name, namespace)
        self.type = type
        self.visibility = Scope.public


#==============================================================================
# Unknown        
#==============================================================================
class Unknown(Declaration):
    '''A declaration that Pyste does not know how to handle.
    '''

    def __init__(self, name):
        Declaration.__init__(self, name, None)
