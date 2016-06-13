import threading

# TODO: Add license

def asynchronous_call(fun, callback=None, *cargs, **ckwargs):
    '''
    This function allows to make asynchronous calls, wrapping a function in
    another one, that is executed in a separated thread.
    Also, it allows to set a callback, together with it's arguments, that will
    be called once the main function processing finishes. The callback function
    MUST recieve as first argument the RESULT from the main function, which
    can be either the result of the execution or an Exception that could've
    been trhown during it's execution.
    '''
    # function that wraps the original function and calls the callback once
    # the processing is finished
    def worker(*args, **kwargs):
        try:
            result = fun(*args, **kwargs)
        except Exception as e:
            result = e

        if callback:
            callback(result, *cargs, **ckwargs)

    def fun2(*args, **kwargs):
        threading.Thread(target=worker, args=args, kwargs=kwargs).start()

    return fun2