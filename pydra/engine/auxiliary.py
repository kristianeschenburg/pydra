import pdb
import itertools
import logging
from .helpers import ensure_list

logger = logging.getLogger('pydra')

# dj: might create a new class or move to State


# Function to change user provided splitter to "reverse polish notation" used in State
def splitter2rpn(splitter, other_splitters=None):
    """ Functions that translate splitter to "reverse polish notation."""
    if not splitter:
        return []
    output_splitter = []
    _ordering(splitter, i=0, output_splitter=output_splitter, other_splitters=other_splitters)
    return output_splitter


def _ordering(el, i, output_splitter, current_sign=None, other_splitters=None):
    """ Used in the splitter2rpn to get a proper order of fields and signs. """
    if type(el) is tuple:
        # checking if the splitter dont contain splitter from previous nodes, i.e. has str "_NA", etc.
        if type(el[0]) is str and el[0].startswith("_"):
            node_nm = el[0][1:]
            if node_nm not in other_splitters:
                raise Exception("can't ask for splitter from {}".format(node_nm))
            splitter_mod = change_splitter(splitter=other_splitters[node_nm], name=node_nm)
            el = (splitter_mod, el[1])
        if type(el[1]) is str and el[1].startswith("_"):
            node_nm = el[1][1:]
            if node_nm not in other_splitters:
                raise Exception("can't ask for splitter from {}".format(node_nm))
            splitter_mod = change_splitter(splitter=other_splitters[node_nm], name=node_nm)
            el = (el[0], splitter_mod)
        _iterate_list(el, ".", other_splitters, output_splitter=output_splitter)
    elif type(el) is list:
        if type(el[0]) is str and el[0].startswith("_"):
            node_nm = el[0][1:]
            if node_nm not in other_splitters:
                raise Exception("can't ask for splitter from {}".format(node_nm))
            splitter_mod = change_splitter(splitter=other_splitters[node_nm], name=node_nm)
            el[0] = splitter_mod
        if type(el[1]) is str and el[1].startswith("_"):
            node_nm = el[1][1:]
            if node_nm not in other_splitters:
                raise Exception("can't ask for splitter from {}".format(node_nm))
            splitter_mod = change_splitter(splitter=other_splitters[node_nm], name=node_nm)
            el[1] = splitter_mod
        _iterate_list(el, "*", other_splitters, output_splitter=output_splitter)
    elif type(el) is str:
        output_splitter.append(el)
    else:
        raise Exception("splitter has to be a string, a tuple or a list")

    if i > 0:
        output_splitter.append(current_sign)


def _iterate_list(element, sign, other_splitters, output_splitter):
    """ Used in the splitter2rpn to get recursion. """
    for i, el in enumerate(element):
        _ordering(
            el, i, current_sign=sign, other_splitters=other_splitters, output_splitter=output_splitter)


# functions used in State to know which element should be used for a specific axis
# TODO: should I moved it to State?

