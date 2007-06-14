
"""
Modeling of fields. The IntegerFieldElement models integer field
elements whereas GF256Element models elements from the GF(2^8) field.
"""

# TODO: add unit tests

from gmpy import mpz

class FieldElement:
    """Common base class for elements."""

    @classmethod
    def field(cls, value):
        """
        Return a new element.
        """
        return cls(value)


class IntegerFieldElement(FieldElement):
    """
    Implements an integer field, Zp for some p. Assign to
    IntegerFieldElement.modulus before use.
    """

    modulus = None

    def __init__(self, value):
        if self.modulus is None:
            raise ValueError("You must assign a value to "
                             "IntegerFieldElement.modulus")

        self.value = value % self.modulus

    def __add__(self, other):
        if isinstance(other, IntegerFieldElement):
            other = other.value
        return IntegerFieldElement(self.value + other)

    __radd__ = __add__

    def __sub__(self, other):
        """Subtraction.

        >>> IntegerFieldElement.modulus = 31
        >>> IntegerFieldElement(5) - IntegerFieldElement(3)
        {2}

        Mixed arguments work as well:
        >>> IntegerFieldElement(5) - 3
        {2}

        Underflows wrap around as expected:
        >>> IntegerFieldElement(5) - 10
        {26}
        """
        if isinstance(other, IntegerFieldElement):
            other = other.value
        return IntegerFieldElement(self.value - other)

    def __rsub__(self, other):
        """Subtraction.

        >>> IntegerFieldElement.modulus = 31
        >>> 5 - IntegerFieldElement(3)
        {2}
        """
        return IntegerFieldElement(other - self.value)

    def __mul__(self, other):
        if isinstance(other, IntegerFieldElement):
            other = other.value
        return IntegerFieldElement(self.value * other)

    __rmul__ = __mul__

    # TODO: add in-place operators to save on the number of newly
    # constructed objects.

    def __pow__(self, exponent):
        return IntegerFieldElement(pow(self.value, exponent, self.modulus))

    def __neg__(self):
        return IntegerFieldElement(-self.value)

    def __invert__(self):
        def extended_gcd(a, b):
            """
            The extended Euclidean algorithm.
            """
            x = 0
            lastx = 1
            y = 1
            lasty = 0
            while b != 0:
                quotient = a // b
                a, b = b, a % b
                x, lastx = lastx - quotient*x, x
                y, lasty = lasty - quotient*y, y

            return (lastx, lasty, a)

        inverse = extended_gcd(self.value, self.modulus)[0]
        return IntegerFieldElement(inverse)

    def __div__(self, other):
        assert isinstance(other, IntegerFieldElement), \
            "Must supply an IntegerFieldElement, you gave a %s" % type(other)
        return self * ~other

    def __rdiv__(self, other):
        return IntegerFieldElement(other) / self

    def sqrt(self):
        """
        Computes a square-root.

        No attempt is made the to return the positive square-root:

        >>> IntegerFieldElement.modulus = 31
        >>> a = IntegerFieldElement(3)
        >>> a**2
        {9}
        >>> (a**2).sqrt()
        {28}

        Note that {28} = {-3} which is a proper square-root of {9}.
        """
        root = pow(self.value, (self.modulus+1)//4, self.modulus)
        return IntegerFieldElement(root)

    def bit(self, index):
        """
        Extract the bit with the given index (counted from zero).

        >>> IntegerFieldElement.modulus = 31
        >>> a = IntegerFieldElement(20)
        >>> [a.bit(i) for i in range(6)]
        [0, 0, 1, 0, 1, 0]
        """
        return (self.value >> index) & 1

    def __repr__(self):
        return "{%s}" % self.value

#    def __repr__(self):
#        return "IntegerFieldElement(%d)" % (self.value)

    def __eq__(self, other):
        if isinstance(other, IntegerFieldElement):
            other = other.value
        return self.value == other



class GMPIntegerFieldElement(FieldElement):
    """
    Models elements from an integer field. Uses GMPY in an attempt to
    speed things up.
    """

    modulus = None

    def __init__(self, value):
        self.value = mpz(value) % self.modulus

    def __getstate__(self):
        return long(self.value)

    def __setstate__(self, state):
        self.value = mpz(state)

    def __add__(self, other):
        if isinstance(other, GMPIntegerFieldElement):
            other = other.value
        return GMPIntegerFieldElement(self.value + other)

    __radd__ = __add__

    def __sub__(self, other):
        if isinstance(other, GMPIntegerFieldElement):
            other = other.value
        return GMPIntegerFieldElement(self.value - other)

    def __rsub__(self, other):
        return GMPIntegerFieldElement(other - self.value)

    def __mul__(self, other):
        if isinstance(other, GMPIntegerFieldElement):
            other = other.value
        return GMPIntegerFieldElement(self.value * other)

    __rmul__ = __mul__

    # TODO: add in-place operators to save on the number of newly
    # constructed objects.

    def __pow__(self, exponent):
        return GMPIntegerFieldElement(pow(self.value, exponent, self.modulus))

    def __neg__(self):
        return GMPIntegerFieldElement(-self.value)

    def __invert__(self):
        return GMPIntegerFieldElement(self.value.invert(self.modulus))

    def __div__(self, other):
        return self * ~other

    def __rdiv__(self, other):
        return GMPIntegerFieldElement(other) / self

    def sqrt(self):
        """
        Return a square root.
        """
        root = pow(self.value, (self.modulus+1)//4, self.modulus)
        return GMPIntegerFieldElement(root)

    def __repr__(self):
        return "{%s}" % self.value

#    def __repr__(self):
#        return "GMPIntegerFieldElement(%d)" % self.value

    def __eq__(self, other):
        return self.value == other.value


_log_table = {}
_exp_table = {}
_inv_table = {}

def _generate_tables():
    """
    Generate tables with logarithms, exponentials and inverses.

    Code adapted from http://www.samiam.org/galois.html.
    """
    a = 1
    for c in range(255):
        a &= 0xff
        _exp_table[c] = a
        d = a & 0x80
        a <<= 1
        if d == 0x80:
            a ^= 0x1b
        a ^= _exp_table[c]
        _log_table[_exp_table[c]] = c
    _exp_table[255] = _exp_table[0]
    _log_table[0] = 0

    #_inv_table[0] = 0
    for c in range(1, 255):
        _inv_table[c] = _exp_table[255 - _log_table[c]]

_generate_tables()

class GF256Element(FieldElement):
    """
    Models an element of the GF(2^8) field.
    """

    modulus = 256

    def __init__(self, value):
        self.value = value % self.modulus

    def __add__(self, other):
        """Add this and another GF256Element.

        For example:
        >>> GF256Element(0x01) + GF256Element(0x01)
        [0]
        >>> GF256Element(0x01) + GF256Element(0x02)
        [3]

        Adding integers works too, the other operand is coerced into a
        GF256Element automatically:
        >>> GF256Element(0x01) + 1
        [0]
        """
        if isinstance(other, GF256Element):
            other = other.value
        return GF256Element(self.value ^ other)

    __radd__ = __add__
    __sub__ = __add__
    __rsub__ = __sub__

    def __iadd__(self, other):
        if isinstance(other, GF256Element):
            other = other.value
        self.value ^= other
        return self

    __isub__ = __iadd__

    def __mul__(self, other):
        """Multiply this and another GF256Element.

        >>> GF256Element(0) * GF256Element(47)
        [0]
        >>> GF256Element(2) * GF256Element(3)
        [6]
        >>> GF256Element(16) * GF256Element(32)
        [54]
        """
        if isinstance(other, GF256Element):
            other = other.value
        if self.value == 0 or other == 0:
            return GF256Element(0)
        else:
            log_product = (_log_table[self.value] + _log_table[other]) % 255
            return GF256Element(_exp_table[log_product])

    __rmul__ = __mul__

    def __pow__(self, exponent):
        result = GF256Element(1)
        for _ in range(exponent):
            result *= self
        return result

    def __div__(self, other):
        return self * ~other

    def __rdiv__(self, other):
        return GF256Element(other) / self

    def __invert__(self):
        return GF256Element(_inv_table[self.value])

    def __repr__(self):
        return "[%d]" % self.value

    def __eq__(self, other):
        if isinstance(other, GF256Element):
            other = other.value
        return self.value == other


if __name__ == "__main__":
    import doctest
    doctest.testmod()
