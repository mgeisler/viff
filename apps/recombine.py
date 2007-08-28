#!/usr/bin/python

# Copyright 2007 Martin Geisler
#
# This file is part of PySMPC
#
# PySMPC is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# PySMPC is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PySMPC in the file COPYING; if not, write to the Free
# Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA

import sys

from pysmpc import shamir
from pysmpc.field import GF, GF256

if sys.argv[1].find(":") == -1:
    F = GF(int(sys.argv.pop(1)))
else:
    F = GF256

print "Field: GF%d" % F.modulus

shares = [map(int, arg.split(":")) for arg in sys.argv[1:]]
shares = [(F(id), F(share)) for id,share in shares]

print "Shares:", shares
print "Result:", shamir.recombine(shares)