def splitting_axis(state_inputs, splitter_rpn):
    """Having inputs and splitter (in rpn notation), functions returns the axes of output for every input."""
    axis_for_input = {}
    stack = []
    # to remember current axis
    current_axis = None
    # to remember shapes and axes for partial results
    out_shape = {}
    out_axes = {}
    # to remember imput names for partial results
    out_inputname = {}
    for el in splitter_rpn:
        # scalar splitter
        if el == ".":
            right = stack.pop()
            left = stack.pop()
            # when both, left and right, are already products of partial splitter
            if left.startswith("OUT") and right.startswith("OUT"):
                if out_shape[left] != out_shape[right]:
                    raise Exception("arrays for scalar operations should have the same size")
                current_inputs = out_inputname[left] + out_inputname[right]
            # when left is already product of partial splitter
            elif left.startswith("OUT"):
                if state_inputs[right].shape == out_shape[left]:  #todo:should we allow for one-element array?
                    axis_for_input[right] = out_axes[left]
                else:
                    raise Exception("arrays for scalar operations should have the same size")
                current_inputs = out_inputname[left] + [right]
            # when right is already product of partial splitter
            elif right.startswith("OUT"):
                if state_inputs[left].shape == out_shape[right]:
                    axis_for_input[left] = out_axes[right]
                else:
                    raise Exception("arrays for scalar operations should have the same size")
                current_inputs = out_inputname[right] + [left]

            else:
                if state_inputs[right].shape == state_inputs[left].shape:
                    current_axis = list(range(state_inputs[right].ndim))
                    current_shape = state_inputs[left].shape
                    axis_for_input[left] = current_axis
                    axis_for_input[right] = current_axis
                    current_inputs = [left, right]
                else:
                    raise Exception("arrays for scalar operations should have the same size")
            # adding partial output to the stack
            stack.append("OUT_{}".format(len(out_shape)))
            out_inputname["OUT_{}".format(len(out_shape))] = current_inputs
            out_axes["OUT_{}".format(len(out_shape))] = current_axis
            out_shape["OUT_{}".format(len(out_shape))] = current_shape

        # outer splitter
        elif el == "*":
            right = stack.pop()
            left = stack.pop()
            # when both, left and right, are already products of partial splitter
            if left.startswith("OUT") and right.startswith("OUT"):
                # changing all axis_for_input for inputs from right
                for key in out_inputname[right]:
                    axis_for_input[key] = [
                        i + len(out_axes[left]) for i in axis_for_input[key]
                    ]
                current_axis = out_axes[left] +\
                               [i + (out_axes[left][-1] + 1) for i in out_axes[right]]
                current_shape = tuple([i for i in out_shape[left] + out_shape[right]])
                current_inputs = out_inputname[left] + out_inputname[right]
            # when left is already product of partial splitter
            elif left.startswith("OUT"):
                axis_for_input[right] = [
                    i + (out_axes[left][-1] + 1) for i in range(state_inputs[right].ndim)
                ]
                current_axis = out_axes[left] + axis_for_input[right]
                current_shape = tuple([i for i in out_shape[left] + state_inputs[right].shape])
                current_inputs = out_inputname[left] + [right]
            # when right is already product of partial splitter
            elif right.startswith("OUT"):
                # changing all axis_for_input for inputs from right
                for key in out_inputname[right]:
                    axis_for_input[key] = [
                        i + state_inputs[left].ndim for i in axis_for_input[key]
                    ]
                axis_for_input[left] = [
                    i - len(out_shape[right]) + (out_axes[right][-1] + 1)
                    for i in range(state_inputs[left].ndim)
                ]
                current_axis = out_axes[right] + [
                    i + (out_axes[right][-1] + 1) for i in range(state_inputs[left].ndim)
                ]
                current_shape = tuple([i for i in state_inputs[left].shape + out_shape[right]])
                current_inputs = out_inputname[right] + [left]
            else:
                axis_for_input[left] = list(range(state_inputs[left].ndim))
                axis_for_input[right] = [
                    i + state_inputs[left].ndim for i in range(state_inputs[right].ndim)
                ]
                current_axis = axis_for_input[left] + axis_for_input[right]
                current_shape = tuple(
                    [i for i in state_inputs[left].shape + state_inputs[right].shape])
                current_inputs = [left, right]
            # adding partial output to the stack
            stack.append("OUT_{}".format(len(out_shape)))
            out_inputname["OUT_{}".format(len(out_shape))] = current_inputs
            out_axes["OUT_{}".format(len(out_shape))] = current_axis
            out_shape["OUT_{}".format(len(out_shape))] = current_shape

        # just a name of input
        else:
            stack.append(el)

    if len(stack) == 0:
        pass
    elif len(stack) > 1:
        raise Exception("exception from splitting_axis")
    elif not stack[0].startswith("OUT"):
        current_axis = [i for i in range(state_inputs[stack[0]].ndim)]
        axis_for_input[stack[0]] = current_axis

    if current_axis:
        ndim = max(current_axis) + 1
    else:
        ndim = 0
    return axis_for_input, ndim


