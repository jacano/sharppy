# This is derived from the Pyste version of policies.py.
# See http://www.boost.org/ for more information.

class Policy:
    'Represents one of the call policies of boost.python.'

    def __init__(self):
        raise RuntimeError, "Can't create an instance of the class Policy"


    def Code(self):
        'Returns the string corresponding to a instancialization of the policy.'
        pass
        

    def _next(self):
        if self.next is not None:
            return ', %s >' % self.next.Code()
        else:
            return ' >'


    def __eq__(self, other):
        try:
            return self.Code() == other.Code()
        except AttributeError:
            return False



class return_internal_reference(Policy):
    'Ties the return value to one of the parameters.'

    def __init__(self, param=1, next=None):
        '''
        param is the position of the parameter, or None for "self".
        next indicates the next policy, or None.
        '''
        self.param = param
        self.next=next


    def Code(self):
        c = 'return_internal_reference< %i' % self.param
        c += self._next()
        return c



class with_custodian_and_ward(Policy):
    'Ties lifetime of two arguments of a function.'

    def __init__(self, custodian, ward, next=None):
        self.custodian = custodian
        self.ward = ward
        self.next = next

    def Code(self):
        c = 'with_custodian_and_ward< %i, %i' % (self.custodian, self.ward)
        c += self._next()
        return c



class return_value_policy(Policy):
    'Policy to convert return values.'
    
    def __init__(self, which, next=None):            
        self.which = which
        self.next = next


    def Code(self):
        c = 'return_value_policy< %s' % self.which
        c += self._next()
        return c


#  values for return_value_policy
reference_existing_object = 'reference_existing_object'
copy_const_reference = 'copy_const_reference'
copy_non_const_reference = 'copy_non_const_reference'
manage_new_object = 'manage_new_object'        
return_opaque_pointer = 'return_opaque_pointer'