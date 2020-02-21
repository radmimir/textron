class PLCDEBUG(object):
    '''
    class for debugiing
    '''
    def __init__(self):
        pass

    def close(self):
        pass

    def read_by_name(self, where, type):
        print('simulating reading ', where)
        return -1

    def write_by_name(self, where, what, type):
        print('simulating writing ', where, '... done')

class fakeADS(object):
    def __init__(self):
        print('Using fakeADS!')
    def PLCTYPE_BYTE(self):
        pass
    def PLCTYPE_REAL(self):
        pass
    def PLCTYPE_BOOL(self):
        pass
    def PLCTYPE_ARR_SHORT(self, size):
        pass
