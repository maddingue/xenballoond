#!/usr/bin/env python
""" fast XenStore API access via ctypes """

from ctypes import *
from ctypes.util import find_library


# types
xs_transaction_t = c_uint32
struct_xs_handle = c_void_p


# load the xenstore library
xenstore = CDLL(find_library("xenstore"))


# install the xs_domain_open() function
#
#   struct xs_handle *xs_domain_open(void);
#
# Connect to the xs daemon. Returns a handle or NULL.
#
xs_domain_open = xenstore.__getattr__("xs_domain_open")
xs_domain_open.restype = struct_xs_handle


# install the xs_read() function
#
#   void *xs_read(struct xs_handle *h, xs_transaction_t t,
#                 const char *path, unsigned int *len);
#
# Get the value of a single file, nul terminated.
# Returns a malloced value: call free() on it after use.
# len indicates length in bytes, not including terminator.
#
xs_read = xenstore.__getattr__("xs_read")
xs_read.argtypes = [ struct_xs_handle, xs_transaction_t, c_char_p,
    POINTER(c_uint) ]
xs_read.restype = c_char_p


# install the xs_write() function
#
#   bool xs_write(struct xs_handle *h, xs_transaction_t t,
#                 const char *path, const void *data, unsigned int len);
#
# Write the value of a single file. Returns false on failure.
#
xs_write = xenstore.__getattr__("xs_write")
xs_write.argtypes = [ struct_xs_handle, xs_transaction_t, c_char_p,
    c_void_p, c_uint ]
xs_write.restype = c_bool


# install the xs_transaction_end() function
#
#   bool xs_transaction_end(struct xs_handle *h, xs_transaction_t t,
#                           bool abort);
#
# Start a transaction: changes by others will not be seen during
# this transaction, and changes will not be visible to others
# until end. Returns NULL on failure.
#
xs_transaction_start = xenstore.__getattr__("xs_transaction_start")
xs_transaction_start.argtypes = [ struct_xs_handle ]
xs_transaction_start.restype = xs_transaction_t


# install the xs_transaction_start() function
#
#   xs_transaction_t xs_transaction_start(struct xs_handle *h);
#
# End a transaction. If abandon is true, transaction is discarded
# instead of committed. Returns false on failure: if errno == EAGAIN,
# you have to restart transaction.
#
xs_transaction_end = xenstore.__getattr__("xs_transaction_end")
xs_transaction_end.argtypes = [ struct_xs_handle, xs_transaction_t, c_bool ]
xs_transaction_end.restype = c_bool


# connect to the XenStore daemon
xsh = xs_domain_open()


class XenStoreLiteError(Exception):
    pass


#
# assert_connected()
# ----------------
## Make sure that we are connected to the XenStore daemon
#
def assert_connected():
    global xsh

    if xsh == None:
        xsh = xs_domain_open()

        if xsh == None:
            raise XenStoreLiteError("can't connect to the XenStore daemon")


#
# xenstore_read()
# -------------
## Get the value of a single XenStore file
# @param  path      path of the XenStore file
# @return string    value or None in case of failure
#
def xenstore_read(path):
    global xsh

    # check that we are connected to the XenStore daemon
    assert_connected()

    # read the value from the XenStore file
    length = c_uint()
    value = xs_read(xsh, 0, path, byref(length))

    return value


#
# xenstore_write()
# --------------
## Write the value of a single XenStore file
# @param  path      path of the XenStore file
# @param  value     value to write
# @return bool      true for success, false for failure
#
def xenstore_write(path, value):
    global xsh

    # check that we are connected to the XenStore daemon
    assert_connected()

    # make sure the value is a string
    value = str(value)

    # write the value to the XenStore file
    r = xs_write(xsh, 0, path, value, len(value))

    return r