def converting_axis2input(axis_for_input, ndim, state_inputs=None):
    """ Having axes for all the input fields, the function returns fields for each axis. """
    input_for_axis = []
    shape = []
    for i in range(ndim):
        input_for_axis.append([])
        shape.append(0)

    for inp, axis in axis_for_input.items():
        for (i, ax) in enumerate(axis):
            input_for_axis[ax].append(inp)
            if state_inputs is not None:
                shape[ax] = state_inputs[inp].shape[i]

    if state_inputs is not None:
        return input_for_axis, shape
    else:
        return input_for_axis


#function used in State if combiner

def matching_input_from_splitter(splitter_rpn):
    """similar to splitting_axis, but without state_input,
        finding inputs that are for the same axes.
        can't find the final dimensions without inputs.
    """
    axes_for_inputs = {}
    output_inputs = {}
    stack_inp = []
    for el in splitter_rpn:
        if el == ".":
            right, left = stack_inp.pop(), stack_inp.pop()
            out_nm = "OUT{}".format(len(output_inputs))
            if left.startswith("OUT") and right.startswith("OUT"):
                output_inputs[out_nm] = output_inputs[left] + output_inputs[right]
                axes_for_inputs[out_nm] = axes_for_inputs[left].copy()
            elif right.startswith("OUT"):
                output_inputs[out_nm] = output_inputs[right] + [left]
                axes_for_inputs[out_nm] = axes_for_inputs[right].copy()
                axes_for_inputs[left] = axes_for_inputs[right].copy()
            elif left.startswith("OUT"):
                output_inputs[out_nm] = output_inputs[left] + [right]
                axes_for_inputs[out_nm] = axes_for_inputs[left].copy()
                axes_for_inputs[right] = axes_for_inputs[left].copy()
            else:
                output_inputs[out_nm] = [left, right]
                axes_for_inputs[left] = [0]
                axes_for_inputs[out_nm] = [0]
                axes_for_inputs[right] = [0]
            stack_inp.append(out_nm)
        elif el == "*":
            right, left = stack_inp.pop(), stack_inp.pop()
            out_nm = "OUT{}".format(len(output_inputs))
            if left.startswith("OUT") and right.startswith("OUT"):
                output_inputs[out_nm] = output_inputs[left] + output_inputs[right]
                for inp in output_inputs[right] + [right]:
                    axes_for_inputs[inp] = [i + len(axes_for_inputs[left])
                                            for i in axes_for_inputs[inp]]
                axes_for_inputs[out_nm] = axes_for_inputs[left] + axes_for_inputs[right]
            elif right.startswith("OUT"):
                output_inputs[out_nm] = output_inputs[right] + [left]
                axes_for_inputs[left] = [min(axes_for_inputs[right]) - 1]
                axes_for_inputs[out_nm] = axes_for_inputs[left] + axes_for_inputs[right]
            elif left.startswith("OUT"):
                output_inputs[out_nm] = output_inputs[left] + [right]
                axes_for_inputs[right] = [max(axes_for_inputs[left]) + 1]
                axes_for_inputs[out_nm] = axes_for_inputs[left] + axes_for_inputs[right]
            else:
                output_inputs[out_nm] = [left, right]
                axes_for_inputs[left] = [0]
                axes_for_inputs[right] = [1]
                axes_for_inputs[out_nm] = [0, 1]
            stack_inp.append(out_nm)
        else:
            stack_inp.append(el)

    # checking if at the end I have only one element
    if len(stack_inp) == 1 and stack_inp[0].startswith("OUT"):
        pass
    elif len(stack_inp) == 1:
        axes_for_inputs[stack_inp[0]] = [0]
    else:
        raise Exception("something wrong with the splittper")

    # removing "OUT*" elements
    axes_for_inputs = dict((key, val) for (key, val) in axes_for_inputs.items()
                           if not key.startswith("OUT"))

    # checking if I have any axes below 0
    all_axes = []
    for _, val in axes_for_inputs.items():
        all_axes += val
    min_ax = min(all_axes)
    # moving all axes in case min_ax <0 , so everything starts from 0
    if min_ax < 0:
        axes_for_inputs = dict((key, [v + abs(min_ax) for v in val])
                               for (key, val) in axes_for_inputs.items())

    #dimensions
    ndim = len(set(all_axes))

    return axes_for_inputs, ndim


