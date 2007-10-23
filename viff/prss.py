# Copyright 2007 Martin Geisler
#
# This file is part of VIFF
#
# VIFF is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# VIFF is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with VIFF in the file COPYING; if not, write to the Free
# Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA

"""Methods for pseudo-random secret sharing."""

import sha
from math import ceil
from struct import pack
from binascii import hexlify

from gmpy import numdigits

from viff import shamir


def prss(n, j, field, prfs, key):
    """Return a pseudo-random secret share for a random number.

    The share is for player j based on the pseudo-random functions
    given. The key is used when evaluating the PRFs.

    An example with (n,t) = (3,1) and a modulus of 31:

    >>> from field import GF
    >>> Zp = GF(31)
    >>> prfs = {frozenset([1,2]): PRF("a", 31),
    ...         frozenset([1,3]): PRF("b", 31),
    ...         frozenset([2,3]): PRF("c", 31)}
    >>> prss(3, 1, Zp, prfs, "key")
    {22}
    >>> prss(3, 2, Zp, prfs, "key")
    {20}
    >>> prss(3, 3, Zp, prfs, "key")
    {18}

    We see that the sharing is consistent because each subset of two
    players will recombine their shares to {29}.

    @param n: number of players
    @param j: id of dealing player
    @param field: field to use
    @param prfs: mapping from subsets of players to L{PRF} instances
    """
    result = 0
    all = frozenset(range(1, n+1))
    # The PRFs contain the subsets we need, plus some extra in the
    # case of dealer_keys. That is why we have to check that j is in
    # the subset before using it.
    for subset in prfs.iterkeys():
        if j in subset:
            points = [(field(x), 0) for x in all-subset]
            points.append((0, 1))
            f_in_j = shamir.recombine(points, j)
            result += prfs[subset](key) * f_in_j

    return result
    
def generate_subsets(orig_set, size):
    """Generates the set of all subsets of a specific size.

    >>> generate_subsets(frozenset('abc'), 2)
    frozenset([frozenset(['c', 'b']), frozenset(['a', 'c']), frozenset(['a', 'b'])])

    Generating subsets larger than the initial set return the empty
    set:

    >>> generate_subsets(frozenset('a'), 2)
    frozenset([])
    """
    if len(orig_set) > size:
        result = set()
        for element in orig_set:
            result.update(generate_subsets(orig_set - set([element]), size))
        return frozenset(result)
    elif len(orig_set) == size:
        return frozenset([orig_set])
    else:
        return frozenset()

# Generating 100,000 bytes like this:
#
# x = PRF("a", 256)
# for i in xrange(100000):
#     sys.stdout.write(chr(x(i)))
# 
# and piping them into ent (http://www.fourmilab.ch/random/) gives:
#    
# Entropy = 7.998124 bits per byte.
#
# Optimum compression would reduce the size
# of this 100000 byte file by 0 percent.
#
# Chi square distribution for 100000 samples is 260.10, and randomly
# would exceed this value 50.00 percent of the times.
#
# Arithmetic mean value of data bytes is 127.6850 (127.5 = random).
# Monte Carlo value for Pi is 3.156846274 (error 0.49 percent).
# Serial correlation coefficient is 0.000919 (totally uncorrelated = 0.0).
class PRF(object):
    """Models a pseudo random function (a PRF).

    The numbers are based on a SHA1 hash of the initial key.

    Each PRF is created based on a key (which should be random and
    secret) and a maximum (which may be public):

    >>> f = PRF("some random key", 256)

    Calling f return values between zero and the given maximum:

    >>> f(1)
    246L
    >>> f(2)
    254L
    >>> f(3)
    13L
    """

    def __init__(self, key, max):
        """Create a PRF keyed with the given key and max.

        The key must be a string whereas the max must be a number.
        Output value will be in the range zero to max, with zero
        included and max excluded.
        
        To make a PRF what generates numbers less than 1000 do:

        >>> f = PRF("key", 1000)

        The PRF can be evaluated by calling it on some input:

        >>> f("input")
        327L

        Creating another PRF with the same key gives identical results
        since f and g are deterministic functions, depending only on
        the key:

        >>> g = PRF("key", 1000)
        >>> g("input")
        327L

        We can test that f and g behave the same on many inputs:

        >>> [f(i) for i in range(100)] == [g(i) for i in range(100)]
        True

        Both the key and the max is used when the PRF is keyed. This
        means that

        >>> f = PRF("key", 1000)
        >>> g = PRF("key", 10000)
        >>> [f(i) for i in range(100)] == [g(i) for i in range(100)]
        False
        """
        self.max = max

        # Number of bits needed for a number in the range [0, max-1].
        bit_length = numdigits(max-1, 2)

        # Number of whole digest blocks needed.
        blocks = int(ceil(bit_length / 8.0 / sha.digest_size))

        # Number of whole bytes needed.
        self.bytes = int(ceil(bit_length / 8.0))
        # Number of bits needed from the final byte.
        self.bits = bit_length % 8

        self.sha1s = []
        for i in range(blocks):
            # TODO: this construction is completely ad-hoc and not
            # known to be secure...

            # Initial seed is key + str(max). The maximum is included
            # since we want PRF("input", 100) and PRF("input", 1000)
            # to generate different output.
            seed = key + str(max)

            # The i'th generator is seeded with H^i(key + str(max))
            # where H^i means repeated hashing i times.
            for _ in range(i):
                seed = sha.new(seed).digest()
            self.sha1s.append(sha.new(seed))

 
    def __call__(self, input):
        """Return a number based on input.

        If the input is not already a string, it is hashed (using the
        normal Python hash built-in) and the hash value is used
        instead. The hash value is a 32 bit value, so a string should
        be given if one wants to evaluate the PRF on more that 2**32
        different values.

        >>> prf = PRF("key", 1000)
        >>> prf(1), prf(2), prf(3)
        (714L, 80L, 617L)
        
        Since prf is a function we can of course evaluate the same
        input to get the same output:

        >>> prf(1)
        714L

        The prf can take arbitrary input:

        >>> prf(("input", 123))
        474L

        but it must be hashable:

        >>> prf(["input", 123])
        Traceback (most recent call last):
            ...
        TypeError: list objects are unhashable
        """
        # We can only feed str data to sha1 instance, so we must
        # convert the input. 
        if not isinstance(input, str):
            input = pack("L", hash(input))

        # There is a chance that we generate a number that is too big,
        # so we must keep trying until we succeed.
        while True:
            # We collect a digest for each keyed sha1 instance.
            digests = []
            for sha1 in self.sha1s:
                # Must work on a copy of the keyed sha1 instance.
                copy = sha1.copy()
                copy.update(input)
                digests.append(copy.digest())

            digest = ''.join(digests)
            random_bytes = digest[:self.bytes]

            # Convert the random bytes to a long by converting it to
            # hexadecimal representation first.
            result = long(hexlify(random_bytes), 16)

            # Shift to get rid of the surplus bits (if needed).
            if self.bits:
                result >>= (8 - self.bits)

            if result < self.max:
                return result
            else:
                # TODO: is this safe? The first idea was to append a
                # fixed string (".") every time, but that makes f("a")
                # and f("a.") return the same number.
                #
                # The final byte of the digest depends on the key
                # which means that it should not be possible to
                # predict it and so it should be hard to find pairs of
                # inputs which give the same output value.
                input += digest[-1]

if __name__ == "__main__":
    import doctest
    doctest.testmod()
