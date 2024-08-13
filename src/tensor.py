# inspired by: https://github.com/tinygrad/tinygrad/blob/c900b6e/tinygrad/tensor.py
import numpy as np
from functools import partialmethod
from typing import Union, List

# TODO: better typing
# TODO: implement lazy eval
class Tensor:
    def __init__(self, data: Union[np.ndarray, List, float], dtype: np.dtype=np.float32):
        if type(data) == np.ndarray: self.data = data.astype(dtype)
        else: raise TypeError('array has to be of type np.ndarray.')
        self.grad = None
        self._ctx: Context = None

    def backward(self, allow_fill=True):
        if self._ctx is None: return 
        if self.grad is None and allow_fill: 
            assert self.data.size == 1, 'can only start backprop on scalar.'
            self.grad = np.ones_like(self.data)

        assert self.grad is not None

        grads = self._ctx.arg.backward(self._ctx, self.grad)
        grads = [grads] if len(self._ctx.parents) == 1 else grads

        for t, g in zip(self._ctx.parents, grads):
            assert g.shape == t.data.shape, 'grad shape does not match tensor shape.'
            t.grad = g 
            t.backward(False) 
        
class Context:
    def __init__(self, arg_func, *tensors: Tensor):
        self.arg = arg_func
        self.parents = tensors 
        self.saved_tensors = [] 

    def save_for_backward(self, *x: np.ndarray): self.saved_tensors.extend(x)

class Function:
    def forward(ctx: Context, *args): raise NotImplementedError('forward not implemented for function.')
    def backward(ctx: Context, grad_out: np.ndarray): raise NotImplementedError('backward not implemented for function.')

    def apply(self, arg, *x):
        ctx = Context(arg, self, *x)
        ret = Tensor(arg.forward(ctx, self.data, *[t.data for t in x]))
        ret._ctx = ctx 
        return ret

def register_function(name: str):
    def decorator(cls: type):
        setattr(Tensor, name, partialmethod(cls.apply, cls))
        return cls
    return decorator

@register_function('add')
class Add(Function):
    def forward(ctx: Context, x: np.ndarray, y: np.ndarray):
        ctx.save_for_backward(x, y)
        return x+y
    
    def backward(ctx: Context, dout: np.ndarray):
        return dout, dout

@register_function('mul')
class Mul(Function):
    def forward(ctx: Context, x: np.ndarray, y: np.ndarray):
        ctx.save_for_backward(x, y)
        return x*y

    def backward(ctx: Context, dout: np.ndarray):
        x, y = ctx.saved_tensors
        return y*dout, x*dout

@register_function('dot')
class Dot(Function):
    def forward(ctx: Context, x: np.ndarray, y: np.ndarray):
        ctx.save_for_backward(x, y)
        return x.dot(y)

    def backward(ctx: Context, dout: np.ndarray):
        x, y = ctx.saved_tensors 
        dx= dout.dot(y.T) 
        dy= dout.T.dot(x).T 
        return dx, dy
    
@register_function('relu')
class ReLU(Function):
    def forward(ctx: Context, x: np.ndarray):
        ctx.save_for_backward(x)
        return np.maximum(x, 0)

    def backward(ctx: Context, dout: np.ndarray):
        x, = ctx.saved_tensors
        dx = dout.copy()
        dx[x<0] = 0
        return dx
    
@register_function('sum')
class Sum(Function):
    def forward(ctx: Context, x: np.ndarray):
        ctx.save_for_backward(x)
        return np.array([x.sum()])
    
    def backward(ctx: Context, dout: np.ndarray):
        x, = ctx.saved_tensors
        return dout*np.ones_like(x)

@register_function('logsoftmax')
class LogSoftmax(Function):
    def forward(ctx: Context, x: np.ndarray):
        def logsumexp(x):
            c = x.max(axis=1)
            return c+np.log(np.exp(x-c.reshape((-1, 1))).sum(axis=1))
        out = x-logsumexp(x).reshape((-1, 1))
        ctx.save_for_backward(out)
        return out

    def backward(ctx: Context, dout: np.ndarray):
        out, = ctx.saved_tensors
        return dout-np.exp(out)*dout.sum(axis=1).reshape((-1, 1))