def remove_inp_from_splitter_rpn(splitter_rpn, inputs_to_remove):
    """modifying splitter_rpn: removing inputs due to combining"""
    splitter_rpn_copy = splitter_rpn.copy()
    # reverting order
    splitter_rpn_copy.reverse()
    stack_inp = []
    stack_sgn = []
    from_last_sign = []
    for (ii, el) in enumerate(splitter_rpn_copy):
        # element is a sign
        if el == "." or el == "*":
            stack_sgn.append((ii, el))
            from_last_sign.append(0)
        # it's an input but not to remove
        elif el not in inputs_to_remove:
            if from_last_sign:
                from_last_sign[-1] += 1
            stack_inp.append((ii, el))
        # it'a an input that should be removed
        else:
            if not from_last_sign:
                pass
            elif from_last_sign[-1] <= 1:
                stack_sgn.pop()
                from_last_sign.pop()
            else:
                stack_sgn.pop(-1*from_last_sign.pop())

    # creating the final splitter_rpn after combining
    remaining_elements = stack_sgn + stack_inp
    remaining_elements.sort(reverse=True)
    splitter_rpn_combined = [el for (i,el) in remaining_elements]
    return splitter_rpn_combined


def rpn2splitter(splitter_rpn):
    """recurrent algorithm to move from splitter_rpn to splitter.
       every time combines pairs of input in one input,
       ends when the length is one
     """
    if splitter_rpn == []:
        return None
    if len(splitter_rpn) == 1:
        return splitter_rpn[0]

    splitter_rpn_copy = splitter_rpn.copy()
    signs = [".", "*"]
    splitter_modified = []

    while splitter_rpn_copy:
        el = splitter_rpn_copy.pop()
        # element is a sign
        if el in signs:
            if splitter_rpn_copy[-1] not in signs and splitter_rpn_copy[-2] not in signs:
                right, left = splitter_rpn_copy.pop(), splitter_rpn_copy.pop()
                if el == ".":
                    splitter_modified.append((left, right))
                elif el == "*":
                    splitter_modified.append([left, right])
            else:
                splitter_modified.append(el)
        else:
            splitter_modified.append(el)

    # reversing the list and combining more
    splitter_modified.reverse()
    return rpn2splitter(splitter_modified)


# used in the Node to change names in a splitter


def change_splitter(splitter, name):
    """changing names of splitter: adding names of the node"""
    if isinstance(splitter, str):
        if "." in splitter or splitter.startswith("_"):
            return splitter
        else:
            return "{}.{}".format(name, splitter)
    elif isinstance(splitter, list):
        return _add_name(splitter, name)
    elif isinstance(splitter, tuple):
        splitter_l = list(splitter)
        return tuple(_add_name(splitter_l, name))


def _add_name(mlist, name):
    for i, elem in enumerate(mlist):
        if isinstance(elem, str):
            if "." in elem or elem.startswith("_"):
                pass
            else:
                mlist[i] = "{}.{}".format(name, mlist[i])
        elif isinstance(elem, list):
            mlist[i] = _add_name(elem, name)
        elif isinstance(elem, tuple):
            mlist[i] = list(elem)
            mlist[i] = _add_name(mlist[i], name)
            mlist[i] = tuple(mlist[i])
    return mlist


op = {'.': zip,
      '*': itertools.product}


def flatten(vals, cur_depth=0, max_depth=None):
    if max_depth is None:
        max_depth = len(list(input_shape(vals)))
    values = []
    if cur_depth >= max_depth:
        values.append([vals])
    else:
        for val in vals:
            if isinstance(val, (list, tuple)):
                values.append(flatten(val, cur_depth + 1, max_depth))
            else:
                values.append([val])
    print(vals, values, cur_depth, max_depth)
    return itertools.chain.from_iterable(values)


def iter_splits(iterable, keys):
    for iter in list(iterable):
        yield dict(zip(keys, list(flatten(iter, max_depth=1000))))


def next_key(new_key):
    return '_' + chr(ord(new_key[1:]) + 1) if new_key else '_a'


def input_shape(in1):
    shape = [len(in1)]
    last_shape = None
    for value in in1:
        if isinstance(value, list):
            cur_shape = input_shape(value)
            if last_shape is None:
                last_shape = cur_shape
            elif last_shape != cur_shape:
                last_shape = None
                break
        else:
            last_shape = None
            break
    if last_shape is not None:
        shape.extend(last_shape)
    return tuple(shape)


def _splits(splitter, inputs):
    import numpy as np
    stack = []
    keys = []
    groups = {}
    group_count = 0
    for token in splitter2rpn(splitter):
        if token in ['.', '*']:
            op1 = stack.pop()
            op2 = stack.pop()
            op1str = op2str = False
            if isinstance(op2, str):
                shape2 = input_shape(inputs[op2])
                op2val = range(np.prod(shape2))
                op2str = True
            else:
                op2val, shape2, oldgroup2 = op2
            if isinstance(op1, str):
                shape1 = input_shape(inputs[op1])
                op1val = range(np.prod(shape1))
                op1str = True
            else:
                op1val, shape1, oldgroup1 = op1
            if token == '.':
                if shape2 != shape1:
                    raise ValueError('Operands {} and {} do not have same shape.'.format(op1, op2))
            if token == '.':
                if all([op1str, op2str]):
                    groups[op2] = group_count
                    groups[op1] = group_count
                    oldgroup = group_count
                elif op1str:
                    groups[op1] = oldgroup2
                    oldgroup = oldgroup2
                elif op2str:
                    groups[op2] = oldgroup1
                    oldgroup = oldgroup1
                newshape = shape1
            if token == '*':
                if all([op1str, op2str]):
                    groups[op2] = group_count
                    group_count += 1
                    groups[op1] = group_count
                    oldgroup = [groups[op2], groups[op1]]
                elif op1str:
                    group_count += 1
                    groups[op1] = group_count
                    if isinstance(oldgroup2, list):
                        oldgroup = oldgroup2 + [groups[op1]]
                elif op2str:
                    group_count += 1
                    groups[op2] = group_count
                    if isinstance(oldgroup1, list):
                        oldgroup = [groups[op2]] + oldgroup1
                newshape = tuple(list(shape2) + list(shape1))
            if isinstance(op2, str):
                keys.insert(0, op2)
            if isinstance(op1, str):
                keys.append(op1)
            pushval = (op[token](op2val, op1val), newshape, oldgroup)
            stack.append(pushval)
        else:
            stack.append(token)
    val = stack.pop()
    if isinstance(val, tuple):
        val = val[0]
    return val, keys, groups


def splits(splitter, inputs):
    values, keys, _ = _splits(splitter, inputs)
    return iter_splits(values, keys)


def map_splits(split_iter, inputs):
    for split in split_iter:
        yield {k: list(flatten(ensure_list(inputs[k])))[v] for k,v in split.items()}



'''
def _splits2d(splitter, inputs):
    stack = []
    keys = []
    for token in splitter2rpn(splitter):
        if token in ['.', '*']:
            op1 = stack.pop()
            op1val = ensure_list(inputs[op1]) if isinstance(op1, str) else op1
            op1val = list2array(op1val)
            op2 = stack.pop()
            op2val = ensure_list(inputs[op2]) if isinstance(op2, str) else op2
            op2val = list2array(op2val)
            shape = op1val.shape
            if token == '.':
                try:
                    if op1val.shape != op2val.shape:
                        raise ValueError('operands not of equal length {} and {}'.format(op1, op2))
                except TypeError:
                    pass
            op_result = list(op[token](op2val.flatten().tolist(),
                                       op1val.flatten().tolist()))
            stack.append(list2array(op_result, shape).tolist())
            if isinstance(op2, str):
                keys.insert(0, op2)
            if isinstance(op1, str):
                keys.append(op1)
        else:
            stack.append(token)
    return stack.pop(), keys


def list2array(inlist, shape=None):
    import numpy as np
    inshape = list_shape(ensure_list(inlist))
    if shape is None:
        shape = inshape
    new_array = np.array(inlist)
    if new_array.shape == shape:
        return new_array
    new_array = np.empty(inshape, dtype=object)
    new_array[:] = inlist
    return new_array.reshape(shape)
'''
